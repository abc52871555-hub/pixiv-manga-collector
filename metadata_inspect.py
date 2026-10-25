"""metadata_inspect.py — 图片文本元数据 / AI 生成残留检查器（纯标准库）。

对外只有一个同步函数::

    from metadata_inspect import inspect_image
    info = inspect_image(r"path\\to\\image.png")

特点：

* 核心只依赖标准库（os / struct / zlib / re / io / json）；Pillow 为可选依赖，
  仅用于 LSB/Alpha 隐写深扫，缺失时自动跳过并写入 notes，不影响其余解析；
* 永不抛异常：解析失败返回 ``{"ok": False, "error": "..."}`` 形式的字典；
* 支持 PNG（tEXt / zTXt / iTXt / eXIf）、JPEG（APP1 Exif、APP1 XMP、COM）、
  WebP（EXIF / XMP）、GIF（Comment Extension）；
* 额外做一遍整文件 printable 字符串扫描作为兜底；
* 对 PNG / WebP 追加 LSB/Alpha 隐写深扫：识别 NovelAI ``stealth_pngcomp`` /
  ``stealth_pnginfo`` 与 RGB LSB 变体（``stealth_rgbcomp`` / ``stealth_rgbinfo``），
  以及无 magic 的裸 JSON 载荷；解析出的 JSON 会拆成可读字段；
* 识别 Stable Diffusion / NovelAI / ComfyUI / Midjourney 等生成参数残留，
  返回字段、命中标记、证据片段，可直接 JSON 序列化。

命令行自测::

    python metadata_inspect.py path\\to\\a.png path\\to\\b.jpg
"""

from __future__ import annotations

import io
import json
import os
import re
import stat
import struct
import zlib

try:  # Pillow 为可选依赖：只用于 LSB/Alpha 深扫，缺失时由 _lsb_deep_scan 记录 note
    from PIL import Image as _PILImage
except Exception:  # pragma: no cover - 取决于运行环境
    _PILImage = None

__all__ = ["inspect_image"]

# --------------------------------------------------------------------------- #
# 常量 / 阈值
# --------------------------------------------------------------------------- #

MAX_FILE_BYTES = 64 * 1024 * 1024      # 直接读入内存的上限（需求要求支持 <= 50MB）
MAX_FIELD_CHARS = 4000                 # 每个元数据 value 的最大长度（供界面展开查看）
MAX_EVIDENCE_CHARS = 300               # 摘要 evidence 的长度上限
MAX_FIELDS = 200                       # fields 条目上限，防止恶意文件撑爆
MAX_CHUNKS = 100000                    # chunk / segment 数量上限
MAX_SEGMENT_READ = 32 * 1024 * 1024    # 单个 chunk/segment 最大处理字节数
MAX_DECOMPRESSED = 4 * 1024 * 1024     # zlib 解压文本上限，防 zip bomb
MAX_EXIF_IFD_ENTRIES = 1000            # 单个 IFD 条目上限
MAX_EXIF_VALUE = 8 * 1024 * 1024       # 单个 EXIF 值上限
MAX_SCAN_BYTES = 64 * 1024 * 1024      # printable 兜底扫描覆盖的字节数
MAX_SCAN_STRINGS = 5000                # printable 兜底扫描最多保留的字符串数
MAX_SCAN_STRING_LEN = 400              # 单条扫描字符串截断长度
MAX_ANALYZE_CHARS = 1_000_000          # 单个字段参与特征匹配的最大字符数

# ---- LSB / Alpha 隐写深扫参数（Pillow 可选；超限只跳过深扫，不影响其它解析）----
MAX_LSB_SIDE = 8000                    # 单边像素上限，超过即跳过深扫
MAX_LSB_PIXELS = 24_000_000            # 总像素上限（解码为 RGBA 约 96MB，峰值约 130MB）
LSB_PREFIX_BYTES = 2048                # magic 滑动搜索覆盖的前缀字节数
MAX_LSB_PAYLOAD = 1_500_000            # 单次从像素中提取的嵌入数据上限（压缩/原始字节）
MAX_LSB_JSON_SCAN = 262_144            # 无 magic 裸 JSON 兜底时最多提取的字节数
MAX_LSB_ATTEMPTS = 6                   # 单张图最多尝试解码的候选数（防病态文件拖慢）
MAX_LSB_NOTES = 60                     # notes 总条数上限（防恶意文件刷屏）

# 已知 stealth 隐写 magic（NovelAI / Forge / SwarmUI 等，均为 15 字节 ASCII）
LSB_MAGICS = (
    b"stealth_pngcomp",
    b"stealth_pnginfo",
    b"stealth_rgbcomp",
    b"stealth_rgbinfo",
)
# 无 magic 时用于兜底识别的 JSON 开头特征（要求足够长，避免随机噪声误触发）
LSB_JSON_HINTS = (
    b'{"prompt',
    b'{"steps',
    b'{"parameters',
    b'{"Description',
    b'{"uc"',
    b'{"uc":',
    b'{"Comment',
    b'{"Software',
    b'{"positive_prompt',
)
# 把 8 个“0/1 字节”打包成 1 个字节的乘法常量（LSB 收集，等价于 numpy.packbits）
_LSB_GATHER = 0x0102040810204080
_LSB_MASK = 0x0101010101010101
_LSB_BITREVERSE = bytes(int(format(value, "08b")[::-1], 2) for value in range(256))

# LSB 载荷 JSON 里常见 key（统一小写），用于抽取可读字段
_LSB_PROMPT_KEYS = ("description", "prompt", "positive_prompt", "positive", "caption")
_LSB_UC_KEYS = ("uc", "negative_prompt", "negative", "undesired_content")
_LSB_STEPS_KEYS = ("steps", "step")
_LSB_SAMPLER_KEYS = ("sampler", "sampler_name")
_LSB_SCHEDULE_KEYS = ("schedule", "scheduler", "noise_schedule")
_LSB_SEED_KEYS = ("seed",)
_LSB_SCALE_KEYS = ("scale", "cfg_scale", "cfg", "guidance", "guidance_scale")
_LSB_MODEL_KEYS = ("model", "model_name", "base_model", "sd_model", "model_hash")
_LSB_SOFTWARE_KEYS = ("software", "app", "tool", "source", "generator")

PNG_SIG = b"\x89PNG\r\n\x1a\n"

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS_RE = re.compile(r"\s+")
_PRINTABLE_RE = re.compile(rb"[ -~]{6,}")
_NORM_RE = re.compile(r"[^a-z0-9]+")

# --------------------------------------------------------------------------- #
# AI 生成残留特征
# --------------------------------------------------------------------------- #

# 强特征：出现即视为生成痕迹（不区分大小写）
_STRONG_MARKERS = (
    ("stable diffusion", re.compile(r"(?i)stable[\s\-_]*diffusion")),
    ("novelai", re.compile(r"(?i)novel[\s\-_]*ai(?:\.net)?")),
    ("comfyui", re.compile(r"(?i)comfy[\s\-_]*ui")),
    ("midjourney", re.compile(r"(?i)midjourney")),
    ("dall-e", re.compile(r"(?i)dall[\s\-·]*e")),
    ("automatic1111", re.compile(r"(?i)automatic[\s\-_]*1111|a1111")),
    ("invokeai", re.compile(r"(?i)invoke[\s\-_]*ai")),
    ("fooocus", re.compile(r"(?i)fooocus")),
    ("sd-webui", re.compile(r"(?i)sd[\s\-_]*webui|stable[\s\-_]*diffusion[\s\-_]*webui")),
    ("sdxl", re.compile(r"(?i)\bsdxl\b")),
    ("flux", re.compile(r"(?i)\bflux(?:\.1|1)?\b")),
    ("model_hash", re.compile(r"(?i)model[\s\-_]*hash")),
    ("<lora:", re.compile(r"(?i)<lora:[^>]{0,300}>")),
    ("denoising_strength", re.compile(r"(?i)denoising[\s\-_]*strength")),
    ("negative prompt", re.compile(r"(?i)negative[\s\-_]*prompt")),
)

# 参数特征：单独出现容易误报，必须同一字段里命中 >= 2 个才视为生成参数块
_PARAM_PATTERNS = (
    ("steps", re.compile(r"(?i)\bsteps\s*:\s*\d{1,4}\b")),
    ("sampler", re.compile(r"(?i)\bsampler\s*:\s*[^\s,;]{2,48}")),
    ("cfg scale", re.compile(r"(?i)\bcfg\s*scale\s*:\s*\d+(?:\.\d+)?")),
    ("seed", re.compile(r"(?i)\bseed\s*:\s*\d{1,20}")),
    ("model_hash", re.compile(r"(?i)\bmodel\s*hash\s*:\s*[0-9a-f]{6,32}")),
    ("denoising_strength", re.compile(r"(?i)\bdenoising_strength\s*:\s*\d")),
)

# key（PNG keyword / EXIF 标签名）命中即视为“值得一提的残留”，且 value 非空
_RESIDUAL_KEYS = frozenset(
    {
        "parameters",
        "prompt",
        "negativeprompt",
        "workflow",
        "sdmetadata",
        "comment",
        "software",
        "description",
        "usercomment",
        "xpcomment",
        "imagedescription",
    }
)

# EXIF 里我们要提取的标签（2 字节 tag -> 名称）
_EXIF_TAGS = {
    270: "ImageDescription",
    305: "Software",
    315: "Artist",
    316: "HostComputer",
    33432: "Copyright",
    37510: "UserComment",
    40091: "XPTitle",
    40092: "XPComment",
    40093: "XPAuthor",
    40094: "XPKeywords",
    40095: "XPSubject",
}
_EXIF_IFD_POINTER = 34665
_GPS_IFD_POINTER = 34853

_TYPE_SIZES = {
    1: 1,   # BYTE
    2: 1,   # ASCII
    3: 2,   # SHORT
    4: 4,   # LONG
    5: 8,   # RATIONAL
    6: 1,   # SBYTE
    7: 1,   # UNDEFINED
    8: 2,   # SSHORT
    9: 4,   # SLONG
    10: 8,  # SRATIONAL
    11: 4,  # FLOAT
    12: 8,  # DOUBLE
}

_XMP_APP1 = b"http://ns.adobe.com/xap/1.0/"
_XMP_EXT_APP1 = b"http://ns.adobe.com/xmp/extension/"


# --------------------------------------------------------------------------- #
# 文本清理 / 解码工具
# --------------------------------------------------------------------------- #

def _clean_text(value, limit=None):
    """清理控制字符、折叠空白；limit 为最大保留字符数。"""
    if not isinstance(value, str):
        return ""
    text = value.replace("\ufeff", "").replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = _CONTROL_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    if limit is not None and len(text) > limit:
        text = text[:limit]
    return text


def _text_score(text):
    """粗略衡量一段解码文本的“可读性”，用于 UTF-16 字节序猜测。"""
    if not text:
        return -1
    score = 0
    for ch in text[:2000]:
        if "\x00" <= ch <= "\x1f":
            score -= 3
        elif " " <= ch <= "~":
            score += 2
        elif ch.isprintable():
            score += 1
        else:
            score -= 1
    return score


def _decode_text_bytes(data, encodings=("utf-8", "latin-1")):
    """按给定编码依次尝试解码；明显是二进制就返回空字符串。"""
    if not data:
        return ""
    data = data.rstrip(b"\x00")
    if not data:
        return ""
    for enc in encodings:
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if not text:
            continue
        bad = sum(1 for ch in text if not ch.isprintable() and ch not in "\r\n\t")
        if bad > max(4, len(text) // 5):
            continue
        return text
    return ""


def _looks_utf16(raw):
    if len(raw) < 4 or len(raw) % 2:
        return False
    even_nulls = raw[0::2].count(0)
    odd_nulls = raw[1::2].count(0)
    threshold = max(2, len(raw) // 8)
    return odd_nulls > threshold or even_nulls > threshold


def _decode_utf16_auto(raw):
    """不依赖 TIFF 字节序的 UTF-16 解码：先看空字节分布，再比可读性。"""
    raw = raw.rstrip(b"\x00")
    if not raw:
        return ""
    if len(raw) % 2:
        raw += b"\x00"
    order = None
    even_nulls = raw[0::2].count(0)
    odd_nulls = raw[1::2].count(0)
    if odd_nulls > even_nulls * 2:
        order = "utf-16-le"
    elif even_nulls > odd_nulls * 2:
        order = "utf-16-be"
    candidates = []
    if order:
        candidates.append(order)
    candidates.extend(["utf-16-le", "utf-16-be"])
    best = ""
    best_score = -10 ** 9
    for enc in candidates:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if "\ufeff" in text:
            text = text.replace("\ufeff", "")
        score = _text_score(text)
        if score > best_score:
            best, best_score = text, score
    return best


def _zlib_decompress(data, notes, what, limit=MAX_DECOMPRESSED):
    """限长 zlib 解压；失败抛 ValueError，由调用方记录 note。"""
    decomp = zlib.decompressobj()
    try:
        out = decomp.decompress(data, limit + 1)
    except zlib.error as exc:
        raise ValueError("zlib 解压失败: %s" % exc) from exc
    if len(out) > limit:
        notes.append("%s 解压文本超过 %d 字节，已截断" % (what, limit))
        out = out[:limit]
    elif not decomp.eof:
        notes.append("%s 的 zlib 数据不完整（可能被截断）" % what)
    return out


# --------------------------------------------------------------------------- #
# EXIF（TIFF）解析
# --------------------------------------------------------------------------- #

def _decode_user_comment(raw, endian):
    """解码 EXIF UserComment（37510）：ASCII\\0\\0\\0 / UNICODE\\0 / JIS\\0 三种前缀。"""
    if not raw:
        return ""
    if len(raw) >= 8:
        head = raw[:8]
        body = raw[8:]
        if head[:5] == b"ASCII":
            text = _decode_text_bytes(body, ("ascii", "latin-1"))
            return text or body.decode("latin-1", "replace")
        if head[:7] == b"UNICODE":
            return _decode_utf16_auto(body)
        if head[:3] == b"JIS":
            try:
                return body.decode("shift_jis", "replace")
            except (UnicodeDecodeError, LookupError):
                pass
    if _looks_utf16(raw):
        return _decode_utf16_auto(raw)
    text = _decode_text_bytes(raw, ("utf-8", "shift_jis", "latin-1"))
    return text or raw.decode("latin-1", "replace")


def _decode_exif_value(tag, typ, raw, endian):
    """把单个目标 EXIF 标签的值解码成文本；不认识的返回空串。"""
    if tag == 37510:
        return _decode_user_comment(raw, endian)
    if tag in (40091, 40092, 40093, 40094, 40095):
        return _decode_utf16_auto(raw)
    if typ == 2:  # ASCII：可能包含多个 \0 分隔串，取第一个
        raw = raw.split(b"\x00", 1)[0]
        return _decode_text_bytes(raw.rstrip(b"\x00"), ("utf-8", "latin-1"))
    if typ in (1, 7):  # BYTE / UNDEFINED：当作文本尝试
        return _decode_text_bytes(raw.rstrip(b"\x00"), ("utf-8", "latin-1"))
    return ""


def _parse_exif(tiff, notes):
    """解析 TIFF/EXIF，返回 [(标签名, 文本), ...]。支持 IFD0 + 一层 ExifIFD。"""
    fields = []
    if len(tiff) < 8:
        raise ValueError("TIFF 头不足 8 字节")
    if tiff[:2] == b"II":
        endian = "<"
    elif tiff[:2] == b"MM":
        endian = ">"
    else:
        raise ValueError("TIFF 字节序标识非法")

    magic = struct.unpack_from(endian + "H", tiff, 2)[0]
    if magic == 43:
        raise ValueError("BigTIFF 暂不支持")
    if magic != 42:
        raise ValueError("TIFF magic=%d 非 42/43" % magic)

    ifd0 = struct.unpack_from(endian + "I", tiff, 4)[0]
    if ifd0 == 0:
        return fields

    queue = [(ifd0, 0)]
    visited = set()
    while queue:
        offset, depth = queue.pop(0)
        if depth > 3 or offset in visited:
            continue
        visited.add(offset)
        if offset < 8 or offset + 2 > len(tiff):
            notes.append("EXIF IFD 偏移 %d 越界，跳过" % offset)
            continue
        count = struct.unpack_from(endian + "H", tiff, offset)[0]
        if count > MAX_EXIF_IFD_ENTRIES:
            notes.append(
                "EXIF IFD 条目数异常（%d），只读前 %d 条" % (count, MAX_EXIF_IFD_ENTRIES)
            )
            count = MAX_EXIF_IFD_ENTRIES
        base = offset + 2
        for index in range(count):
            entry = base + 12 * index
            if entry + 12 > len(tiff):
                notes.append("EXIF IFD 条目越界，停止读取")
                break
            tag, typ, cnt = struct.unpack_from(endian + "HHI", tiff, entry)
            comp = _TYPE_SIZES.get(typ)
            if comp is None:
                continue
            total = comp * cnt
            if total > MAX_EXIF_VALUE:
                notes.append("EXIF 标签 %d 值过大（%d 字节），跳过" % (tag, total))
                continue
            if total <= 4:
                raw = tiff[entry + 8 : entry + 8 + total]
            else:
                value_offset = struct.unpack_from(endian + "I", tiff, entry + 8)[0]
                if value_offset + total > len(tiff):
                    notes.append("EXIF 标签 %d 值偏移越界，跳过" % tag)
                    continue
                raw = tiff[value_offset : value_offset + total]

            if tag == _EXIF_IFD_POINTER:
                if typ == 4 and cnt >= 1 and len(raw) >= 4:
                    queue.append((struct.unpack_from(endian + "I", raw, 0)[0], depth + 1))
                continue
            if tag == _GPS_IFD_POINTER:
                continue
            name = _EXIF_TAGS.get(tag)
            if not name:
                continue
            try:
                text = _decode_exif_value(tag, typ, raw, endian)
            except Exception as exc:  # pragma: no cover - 防御性
                notes.append("EXIF %s 解码失败: %r" % (name, exc))
                continue
            if text:
                fields.append((name, text))

    if not fields:
        notes.append("EXIF 已解析，但未发现目标文本标签")
    return fields


# --------------------------------------------------------------------------- #
# PNG
# --------------------------------------------------------------------------- #

def _png_keyword(payload):
    index = payload.find(b"\x00")
    if index <= 0:
        raise ValueError("缺少 keyword 分隔符")
    keyword = payload[:index].decode("latin-1", "replace").strip()
    return keyword or "?", index + 1


def _png_text(payload):
    keyword, start = _png_keyword(payload)
    return keyword, payload[start:].decode("latin-1", "replace")


def _png_ztxt(payload, notes):
    keyword, start = _png_keyword(payload)
    if start >= len(payload):
        raise ValueError("zTXt 数据为空")
    method = payload[start]
    if method != 0:
        raise ValueError("不支持的 zTXt 压缩方法 %d" % method)
    raw = _zlib_decompress(payload[start + 1 :], notes, "PNG zTXt(%s)" % keyword)
    text = _decode_text_bytes(raw, ("utf-8", "latin-1"))
    if not text:
        text = raw.decode("latin-1", "replace")
    return keyword, text


def _png_itxt(payload, notes):
    keyword, start = _png_keyword(payload)
    if start + 2 > len(payload):
        raise ValueError("iTXt 头不完整")
    comp_flag = payload[start]
    comp_method = payload[start + 1]
    start += 2
    end_lang = payload.find(b"\x00", start)
    if end_lang < 0:
        raise ValueError("iTXt 缺少语言标签分隔符")
    start = end_lang + 1
    end_trans = payload.find(b"\x00", start)
    if end_trans < 0:
        raise ValueError("iTXt 缺少 translated keyword 分隔符")
    start = end_trans + 1
    raw = payload[start:]
    if comp_flag == 1:
        if comp_method != 0:
            raise ValueError("不支持的 iTXt 压缩方法 %d" % comp_method)
        raw = _zlib_decompress(raw, notes, "PNG iTXt(%s)" % keyword)
    elif comp_flag != 0:
        raise ValueError("非法的 iTXt 压缩标志 %d" % comp_flag)
    return keyword, raw.decode("utf-8", "replace")


def _parse_png(data, notes):
    """逐 chunk 解析 PNG，返回 [(字段key, 标签名, 文本), ...]。"""
    if not data.startswith(PNG_SIG):
        raise ValueError("PNG 签名不匹配")

    fields = []
    pos = len(PNG_SIG)
    chunks = 0
    found_iend = False
    while pos + 8 <= len(data):
        length, ctype = struct.unpack_from(">I4s", data, pos)
        pos += 8
        chunks += 1
        if chunks > MAX_CHUNKS:
            notes.append("PNG chunk 数量异常，停止解析")
            break
        if length + 4 > len(data) - pos:
            notes.append("PNG chunk 长度越界（文件可能被截断）")
            break
        if ctype == b"IEND":
            found_iend = True
            break

        if ctype not in (b"tEXt", b"zTXt", b"iTXt", b"eXIf"):
            pos += length + 4  # 跳过不关心的 chunk（含 CRC）
            continue
        if length > MAX_SEGMENT_READ:
            notes.append(
                "PNG %s chunk 过大（%d 字节），已跳过"
                % (ctype.decode("latin-1", "replace"), length)
            )
            pos += length + 4
            continue

        payload = data[pos : pos + length]
        pos += length
        crc = data[pos : pos + 4]
        pos += 4
        if len(crc) == 4:
            want = struct.unpack(">I", crc)[0]
            got = zlib.crc32(payload, zlib.crc32(ctype)) & 0xFFFFFFFF
            if want != got:
                notes.append(
                    "PNG %s chunk CRC 不匹配（继续尝试解析）"
                    % ctype.decode("latin-1", "replace")
                )

        name = ctype.decode("latin-1", "replace")
        try:
            if ctype == b"tEXt":
                keyword, text = _png_text(payload)
                fields.append(("png:text:%s" % keyword, keyword, text))
            elif ctype == b"zTXt":
                keyword, text = _png_ztxt(payload, notes)
                fields.append(("png:ztxt:%s" % keyword, keyword, text))
            elif ctype == b"iTXt":
                keyword, text = _png_itxt(payload, notes)
                fields.append(("png:itxt:%s" % keyword, keyword, text))
            elif ctype == b"eXIf":
                tiff = payload
                if tiff.startswith(b"Exif\x00\x00"):
                    tiff = tiff[6:]
                for tag_name, text in _parse_exif(tiff, notes):
                    fields.append(("png:exif:%s" % tag_name, tag_name, text))
        except Exception as exc:
            notes.append("PNG %s 解析失败: %s" % (name, exc))

    if not found_iend:
        notes.append("PNG 未找到 IEND（文件可能被截断）")
    if not fields:
        notes.append("PNG 未发现 tEXt/zTXt/iTXt/eXIf 文本元数据")
    return fields


# --------------------------------------------------------------------------- #
# JPEG
# --------------------------------------------------------------------------- #

def _handle_jpeg_app1(payload, fields, notes):
    if payload.startswith(b"Exif\x00\x00"):
        try:
            exif_fields = _parse_exif(payload[6:], notes)
        except Exception as exc:
            notes.append("JPEG APP1 Exif 解析失败: %s" % exc)
            return
        for tag_name, text in exif_fields:
            fields.append(("jpeg:exif:%s" % tag_name, tag_name, text))
        return

    if payload.startswith(_XMP_EXT_APP1):
        notes.append("发现 Extended XMP 分片（未合并解析）")
        return

    if payload.startswith(_XMP_APP1):
        start = len(_XMP_APP1)
        if payload[start : start + 1] == b"\x00":
            start += 1
        text = _decode_text_bytes(payload[start:], ("utf-8", "latin-1"))
        if text:
            fields.append(("jpeg:xmp", "xmp", text))
        else:
            notes.append("JPEG XMP 内容无法解码为文本")


def _parse_jpeg(data, notes):
    """解析 JPEG 段直到 SOS；返回 [(字段key, 标签名, 文本), ...]。"""
    if data[:2] != b"\xff\xd8":
        raise ValueError("JPEG SOI 缺失")

    fields = []
    pos = 2
    segments = 0
    reached_eoi = False
    while pos < len(data):
        if data[pos] != 0xFF:
            next_marker = data.find(b"\xff", pos)
            if next_marker < 0:
                notes.append("JPEG 段边界前遇到非 marker 数据，停止解析")
                break
            pos = next_marker
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos >= len(data):
            break
        marker = data[pos]
        pos += 1

        if marker == 0x00:
            continue
        if marker == 0xD8:
            continue
        if marker == 0xD9:
            reached_eoi = True
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if marker == 0xDA:
            notes.append("JPEG 在 SOS 后停止解析（熵编码数据已跳过）")
            break

        if pos + 2 > len(data):
            notes.append("JPEG 段长度字段缺失，停止解析")
            break
        seglen = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        if seglen < 2:
            notes.append("JPEG 段 0xFF%02X 长度非法（%d），停止解析" % (marker, seglen))
            break
        payload_len = seglen - 2
        if pos + payload_len > len(data):
            notes.append("JPEG 段 0xFF%02X 数据被截断，停止解析" % marker)
            break
        if payload_len > MAX_SEGMENT_READ:
            notes.append("JPEG 段 0xFF%02X 过大（%d 字节），已跳过" % (marker, payload_len))
            pos += payload_len
            continue
        payload = data[pos : pos + payload_len]
        pos += payload_len
        segments += 1
        if segments > MAX_CHUNKS:
            notes.append("JPEG 段数量异常，停止解析")
            break

        try:
            if marker == 0xE1:
                _handle_jpeg_app1(payload, fields, notes)
            elif marker == 0xFE:
                text = _decode_text_bytes(payload, ("utf-8", "shift_jis", "latin-1"))
                if text and _clean_text(text):
                    fields.append(("jpeg:comment", "comment", text))
        except Exception as exc:  # pragma: no cover - 防御性
            notes.append("JPEG 段 0xFF%02X 解析失败: %s" % (marker, exc))

    if not reached_eoi and not fields:
        notes.append("JPEG 未发现 Exif/XMP/COM 文本元数据")
    return fields


# --------------------------------------------------------------------------- #
# WebP
# --------------------------------------------------------------------------- #

def _parse_webp(data, notes):
    """解析 RIFF/WebP 的 EXIF、XMP chunk。"""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("WebP RIFF 头非法")

    riff_size = struct.unpack_from("<I", data, 4)[0]
    end = min(len(data), 8 + riff_size)
    fields = []
    pos = 12
    chunks = 0
    while pos + 8 <= end:
        fourcc = data[pos : pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        pos += 8
        if size > end - pos:
            notes.append(
                "WebP chunk %r 声明长度越界，停止解析"
                % fourcc.decode("latin-1", "replace")
            )
            break
        chunks += 1
        if chunks > MAX_CHUNKS:
            notes.append("WebP chunk 数量异常，停止解析")
            break
        payload = data[pos : pos + size]
        pos += size + (size & 1)

        try:
            if fourcc == b"EXIF":
                tiff = payload
                if tiff.startswith(b"Exif\x00\x00"):
                    tiff = tiff[6:]
                for tag_name, text in _parse_exif(tiff, notes):
                    fields.append(("webp:exif:%s" % tag_name, tag_name, text))
            elif fourcc == b"XMP ":
                text = _decode_text_bytes(payload, ("utf-8", "latin-1"))
                if text:
                    fields.append(("webp:xmp", "xmp", text))
        except Exception as exc:
            notes.append(
                "WebP chunk %r 解析失败: %s"
                % (fourcc.decode("latin-1", "replace"), exc)
            )

    if not fields:
        notes.append("WebP 未发现 EXIF/XMP 文本元数据")
    return fields


# --------------------------------------------------------------------------- #
# GIF
# --------------------------------------------------------------------------- #

def _gif_subblocks(data, pos):
    """读取 GIF 连续 sub-block 数据，返回 (拼接后的数据, 新位置, 是否完整)。"""
    parts = []
    total = 0
    while True:
        if pos >= len(data):
            return b"".join(parts), pos, False
        size = data[pos]
        pos += 1
        if size == 0:
            return b"".join(parts), pos, True
        if pos + size > len(data):
            return b"".join(parts), pos, False
        parts.append(data[pos : pos + size])
        pos += size
        total += size
        if total > MAX_SEGMENT_READ:
            return b"".join(parts), pos, False


def _parse_gif(data, notes):
    """解析 GIF，收集 Comment Extension（0x21 0xFE）文本。"""
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("GIF 头非法")
    if len(data) < 13:
        notes.append("GIF 逻辑屏幕描述符不完整")
        return []

    fields = []
    comments = []
    packed = data[10]  # 逻辑屏幕描述符里的全局调色板标志 / 大小
    pos = 13 + (3 * (2 ** ((packed & 0x07) + 1)) if packed & 0x80 else 0)
    while pos < len(data):
        block = data[pos]
        pos += 1
        if block == 0x3B:  # trailer
            break
        if block == 0x21:  # extension
            if pos >= len(data):
                break
            label = data[pos]
            pos += 1
            payload, pos, ok = _gif_subblocks(data, pos)
            if not ok:
                notes.append("GIF 扩展块数据被截断")
                break
            if label == 0xFE:
                text = _decode_text_bytes(payload, ("utf-8", "shift_jis", "latin-1"))
                if text:
                    comments.append(text)
        elif block == 0x2C:  # image descriptor
            if pos + 9 > len(data):
                notes.append("GIF 图像描述符被截断")
                break
            packed = data[pos + 8]
            pos += 9
            if packed & 0x80:
                pos += 3 * (2 ** ((packed & 0x07) + 1))
            pos += 1  # LZW minimum code size
            _, pos, ok = _gif_subblocks(data, pos)
            if not ok:
                notes.append("GIF 图像数据被截断")
                break
        else:
            notes.append("GIF 遇到未知块 0x%02X，停止解析" % block)
            break

    for index, text in enumerate(comments, 1):
        key = "gif:comment" if index == 1 else "gif:comment:%d" % index
        fields.append((key, "comment", text))
    if not fields:
        notes.append("GIF 未发现 Comment 扩展")
    return fields


# --------------------------------------------------------------------------- #
# printable 兜底扫描
# --------------------------------------------------------------------------- #

def _scan_printable(data):
    """把文件里 >= 6 字符的连续可打印串扫出来，作为漏解析元数据的兜底。"""
    notes = []
    if len(data) > MAX_SCAN_BYTES:
        notes.append("printable 兜底扫描只覆盖前 %d 字节" % MAX_SCAN_BYTES)
        data = data[:MAX_SCAN_BYTES]
    strings = []
    for match in _PRINTABLE_RE.finditer(data):
        if len(strings) >= MAX_SCAN_STRINGS:
            notes.append("printable 扫描达到 %d 条上限，后续未扫描" % MAX_SCAN_STRINGS)
            break
        chunk = match.group(0)
        if len(chunk) > MAX_SCAN_STRING_LEN:
            chunk = chunk[:MAX_SCAN_STRING_LEN]
        strings.append(chunk.decode("latin-1"))
    return strings, notes


# --------------------------------------------------------------------------- #
# AI 残留特征判定
# --------------------------------------------------------------------------- #

def _norm_label(label):
    return _NORM_RE.sub("", str(label).lower())


def _try_json(text):
    stripped = text.strip()
    if not stripped or len(stripped) > 4_000_000:
        return None
    if stripped[0] not in "[{":
        return None
    try:
        return json.loads(stripped)
    except (ValueError, RecursionError):
        return None


def _json_shape_markers(text):
    """识别 ComfyUI workflow/prompt 与 NovelAI Comment 的 JSON 形态。"""
    markers = []
    low = text.lower()
    if '"class_type"' in low:
        markers.append("comfyui class_type")
    if ('"nodes"' in low and ('"links"' in low or '"last_node_id"' in low)) or (
        '"workflow"' in low and '"class_type"' in low
    ):
        markers.append("comfyui workflow json")

    obj = _try_json(text)
    if isinstance(obj, dict):
        keys = {str(key).lower() for key in obj}
        if "prompt" in keys and (
            "uc" in keys
            or "negative_prompt" in keys
            or ("steps" in keys and ("seed" in keys or "scale" in keys))
        ):
            markers.append("novelai comment json")
    elif '"prompt"' in low and '"steps"' in low and '"seed"' in low and '"uc"' in low:
        markers.append("novelai comment json")
    return markers


def _markers_for_text(text):
    """返回一段文本命中的生成痕迹标记（强特征 + 参数块 + JSON 形态）。"""
    if not text:
        return []
    hits = []
    for name, pattern in _STRONG_MARKERS:
        if pattern.search(text):
            hits.append(name)

    param_hits = [name for name, pattern in _PARAM_PATTERNS if pattern.search(text)]
    if len(param_hits) >= 2:  # 至少两个参数特征共现，才认定为生成参数块
        hits.append("parameters")
        hits.extend(param_hits)

    hits.extend(_json_shape_markers(text))

    unique = []
    seen = set()
    for hit in hits:
        if hit not in seen:
            seen.add(hit)
            unique.append(hit)
    return unique


# --------------------------------------------------------------------------- #
# LSB / Alpha 隐写深扫
# --------------------------------------------------------------------------- #
#
# 参考实现与格式（2024-2025 实际生态）：
#
# * NovelAI / Forge / SwarmUI 的 stealth 隐写都写成同一层次结构：
#       15 字节 ASCII magic（见 LSB_MAGICS）
#       + 4 字节大端整数（载荷的“比特数”，因此 payload_bytes = 值 // 8）
#       + 载荷（comp 变体为 gzip 压缩的 JSON；info 变体为未压缩 UTF-8 JSON）
# * 位序：像素按“列优先”遍历（x 外层、y 内层，即 (0,0)(1,0)(2,0)...），
#   每个比特按 MSB-first 组装成字节；通道方面 alpha 变体每像素取 1 bit，
#   rgb 变体每像素依次取 R、G、B 各 1 bit。
# * 因此本模块除标准组合外，还兜底尝试：行优先遍历、LSB-first 组字节、
#   以及 magic 在载荷前 2KB 内任意字节偏移处的滑动搜索；长度字段同时兼容
#   “比特数 / 字节数 / 缺失”三种情况，压缩兼容 gzip / zlib / raw-deflate。
#
# 为防 zip bomb / 超大图卡死：限制像素数、载荷提取字节、解压字节与候选数。


def _lsb_note(notes, text):
    """写入深扫 note（上限保护，避免恶意文件刷屏）。"""
    if len(notes) >= MAX_LSB_NOTES:
        return
    notes.append(text)


def _lsb_pack_bits(parity):
    """把 0/1 序列按 MSB-first 打包成字节；末尾不足 8 位补 0。"""
    if not parity:
        return b""
    if len(parity) % 8:
        parity = bytes(parity) + b"\x00" * (8 - len(parity) % 8)
    result = bytearray(len(parity) // 8)
    gather = _LSB_GATHER
    mask = _LSB_MASK
    for index in range(len(result)):
        word = int.from_bytes(parity[index * 8 : index * 8 + 8], "big")
        result[index] = ((word & mask) * gather >> 56) & 0xFF
    return bytes(result)


def _lsb_parity_range(buffer, width, height, channels, row_major, bit_start, bit_count):
    """按指定遍历顺序抽取 LSB 序列（返回 0/1 字节串，可跨像素任意比特起点）。

    直接对 RGBA 字节串做带步长的切片，避免为整幅图复制通道平面。
    """
    total_bits = width * height * channels
    start = max(0, int(bit_start))
    end = min(total_bits, start + max(0, int(bit_count)))
    if end <= start:
        return b""
    pixel_start = start // channels
    intra = start - pixel_start * channels
    pixel_end = (end + channels - 1) // channels
    count = pixel_end - pixel_start
    parity = bytearray()
    if row_major:
        start_byte = 4 * pixel_start
        if channels == 1:
            parity += buffer[start_byte + 3 : 4 * pixel_end + 3 : 4]
        else:
            parity = bytearray(count * 3)
            for offset in (0, 1, 2):
                parity[offset::3] = buffer[
                    start_byte + offset : 4 * pixel_end + offset : 4
                ]
    else:
        x, y = divmod(pixel_start, height)
        stride = 4 * width
        remaining = count
        while remaining > 0:
            take = min(height - y, remaining)
            base = 4 * (y * width + x)
            last = base + (take - 1) * stride
            if channels == 1:
                parity += buffer[base + 3 : last + 4 : stride]
            else:
                block = bytearray(take * 3)
                for offset in (0, 1, 2):
                    block[offset::3] = buffer[
                        base + offset : last + offset + 1 : stride
                    ]
                parity += block
            remaining -= take
            x += 1
            y = 0
    return bytes(parity[intra : intra + (end - start)])


def _lsb_read_bytes(buffer, width, height, channels, row_major, packing, bit_start, byte_count):
    """从指定比特位置读出 byte_count 个字节；容量不足返回空串。"""
    if byte_count <= 0:
        return b""
    parity = _lsb_parity_range(
        buffer, width, height, channels, row_major, bit_start, byte_count * 8
    )
    if len(parity) < byte_count * 8:
        return b""
    packed = _lsb_pack_bits(parity)
    if packing == "lsb":
        packed = packed.translate(_LSB_BITREVERSE)
    return packed


def _lsb_open(data, fmt, notes):
    """用 Pillow 解码 PNG/WebP 并返回 (width, height, RGBA bytes)；失败/超限返回 None。"""
    image = None
    try:
        image = _PILImage.open(io.BytesIO(data))
        image.load()
        width, height = image.size
    except Exception as exc:
        _lsb_note(notes, "LSB 深扫无法用 Pillow 解码 %s: %s" % (fmt.upper(), exc))
        return None
    try:
        if width <= 0 or height <= 0:
            _lsb_note(notes, "LSB 深扫跳过：图片尺寸非法（%dx%d）" % (width, height))
            return None
        if width > MAX_LSB_SIDE or height > MAX_LSB_SIDE:
            _lsb_note(
                notes,
                "LSB 深扫跳过：尺寸 %dx%d 超过单边上限 %d" % (width, height, MAX_LSB_SIDE),
            )
            return None
        pixels = width * height
        if pixels > MAX_LSB_PIXELS:
            _lsb_note(
                notes,
                "LSB 深扫跳过：像素数 %d 超过上限 %d（防止大图卡死）"
                % (pixels, MAX_LSB_PIXELS),
            )
            return None
        rgba = image if image.mode == "RGBA" else image.convert("RGBA")
        buffer = rgba.tobytes()
        del rgba
        if int(getattr(image, "n_frames", 1) or 1) > 1:
            _lsb_note(notes, "多帧图片（APNG / 动画 WebP）只扫描了首帧的 LSB")
    except Exception as exc:
        _lsb_note(notes, "LSB 深扫读取像素失败: %s" % exc)
        return None
    finally:
        try:
            image.close()
        except Exception:
            pass
    if len(buffer) < width * height * 4:
        _lsb_note(notes, "LSB 深扫跳过：RGBA 像素数据不完整")
        return None
    return width, height, buffer


def _lsb_order_modes(buffer, width, height):
    """返回需要尝试的 (channels, row_major) 组合；alpha 全为 255 时跳过 alpha。"""
    modes = []
    try:
        if buffer[3::4].count(255) != width * height:
            modes.append((1, False))
            modes.append((1, True))
    except Exception:
        modes.append((1, False))
    modes.append((3, False))
    modes.append((3, True))
    return modes


def _lsb_search_hits(needles, buffer, width, height, modes, prefix_bits):
    """在前缀 LSB 流（4 种顺序/位序组合）里滑动搜索 needles，返回按优先级排序的候选。"""
    candidates = []
    seen = set()
    for channels, row_major in modes:
        parity = _lsb_parity_range(
            buffer, width, height, channels, row_major, 0, prefix_bits
        )
        if not parity:
            continue
        packed_msb = _lsb_pack_bits(parity)
        packed_variants = (("msb", packed_msb), ("lsb", packed_msb.translate(_LSB_BITREVERSE)))
        for packing, packed in packed_variants:
            for needle in needles:
                offset = packed.find(needle)
                while offset >= 0:
                    key = (channels, row_major, packing, offset, needle)
                    if key not in seen:
                        seen.add(key)
                        candidates.append(
                            {
                                "channels": channels,
                                "channel_name": "alpha" if channels == 1 else "rgb",
                                "row_major": row_major,
                                "order_name": "row-major" if row_major else "column-major",
                                "packing": packing,
                                "offset": offset,
                                "magic": needle,
                            }
                        )
                    offset = packed.find(needle, offset + 1)

    def sort_key(candidate):
        # 优先：偏移 0（规范起点）→ alpha → 列优先 → MSB-first → 偏移小
        return (
            0 if candidate["offset"] == 0 else 1,
            0 if candidate["channels"] == 1 else 1,
            0 if not candidate["row_major"] else 1,
            0 if candidate["packing"] == "msb" else 1,
            candidate["offset"],
        )

    candidates.sort(key=sort_key)
    return candidates


def _lsb_magic_candidates(buffer, width, height, modes):
    return _lsb_search_hits(LSB_MAGICS, buffer, width, height, modes, LSB_PREFIX_BYTES * 8)


def _lsb_json_candidates(buffer, width, height, modes):
    return _lsb_search_hits(
        LSB_JSON_HINTS, buffer, width, height, modes, LSB_PREFIX_BYTES * 8
    )


def _lsb_length_candidates(raw_value, capacity_bytes):
    """把 4 字节长度字段解释为若干候选载荷长度（优先“比特数”语义）。"""
    candidates = []
    if raw_value and raw_value % 8 == 0:
        bits_length = raw_value // 8
        if 0 < bits_length <= capacity_bytes:
            candidates.append(bits_length)
    if 0 < raw_value <= capacity_bytes and raw_value not in candidates:
        candidates.append(raw_value)
    return candidates


def _lsb_try_decompress(payload, notes, what):
    """依次尝试 gzip / zlib / raw-deflate 限长解压，返回 (data, 方法名) 或 (None, "")。"""
    limit = MAX_DECOMPRESSED
    for wbits, label in ((31, "gzip"), (15, "zlib"), (-15, "raw-deflate")):
        try:
            decomp = zlib.decompressobj(wbits)
            out = decomp.decompress(payload, limit + 1)
        except zlib.error:
            continue
        if len(out) > limit:
            _lsb_note(notes, "%s 解压后超过 %d 字节，已截断" % (what, limit))
            out = out[:limit]
        if out and not decomp.eof:
            _lsb_note(notes, "%s 的压缩数据不完整（可能被截断），解压内容可能不可靠" % what)
        if out or decomp.eof:
            return out, label
    return None, ""


def _lsb_payload_to_text(payload, magic, notes, what):
    """把 LSB 载荷解码成文本；返回 (text, 是否经过解压)。"""
    if not payload:
        return "", False
    expected_compressed = magic.endswith(b"comp")
    header_compressed = payload[:2] == b"\x1f\x8b" or payload[:1] == b"\x78"
    text = ""
    decompressed = False
    if expected_compressed or header_compressed:
        data, method = _lsb_try_decompress(payload, notes, what)
        if data is not None:
            text = _decode_text_bytes(data, ("utf-8", "latin-1"))
            if text:
                decompressed = True
                _lsb_note(notes, "%s 载荷按 %s 解压成功" % (what, method or "?"))
            else:
                _lsb_note(notes, "%s 解压成功但文本解码失败" % what)
        elif expected_compressed:
            _lsb_note(notes, "%s 解压失败（数据可能被截断或不是 gzip/zlib）" % what)
    if not text:
        text = _decode_text_bytes(payload.rstrip(b"\x00"), ("utf-8", "latin-1"))
    if not text and not (expected_compressed or header_compressed):
        data, method = _lsb_try_decompress(payload, notes, what)
        if data is not None:
            text = _decode_text_bytes(data, ("utf-8", "latin-1"))
            decompressed = bool(text)
    return text, decompressed


def _lsb_try_json_text(text):
    """尝试把文本解析为 JSON；失败返回 None。"""
    if not text:
        return None
    stripped = text.strip().lstrip("\ufeff").strip()
    if not stripped:
        return None
    obj = _try_json(stripped)
    if obj is not None:
        return obj
    try:
        return json.JSONDecoder().raw_decode(stripped)[0]
    except (ValueError, RecursionError):
        return None


def _lsb_flatten_json(obj, depth=0):
    """把 JSON 里嵌套的 JSON 字符串（如 NovelAI 的 Comment）摊平为小写 key 映射。"""
    flat = {}
    if not isinstance(obj, dict) or depth > 2:
        return flat
    for key, value in obj.items():
        name = str(key).strip().lower()
        if isinstance(value, str):
            stripped = value.strip()
            nested = None
            if stripped[:1] in "[{" and len(stripped) <= MAX_LSB_JSON_SCAN:
                nested = _lsb_try_json_text(stripped)
            if isinstance(nested, dict):
                for sub_key, sub_value in _lsb_flatten_json(nested, depth + 1).items():
                    flat.setdefault(sub_key, sub_value)
                continue
            flat.setdefault(name, value)
        elif isinstance(value, (int, float, bool)):
            flat.setdefault(name, value)
        elif isinstance(value, dict):
            for sub_key, sub_value in _lsb_flatten_json(value, depth + 1).items():
                flat.setdefault(sub_key, sub_value)
    return flat


def _lsb_first_value(flat, keys):
    """按 key 优先级取第一个非空标量值并清理。"""
    for key in keys:
        value = flat.get(key)
        if value is None or isinstance(value, (dict, list, tuple)):
            continue
        if isinstance(value, bool):
            text = "true" if value else "false"
        else:
            text = str(value)
        text = _clean_text(text, MAX_FIELD_CHARS)
        if text:
            return text
    return ""


def _lsb_size_text(flat):
    """拼出 width x height（JSON 里若存在）。"""
    width = flat.get("width")
    height = flat.get("height")
    try:
        if width is not None and height is not None:
            return "%dx%d" % (int(float(width)), int(float(height)))
    except (TypeError, ValueError):
        pass
    return ""


def _lsb_packing_text(packing):
    """位序的展示名。"""
    return "LSB-first" if packing == "lsb" else "MSB-first"


def _lsb_build_fields(fmt, candidate, text, obj, decompressed):
    """把一次成功命中的 LSB 载荷整理成 raw_fields + 额外 markers。"""
    channels = candidate["channels"]
    prefix = "%s:%s_lsb" % (fmt, "alpha" if channels == 1 else "rgb")
    magic_name = candidate["magic"].decode("latin-1")
    packing_text = "lsb-first" if candidate["packing"] == "lsb" else "msb-first"
    fields = []
    markers = ["lsb", magic_name]
    format_text = (
        "%s; channel=%s; order=%s; bit_order=%s; byte_offset=%d%s"
        % (
            magic_name,
            candidate["channel_name"],
            candidate["order_name"],
            packing_text,
            candidate["offset"],
            "; decompressed" if decompressed else "",
        )
    )
    fields.append(("%s:format" % prefix, "lsb", format_text))

    flat = {}
    obj_text = ""
    if isinstance(obj, dict):
        flat = _lsb_flatten_json(obj)
        try:
            obj_text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError, RecursionError):
            obj_text = ""
    if obj_text:
        fields.append(("%s:json" % prefix, "json", obj_text[:MAX_FIELD_CHARS]))

    prompt = _lsb_first_value(flat, _LSB_PROMPT_KEYS)
    uc = _lsb_first_value(flat, _LSB_UC_KEYS)
    steps = _lsb_first_value(flat, _LSB_STEPS_KEYS)
    sampler = _lsb_first_value(flat, _LSB_SAMPLER_KEYS)
    schedule = _lsb_first_value(flat, _LSB_SCHEDULE_KEYS)
    seed = _lsb_first_value(flat, _LSB_SEED_KEYS)
    scale = _lsb_first_value(flat, _LSB_SCALE_KEYS)
    model = _lsb_first_value(flat, _LSB_MODEL_KEYS)
    software = _lsb_first_value(flat, _LSB_SOFTWARE_KEYS)

    if prompt:
        fields.append(("%s:prompt" % prefix, "prompt", prompt))
    if uc:
        fields.append(("%s:uc" % prefix, "negativeprompt", uc))
    for key, value, label in (
        ("steps", steps, "steps"),
        ("sampler", sampler, "sampler"),
        ("seed", seed, "seed"),
        ("scale", scale, "parameters"),
        ("model", model, "parameters"),
    ):
        if value:
            fields.append(("%s:%s" % (prefix, key), label, value))

    summary_parts = []
    for label, value in (
        ("steps", steps),
        ("sampler", sampler),
        ("schedule", schedule),
        ("seed", seed),
        ("scale", scale),
        ("model", model),
        ("software", software),
    ):
        if value:
            summary_parts.append("%s: %s" % (label, value))
    size_text = _lsb_size_text(flat)
    if size_text:
        summary_parts.append("size: %s" % size_text)
    if summary_parts:
        fields.append(
            (
                "%s:parameters" % prefix,
                "parameters",
                ", ".join(summary_parts)[:MAX_FIELD_CHARS],
            )
        )

    # 部分实现（A1111 / Forge）把参数串直接放在 Comment / parameters 文本里
    text_params = ""
    for key in ("comment", "parameters", "parameters_text"):
        value = flat.get(key)
        if isinstance(value, str) and value.strip() and (
            "\n" in value or "steps:" in value.lower() or "sampler:" in value.lower()
        ):
            text_params = _clean_text(value, MAX_FIELD_CHARS)
            break
    if text_params:
        fields.append(("%s:parameters_text" % prefix, "parameters", text_params))
    elif not isinstance(obj, dict) and text:
        # 载荷本身不是 JSON：作为原始参数/文本保留
        fields.append(("%s:parameters_text" % prefix, "parameters", text[:MAX_FIELD_CHARS]))
    return fields, markers


def _lsb_decode_candidate(buffer, width, height, candidate, fmt, notes):
    """尝试解码一个确认 magic 的候选；成功返回 (fields, markers)，失败返回 None。"""
    channels = candidate["channels"]
    row_major = candidate["row_major"]
    packing = candidate["packing"]
    magic = candidate["magic"]
    offset = candidate["offset"]
    total_bytes = (width * height * channels) // 8
    magic_end = offset + len(magic)
    capacity = total_bytes - magic_end
    what = "LSB %s(%s/%s/%s)" % (
        magic.decode("latin-1"),
        candidate["channel_name"],
        candidate["order_name"],
        candidate["packing"],
    )
    if capacity < 4:
        _lsb_note(notes, "%s 剩余容量不足 4 字节，跳过" % what)
        return None

    length_start_bit = magic_end * 8
    raw_length = _lsb_read_bytes(
        buffer, width, height, channels, row_major, packing, length_start_bit, 4
    )
    if len(raw_length) != 4:
        _lsb_note(notes, "%s 长度字段读取失败" % what)
        return None
    length_value = int.from_bytes(raw_length, "big")
    payload_limit = min(MAX_LSB_PAYLOAD, capacity - 4)
    attempts = [
        (length_start_bit + 32, payload_length)
        for payload_length in _lsb_length_candidates(length_value, payload_limit)
    ]
    if not attempts:
        # 兼容“没有 4 字节长度字段”的变体：magic 之后直接是载荷
        fallback_length = min(capacity, MAX_LSB_JSON_SCAN)
        if fallback_length > 0:
            attempts.append((length_start_bit, fallback_length))
            _lsb_note(
                notes,
                "%s 长度字段异常（%d），按无长度字段变体尝试" % (what, length_value),
            )
    for start_bit, payload_length in attempts:
        payload = _lsb_read_bytes(
            buffer, width, height, channels, row_major, packing, start_bit, payload_length
        )
        if len(payload) != payload_length:
            continue
        text, decompressed = _lsb_payload_to_text(payload, magic, notes, what)
        if not text:
            continue
        obj = _lsb_try_json_text(text)
        if obj is None and text.lstrip()[:1] in "{[":
            # 长度字段解释错误会让 JSON 被截断，继续尝试下一种长度解释
            continue
        fields, markers = _lsb_build_fields(fmt, candidate, text, obj, decompressed)
        _lsb_note(
            notes,
            "LSB 命中 %s：%s 通道 / %s / %s，字节偏移 %d，载荷 %d 字节%s"
            % (
                magic.decode("latin-1"),
                candidate["channel_name"],
                candidate["order_name"],
                _lsb_packing_text(candidate["packing"]),
                offset,
                payload_length,
                "（已解压）" if decompressed else "",
            ),
        )
        return fields, markers
    _lsb_note(
        notes,
        "%s 载荷解码失败（长度字段=%d，已尝试 %d 种解释）"
        % (what, length_value, len(attempts)),
    )
    return None


def _lsb_decode_json_hint(buffer, width, height, candidate, fmt, notes):
    """magic 未命中时，尝试把裸 JSON 提示处的 LSB 数据按 JSON 解析。"""
    channels = candidate["channels"]
    total_bytes = (width * height * channels) // 8
    byte_count = min(MAX_LSB_JSON_SCAN, total_bytes - candidate["offset"])
    if byte_count <= 0:
        return None
    payload = _lsb_read_bytes(
        buffer,
        width,
        height,
        channels,
        candidate["row_major"],
        candidate["packing"],
        candidate["offset"] * 8,
        byte_count,
    )
    if not payload:
        return None
    text = _decode_text_bytes(payload.rstrip(b"\x00"), ("utf-8", "latin-1"))
    if not text:
        return None
    obj = _lsb_try_json_text(text)
    if not isinstance(obj, dict):
        return None
    flat = _lsb_flatten_json(obj)
    required = _LSB_PROMPT_KEYS + _LSB_STEPS_KEYS + ("parameters", "uc")
    if not any(key in flat for key in required):
        return None
    raw_candidate = dict(candidate)
    raw_candidate["magic"] = b"raw_json"
    fields, markers = _lsb_build_fields(fmt, raw_candidate, text, obj, False)
    _lsb_note(
        notes,
        "LSB 未识别 stealth magic，按裸 JSON 兜底提取（%s 通道 / %s / %s，偏移 %d）"
        % (
            candidate["channel_name"],
            candidate["order_name"],
            _lsb_packing_text(candidate["packing"]),
            candidate["offset"],
        ),
    )
    return fields, markers


def _lsb_deep_scan(data, fmt, notes):
    """对 PNG/WebP 做 LSB/Alpha 隐写深扫，返回 (raw_fields, extra_markers)。"""
    fields = []
    markers = []
    if _PILImage is None:
        _lsb_note(notes, "未安装 Pillow，跳过 LSB/Alpha 隐写深扫（安装 Pillow 后自动启用）")
        return fields, markers
    opened = _lsb_open(data, fmt, notes)
    if opened is None:
        return fields, markers
    width, height, buffer = opened
    _lsb_note(notes, "已执行 LSB/Alpha 隐写深扫（%s %dx%d）" % (fmt.upper(), width, height))
    if fmt == "webp":
        _lsb_note(notes, "WebP 为有损编码时 LSB 会被破坏；仅无损 WebP 可稳定检出 LSB 隐写")

    modes = _lsb_order_modes(buffer, width, height)
    magic_candidates = _lsb_magic_candidates(buffer, width, height, modes)
    handled_modes = set()
    attempts = 0
    for candidate in magic_candidates:
        if candidate["channels"] in handled_modes:
            continue
        if attempts >= MAX_LSB_ATTEMPTS:
            _lsb_note(notes, "LSB 候选较多，只尝试了前 %d 个" % MAX_LSB_ATTEMPTS)
            break
        attempts += 1
        hit = _lsb_decode_candidate(buffer, width, height, candidate, fmt, notes)
        if hit is None:
            continue
        handled_modes.add(candidate["channels"])
        fields.extend(hit[0])
        for marker in hit[1]:
            if marker not in markers:
                markers.append(marker)

    if not fields:
        for candidate in _lsb_json_candidates(buffer, width, height, modes):
            if attempts >= MAX_LSB_ATTEMPTS:
                break
            attempts += 1
            hit = _lsb_decode_json_hint(buffer, width, height, candidate, fmt, notes)
            if hit is None:
                continue
            handled_modes.add(candidate["channels"])
            fields.extend(hit[0])
            for marker in hit[1]:
                if marker not in markers:
                    markers.append(marker)
            break

    if not fields:
        if magic_candidates:
            _lsb_note(
                notes,
                "检测到 LSB stealth magic 候选，但载荷解码失败（可能被截断或格式变体不支持）",
            )
        else:
            _lsb_note(
                notes,
                "前 %d 字节 LSB 未发现 stealth_* magic，也未命中裸 JSON 提示"
                % LSB_PREFIX_BYTES,
            )
    return fields, markers


# --------------------------------------------------------------------------- #
# 结果组装
# --------------------------------------------------------------------------- #

def _error_result(path, fmt, error, notes=None):
    path_text = path if isinstance(path, str) else ""
    return {
        "ok": False,
        "path": path_text,
        "format": fmt,
        "has_metadata": False,
        "generation_markers": [],
        "fields": {},
        "field_count": 0,
        "evidence": "",
        "notes": list(notes or []),
        "error": str(error),
    }


def _build_result(path, fmt, raw_fields, notes, scan_strings, extra_markers=None):
    """把解析出的原始字段整理成对外结构，并做 AI 残留判定。"""
    fields = {}
    labels = {}
    full_texts = {}
    for item in raw_fields:
        if not isinstance(item, (tuple, list)) or len(item) != 3:
            continue
        key, label, value = item
        text = _clean_text(value)
        if not text:
            continue
        if len(fields) >= MAX_FIELDS:
            notes.append("字段数超过 %d，已忽略其余字段" % MAX_FIELDS)
            break
        unique_key = str(key) if key else "field"
        suffix = 2
        while unique_key in fields:
            unique_key = "%s:%d" % (key, suffix)
            suffix += 1
        fields[unique_key] = text[:MAX_FIELD_CHARS]
        labels[unique_key] = str(label) if label else ""
        full_texts[unique_key] = text[:MAX_ANALYZE_CHARS]

    markers = []
    seen_markers = set()

    def add_marker(marker):
        marker = _clean_text(str(marker), 120)
        if marker and marker not in seen_markers:
            seen_markers.add(marker)
            markers.append(marker)

    # 深扫等外部逻辑确认过的标记（如 lsb / stealth_pngcomp）优先写入
    for marker in extra_markers or ():
        add_marker(marker)

    strong_evidence = ""
    evidence_candidates = []  # (优先级, 文本长度, 文本)
    for key, label in labels.items():
        text = full_texts.get(key, "")
        hits = _markers_for_text(text)
        for hit in hits:
            add_marker(hit)
        norm_label = _norm_label(label)
        if norm_label in _RESIDUAL_KEYS:
            add_marker("key:%s" % norm_label)
            evidence_candidates.append((2 if hits else 1, len(text), text))
        if norm_label == "software":
            software_value = _clean_text(text, 60)
            if software_value:
                add_marker("software:%s" % software_value)
        if hits:
            strong_evidence = strong_evidence or text

    # printable 兜底扫描：只补 fields 里没有的线索
    scan_evidence = ""
    scan_examples = []
    scan_hit = False
    for scanned in scan_strings:
        text = _clean_text(scanned)
        if len(text) < 6:
            continue
        hits = _markers_for_text(text)
        if not hits:
            continue
        scan_hit = True
        for hit in hits:
            add_marker(hit)
        if not scan_evidence:
            scan_evidence = text
        if len(scan_examples) < 5 and text not in scan_examples:
            scan_examples.append(text)

    if scan_hit and not strong_evidence and not evidence_candidates:
        joined = _clean_text(" | ".join(scan_examples), MAX_FIELD_CHARS)
        if joined:
            fields["scan:matched_strings"] = joined
            labels["scan:matched_strings"] = "scan"

    if evidence_candidates:
        evidence = max(evidence_candidates, key=lambda item: (item[0], item[1]))[2]
    else:
        evidence = scan_evidence
    evidence = _clean_text(evidence, MAX_EVIDENCE_CHARS)
    has_metadata = bool(markers)

    return {
        "ok": True,
        "path": path,
        "format": fmt,
        "has_metadata": has_metadata,
        "generation_markers": markers,
        "fields": fields,
        "field_count": len(fields),
        "evidence": evidence,
        "notes": notes,
    }


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #

def _detect_format(head):
    if head.startswith(PNG_SIG):
        return "png"
    if head[:2] == b"\xff\xd8":
        return "jpeg"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return "unknown"


def _inspect(path):
    if not isinstance(path, (str, bytes, os.PathLike)):
        return _error_result("", "unknown", "path 参数必须是 str 或 os.PathLike")

    try:
        absolute = os.path.abspath(os.fspath(path))
    except Exception as exc:
        return _error_result("", "unknown", "无法解析路径: %r" % (exc,))
    if isinstance(absolute, bytes):
        absolute = os.fsdecode(absolute)

    try:
        file_stat = os.stat(absolute)
    except FileNotFoundError:
        return _error_result(absolute, "unknown", "文件不存在")
    except OSError as exc:
        return _error_result(absolute, "unknown", "无法访问文件: %s" % exc)

    if not stat.S_ISREG(file_stat.st_mode):
        return _error_result(absolute, "unknown", "不是普通文件")
    if file_stat.st_size == 0:
        return _error_result(absolute, "unknown", "空文件")
    if file_stat.st_size > MAX_FILE_BYTES:
        return _error_result(
            absolute,
            "unknown",
            "文件过大（%d 字节，上限 %d 字节）"
            % (file_stat.st_size, MAX_FILE_BYTES),
        )

    try:
        with open(absolute, "rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        return _error_result(absolute, "unknown", "读取文件失败: %s" % exc)

    fmt = _detect_format(data[:16])
    if fmt == "unknown":
        return _error_result(absolute, "unknown", "无法识别的图片格式")

    notes = []
    try:
        if fmt == "png":
            raw_fields = _parse_png(data, notes)
        elif fmt == "jpeg":
            raw_fields = _parse_jpeg(data, notes)
        elif fmt == "webp":
            raw_fields = _parse_webp(data, notes)
        else:
            raw_fields = _parse_gif(data, notes)
    except Exception as exc:  # pragma: no cover - 兜底，理论上不应触发
        return _error_result(absolute, fmt, "%s 解析失败: %r" % (fmt, exc), notes)

    scan_strings, scan_notes = _scan_printable(data)
    notes.extend(scan_notes)

    # PNG / WebP 追加 LSB/Alpha 隐写深扫（Pillow 缺失时自动降级为仅记录 note）
    extra_markers = []
    if fmt in ("png", "webp"):
        try:
            deep_fields, deep_markers = _lsb_deep_scan(data, fmt, notes)
        except Exception as exc:  # pragma: no cover - 深扫失败不影响文本块结果
            notes.append("LSB 深扫异常，已跳过: %r" % (exc,))
        else:
            raw_fields.extend(deep_fields)
            extra_markers.extend(deep_markers)

    return _build_result(
        absolute, fmt, raw_fields, notes, scan_strings, extra_markers
    )


def inspect_image(path):
    """检查一张图片的文本元数据与 AI 生成残留。

    参数:
        path: 图片路径（str / bytes / os.PathLike）。

    返回:
        dict，JSON 可序列化。``ok`` 为 False 时一定带有 ``error`` 字段；
        其他情况下结构见模块文档 / 项目说明。本函数不会抛出异常。
    """
    try:
        return _inspect(path)
    except Exception as exc:  # pragma: no cover - 最后一道防线
        return _error_result("", "unknown", "内部错误: %r" % (exc,))


if __name__ == "__main__":  # 简易命令行自测
    import sys

    targets = sys.argv[1:]
    if not targets:
        targets = ["."]
    for target in targets:
        print(json.dumps(inspect_image(target), ensure_ascii=False, indent=2))
