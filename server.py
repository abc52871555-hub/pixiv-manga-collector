#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pixiv 漫画采集器 —— 单文件后端服务（Python 3.10+ / 仅标准库 + requests）

功能：
  * Pixiv OAuth refresh_token 登录，access_token 过期自动续期
  * 标签搜索预览 / 按作品 ID 找相似画风（加权打分）
  * 异步下载任务：作品级并发、作品内页串行、实时速度与 ETA
  * 缩略图防盗链代理（浏览器 <img> 无法直连 pximg）
  * 静态托管 web/ 目录（/ → index.html）

启动方式：
  python server.py [--port 8765] [--key-file 路径] [--open]

注意：本文件不依赖 Web 框架，双击 bat / 命令行均可启动。
"""

from __future__ import annotations

import argparse
import base64
import collections
import csv
import glob
import hashlib
import importlib.util
import io
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import uuid
import webbrowser
from collections import OrderedDict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

try:
    from metadata_inspect import inspect_image as _inspect_image
except Exception:  # noqa: BLE001 - 元数据模块缺失时仍可运行其他功能
    _inspect_image = None

# ---------------------------------------------------------------------------
# 常量与路径
# ---------------------------------------------------------------------------

APP_NAME = "Pixiv 漫画采集器"
APP_VERSION = "1.1.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
KEY_FILE_IN_DIR = os.path.join(BASE_DIR, "pixiv_通行密钥.json")
CONFIG_FILE_IN_DIR = os.path.join(BASE_DIR, "config.json")
SETTINGS_FILE_IN_DIR = os.path.join(BASE_DIR, "settings.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DESKTOP_KEY_PATH = os.path.join(
    os.path.expanduser("~"), "Desktop", "api", "pixiv_通行密钥.json"
)

DEFAULT_SETTINGS = {
    "proxy_mode": "system",          # system | direct | custom
    "proxy_url": "",
    "api_min_interval": 0.35,
    "download_timeout": 25,
    "scan_batch_size": 10,
    "scan_max_batches": 0,           # 0 = 不限
    "scan_max_disk_gb": 0,           # 0 = 不限
    "notify_hits": True,
    "history_limit": 30,
}

# OAuth（Android App 客户端凭据；client_id 少一个字符都会 403/918）
OAUTH_URL = "https://oauth.secure.pixiv.net/auth/token"
CLIENT_ID = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"
APP_UA = "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)"
OAUTH_HEADERS = {
    "User-Agent": APP_UA,
    "App-OS": "android",
    "App-OS-Version": "11",
    "App-Version": "5.0.234",
    "Referer": "https://app-api.pixiv.net/",
    "Content-Type": "application/x-www-form-urlencoded",
}

API_BASE = "https://app-api.pixiv.net"
API_REFERER = "https://app-api.pixiv.net/"
ACCEPT_LANGUAGE = "zh-CN,zh;q=0.9"
IMG_HEADERS = {"Referer": API_REFERER, "User-Agent": APP_UA}

# 缩略图代理允许的图床域名
THUMB_ALLOWED_HOSTS = {"i.pximg.net", "i-cf.pximg.net"}

# 预览阶段 API 调用上限（防止网络异常时卡死）
MAX_PREVIEW_CALLS = 40

# 通用标签黑名单（相似模式抽取种子标签时过滤）
GENERIC_TAGS = {
    "イラスト", "オリジナル", "漫画", "插画", "原创", "原创插画",
    "r-18", "r18", "r-18g", "r18g", "女の子", "男の子", "女の子一人",
    "男の子一人", "ai生成", "ai", "aiイラスト", "ai-generated", "ai生成イラスト",
    "健全", "全年齢", "pixiv", "ファンボックス", "fANBOX", "fanbox",
    "マンガ", "アニメ", "キャラクター", "落書き", "らくがき", "イラスト本",
    "オリジナルイラスト", "女の子向け", "男の子向け", "講座",
    # 作画工具/软件标签，和画风无关
    "クリスタ", "clip studio", "clipstudio", "clip studio paint", "クリップスタジオ",
    "sai", "photoshop", "illustrator", "procreate", "medibang", "アイビス",
    "ibis paint", "アナログ", "デジタル", "マンガ制作", "作画",
}
# 画风类关键词（命中就加权重，鼓励“像画风”的标签）
STYLE_KEYWORDS = (
    "画風", "塗り", "水彩", "厚塗り", "線画", "アニメ調", "セル", "ちび",
    "デフォルメ", "タッチ", "彩色", "モノクロ",
)

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".map": "application/json; charset=utf-8",
}

EXT_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
}


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def _int(value, default=0):
    """尽量把值转成 int，失败返回 default。"""
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value, default=False):
    """把前端传来的 true/false/"1"/"0" 等统一成 bool。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "yes", "on"):
            return True
        if v in ("0", "false", "no", "off", ""):
            return False
    return default


def _clamp_int(value, lo, hi, default):
    return max(lo, min(hi, _int(value, default)))


def _snake(name):
    """camelCase → snake_case"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", str(name)).lower()


def _camel(name):
    """snake_case → camelCase"""
    parts = str(name).split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def get(data, *names, default=None):
    """
    兼容取值：同时支持 snake_case 与 camelCase 字段名。
    例：get(illust, "page_count", "pageCount", default=1)
    """
    if not isinstance(data, dict):
        return default
    for name in names:
        for key in (name, _snake(name), _camel(name)):
            if key in data and data[key] is not None:
                return data[key]
    return default


def format_bytes(num):
    """人类可读字节数（仅用于日志展示）。"""
    n = float(num or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(n)}B"
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"


def now_ms():
    return int(time.time() * 1000)


def safe_print(*args, **kwargs):
    """控制台输出兜底：忽略编码错误，避免中文标题把进程打崩；同时写入日志文件。"""
    text = " ".join(str(arg) for arg in args)
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            sys.stdout.write(text.encode(sys.stdout.encoding or "utf-8", "replace").decode(
                sys.stdout.encoding or "utf-8", "replace") + "\n")
            sys.stdout.flush()
        except Exception:
            pass
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "app.log"), "a", encoding="utf-8") as handle:
            handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 标题 / 文件名 / 扩展名
# ---------------------------------------------------------------------------

_INVALID_NAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_title(title):
    """生成 Windows 合法目录名片段：替换非法字符、去尾部点与空格、长度 ≤70。"""
    text = _INVALID_NAME_CHARS.sub("_", str(title or ""))
    text = re.sub(r"\s+", " ", text).strip()
    text = text.rstrip(". ")
    if not text:
        text = "untitled"
    text = text[:70].rstrip(". ") or "untitled"
    return text


def guess_ext(content_type, url):
    """按 Content-Type 猜扩展名，回退到 URL 后缀，再回退 .jpg。"""
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype in EXT_BY_CONTENT_TYPE:
        return EXT_BY_CONTENT_TYPE[ctype]
    path = urllib.parse.urlsplit(url or "").path
    ext = os.path.splitext(path)[1].lower()
    if ext == ".jpeg":
        return ".jpg"
    if ext in (".jpg", ".png", ".webp", ".gif", ".avif"):
        return ext
    return ".jpg"


def find_work_dir(work_id):
    """在 output 下查找 {id}_标题 目录；找不到返回 None。"""
    prefix = f"{work_id}_"
    try:
        with os.scandir(OUTPUT_DIR) as it:
            for entry in it:
                if entry.is_dir() and entry.name.startswith(prefix):
                    return entry.path
    except OSError:
        pass
    return None


def count_page_files(directory, work_id):
    """统计目录中已下载的页文件数量（{id}_pNN.*，排除 .part）。"""
    if not directory or not os.path.isdir(directory):
        return 0
    prefix = f"{work_id}_p"
    count = 0
    try:
        for name in os.listdir(directory):
            if name.startswith(prefix) and not name.endswith(".part"):
                count += 1
    except OSError:
        pass
    return count


def scan_downloaded_ids():
    """扫描 output 下所有已存在的作品 id（目录名形如 123456_标题）。"""
    ids = set()
    try:
        with os.scandir(OUTPUT_DIR) as it:
            for entry in it:
                if not entry.is_dir():
                    continue
                m = re.match(r"^(\d+)_", entry.name)
                if m:
                    ids.add(int(m.group(1)))
    except OSError:
        pass
    return ids


def _silent_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 密钥文件
# ---------------------------------------------------------------------------

def read_key_file(path):
    """读取密钥文件，容忍 BOM / 字段差异。返回 {refresh_token, account}。"""
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except Exception as exc:  # noqa: BLE001 - 读文件失败不应崩溃
        safe_print(f"[警告] 读取密钥文件失败：{path}（{exc}）")
        return {}
    if not isinstance(data, dict):
        return {}
    token = str(data.get("refresh_token") or data.get("refreshToken") or "").strip()
    account = str(data.get("account") or data.get("user") or "").strip()
    return {"refresh_token": token, "account": account}


def save_key_file(token, account=""):
    """把 refresh_token 写入程序目录密钥文件（仅在 remember=true 时调用）。"""
    path = KEY_FILE_IN_DIR
    data = {"account": account or "", "refresh_token": token or ""}
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError as exc:
        _silent_remove(tmp)
        safe_print(f"[警告] 写入密钥文件失败：{path}（{exc}）")
        return None
    STATE.key_path = path
    STATE.key_data = data
    safe_print(f"[密钥] 已保存到 {path}")
    return path


# ---------------------------------------------------------------------------
# Pixiv 客户端：OAuth + 全局限速 + 重试
# ---------------------------------------------------------------------------

class PixivError(Exception):
    """Pixiv 接口错误（status 用于映射 HTTP 状态码）。"""

    def __init__(self, message, status=0):
        super().__init__(message)
        self.message = message
        self.status = status


class BudgetExceeded(Exception):
    """预览 API 调用预算耗尽。"""


class ApiBudget:
    """一次预览请求内允许的最大 API 调用次数。"""

    def __init__(self, limit=MAX_PREVIEW_CALLS):
        self.limit = limit
        self.used = 0
        self.lock = threading.Lock()

    def take(self):
        with self.lock:
            if self.used >= self.limit:
                raise BudgetExceeded()
            self.used += 1

    def left(self):
        with self.lock:
            return max(0, self.limit - self.used)


def _extract_error(resp):
    """从错误响应里提取可读信息。"""
    try:
        payload = resp.json()
    except ValueError:
        return (resp.text or "").strip()[:300] or "未知错误"
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err.get("reason") or err.get("user_message") or err)
        if isinstance(err, str) and err:
            return err
        for key in ("message", "detail", "error_description"):
            if payload.get(key):
                return str(payload[key])
        return json.dumps(payload, ensure_ascii=False)[:300]
    return str(payload)[:300]


def normalize_user(user):
    """统一用户信息结构（id / name / account / avatar_url）。"""
    user = user or {}
    images = get(user, "profile_image_urls", "profileImageUrls", default={}) or {}
    if not isinstance(images, dict):
        images = {}
    return {
        "id": _int(get(user, "id", default=0)),
        "name": str(get(user, "name", default="") or ""),
        "account": str(get(user, "account", default="") or ""),
        "avatar_url": str(images.get("px_170x170") or images.get("px_50x50") or ""),
    }


class PixivClient:
    """封装 OAuth 会话、全局限速与 429/5xx 退避重试。"""

    def __init__(self):
        self.session = requests.Session()
        self._lock = threading.RLock()
        self.access_token = ""
        self.refresh_token = ""
        self.user = None
        self.expires_at = 0.0          # access_token 过期时间（time.time() 秒级基准）
        self.min_interval = 0.35       # 全局串行最小间隔（秒）
        self._last_request = 0.0
        self.calls = 0                 # 实际发出的 HTTP 次数（统计用）

    # -- 基础 --------------------------------------------------------------

    def _api_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": APP_UA,
            "Referer": API_REFERER,
            "Accept-Language": ACCEPT_LANGUAGE,
        }

    def _throttle(self):
        """全局限速：任意两个请求之间至少间隔 min_interval 秒。"""
        with self._lock:
            now = time.monotonic()
            wait = self.min_interval - (now - self._last_request)
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._last_request = now
            self.calls += 1

    # -- 登录 --------------------------------------------------------------

    def _oauth_refresh_locked(self, refresh_token):
        """调用 OAuth 刷新 access_token（调用方需持有 self._lock）。"""
        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "include_policy": "true",
            "refresh_token": refresh_token,
            "get_secure_url": "1",
        }
        self._throttle()
        try:
            resp = self.session.post(OAUTH_URL, data=payload, headers=OAUTH_HEADERS, timeout=30)
        except requests.RequestException as exc:
            raise PixivError(f"网络错误，无法连接 Pixiv 登录接口：{exc}", 502) from exc

        if resp.status_code == 200:
            try:
                body = resp.json()
            except ValueError as exc:
                raise PixivError("登录接口返回了非 JSON 内容", 502) from exc
            root = body.get("response") if isinstance(body.get("response"), dict) else body
            token = str(root.get("access_token") or body.get("access_token") or "")
            if not token:
                raise PixivError("登录失败：响应中没有 access_token", 502)
            self.access_token = token
            # 服务端可能轮换 refresh_token：仅更新内存，不自动覆盖用户文件
            new_refresh = str(root.get("refresh_token") or body.get("refresh_token") or "")
            if new_refresh:
                self.refresh_token = new_refresh
            self.expires_at = time.time() + _int(root.get("expires_in"), 3600)
            self.user = normalize_user(root.get("user") or body.get("user") or {})
            return self.user

        message = _extract_error(resp)
        if resp.status_code in (429, 500, 502, 503, 504):
            raise PixivError(f"Pixiv 登录接口暂时不可用（HTTP {resp.status_code}）：{message}", 502)
        raise PixivError(f"登录失败：{message or f'HTTP {resp.status_code}'}", 401)

    def login(self, refresh_token=None):
        """强制使用给定 token（或当前 token）刷新登录。

        登录失败时回滚会话状态，避免“填错 token 把已连接会话弄坏”。
        """
        with self._lock:
            token = (refresh_token or self.refresh_token or "").strip()
            if not token:
                raise PixivError("尚未设置 refresh_token，请先连接 Pixiv", 401)
            old_state = (self.refresh_token, self.access_token, self.user, self.expires_at)
            self.refresh_token = token
            try:
                return self._oauth_refresh_locked(token)
            except Exception:
                self.refresh_token, self.access_token, self.user, self.expires_at = old_state
                raise

    def ensure_token(self):
        """确保 access_token 有效，过期则自动刷新。"""
        with self._lock:
            if self.access_token and time.time() < (self.expires_at - 120):
                return
            if not self.refresh_token:
                raise PixivError("尚未设置 refresh_token，请先连接 Pixiv", 401)
            self._oauth_refresh_locked(self.refresh_token)

    # -- 业务请求 ----------------------------------------------------------

    def api_get(self, url, params=None, budget=None, timeout=30):
        """带限速 / 重试 / 自动续期的 GET，返回解析后的 JSON。"""
        if budget is not None:
            budget.take()
        if not str(url).startswith("http"):
            url = API_BASE + str(url)

        last_error = ""
        for attempt in range(4):  # 首次 + 最多 3 次重试
            self.ensure_token()
            self._throttle()
            try:
                resp = self.session.get(url, params=params, headers=self._api_headers(), timeout=timeout)
            except requests.RequestException as exc:
                last_error = f"网络错误：{exc}"
                if attempt < 3:
                    time.sleep(0.8 * (2 ** attempt))
                    continue
                raise PixivError(last_error, 502) from exc

            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise PixivError("接口返回了非 JSON 内容", 502) from exc

            if resp.status_code == 401 and attempt == 0:
                # token 提前失效：清空后强制刷新再试一次
                with self._lock:
                    self.access_token = ""
                continue

            message = _extract_error(resp)
            last_error = f"HTTP {resp.status_code}：{message}"
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(0.8 * (2 ** attempt))
                continue
            raise PixivError(last_error, resp.status_code if resp.status_code >= 400 else 502)

        raise PixivError(last_error or "请求失败", 502)

    # -- 具体接口 ----------------------------------------------------------

    def search_illust(self, word, sort="date_desc", budget=None, page_url=None):
        """搜索插画/漫画。page_url 用于翻页（直接 GET 返回的 next_url）。"""
        if page_url:
            return self.api_get(page_url, budget=budget)
        params = {
            "word": word,
            "search_target": "partial_match_for_tags",
            "sort": sort,
            "filter": "for_android",
        }
        return self.api_get("/v1/search/illust", params=params, budget=budget)

    def illust_detail(self, illust_id, budget=None):
        """作品详情（含 meta_pages / meta_single_page）。"""
        data = self.api_get("/v1/illust/detail", params={"illust_id": int(illust_id)}, budget=budget)
        if isinstance(data, dict) and isinstance(data.get("illust"), dict):
            return data["illust"]
        return data

    def illust_related(self, illust_id, budget=None):
        """相关推荐（v1 已失效，必须用 v2）。"""
        return self.api_get(
            "/v2/illust/related",
            params={"illust_id": int(illust_id), "filter": "for_android"},
            budget=budget,
        )


# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------

class AppState:
    def __init__(self):
        self.client = PixivClient()
        self.output_dir = OUTPUT_DIR
        self.key_path = ""
        self.key_data = {}
        self.jobs = {}
        self.jobs_lock = threading.RLock()
        self.active_job = None
        self.scans = {}
        self.scans_lock = threading.RLock()
        self.active_scan = None
        self.scan_root = os.path.join(OUTPUT_DIR, "AI元数据扫描")
        self.pkce_sessions = {}
        self.pkce_lock = threading.RLock()
        self.settings = dict(DEFAULT_SETTINGS)
        self.api_token = secrets.token_urlsafe(24)
        self.thumb_session = requests.Session()
        self.speedtest_url = ""
        self.auto_logins = {}
        self.auto_login_lock = threading.RLock()
        self.auto_login_proc = None
        self.related_sessions = {}
        self.related_lock = threading.RLock()


STATE = AppState()


# ---------------------------------------------------------------------------
# 设置 / 代理 / HTTP 会话
# ---------------------------------------------------------------------------

def normalize_settings(payload):
    """把任意输入收敛成合法的设置字典。"""
    result = dict(DEFAULT_SETTINGS)
    if not isinstance(payload, dict):
        return result
    mode = str(payload.get("proxy_mode") or "system").lower()
    result["proxy_mode"] = mode if mode in ("system", "direct", "custom") else "system"
    result["proxy_url"] = str(payload.get("proxy_url") or "").strip()[:300]
    try:
        result["api_min_interval"] = max(0.0, min(5.0, float(payload.get("api_min_interval", 0.35))))
    except (TypeError, ValueError):
        pass
    try:
        result["download_timeout"] = max(5, min(180, int(payload.get("download_timeout", 25))))
    except (TypeError, ValueError):
        pass
    try:
        result["scan_batch_size"] = max(1, min(50, int(payload.get("scan_batch_size", 10))))
    except (TypeError, ValueError):
        pass
    try:
        result["scan_max_batches"] = max(0, min(1000, int(payload.get("scan_max_batches", 0))))
    except (TypeError, ValueError):
        pass
    try:
        result["scan_max_disk_gb"] = max(0.0, min(1000.0, float(payload.get("scan_max_disk_gb", 0))))
    except (TypeError, ValueError):
        pass
    result["notify_hits"] = bool(payload.get("notify_hits", True))
    try:
        result["history_limit"] = max(5, min(200, int(payload.get("history_limit", 30))))
    except (TypeError, ValueError):
        pass
    return result


def load_settings():
    data = dict(DEFAULT_SETTINGS)
    try:
        if os.path.isfile(SETTINGS_FILE_IN_DIR):
            with open(SETTINGS_FILE_IN_DIR, encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                data.update(raw)
    except (OSError, ValueError):
        pass
    return normalize_settings(data)


def save_settings(settings):
    path = SETTINGS_FILE_IN_DIR
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError as exc:
        _silent_remove(tmp)
        raise PixivError(f"保存设置失败：{exc}", 500) from exc


def apply_session_network(session, mode=None, proxy_url=None):
    """按设置给 requests.Session 应用系统代理 / 直连 / 自定义代理。"""
    settings = getattr(STATE, "settings", None) or DEFAULT_SETTINGS
    mode = (mode or settings.get("proxy_mode") or "system").lower()
    proxy_url = (proxy_url if proxy_url is not None else settings.get("proxy_url") or "").strip()
    if mode == "direct":
        session.trust_env = False
        session.proxies = {}
    elif mode == "custom" and proxy_url:
        session.trust_env = False
        session.proxies = {"http": proxy_url, "https": proxy_url}
    else:
        session.trust_env = True
        session.proxies = {}
    return session


def build_http_session(mode=None, proxy_url=None):
    session = requests.Session()
    return apply_session_network(session, mode, proxy_url)


def apply_current_network():
    apply_session_network(STATE.client.session)
    apply_session_network(STATE.thumb_session)
    STATE.client.min_interval = float(STATE.settings.get("api_min_interval") or 0.35)


def settings_snapshot():
    return dict(STATE.settings)


def api_get_settings():
    return {
        "ok": True,
        "settings": settings_snapshot(),
        "output_dir": STATE.output_dir,
        "log_file": os.path.join(LOG_DIR, "app.log"),
        "version": APP_VERSION,
    }


def api_save_settings(payload):
    merged = dict(STATE.settings)
    merged.update(payload if isinstance(payload, dict) else {})
    settings = normalize_settings(merged)
    save_settings(settings)
    STATE.settings = settings
    apply_current_network()
    safe_print(f"[设置] 已保存：代理={settings['proxy_mode']}，下载超时={settings['download_timeout']}s，每批={settings['scan_batch_size']}")
    return {"ok": True, "settings": settings_snapshot()}


# ---------------------------------------------------------------------------
# 线路测试
# ---------------------------------------------------------------------------

def _speedtest_target_url():
    if STATE.speedtest_url:
        return STATE.speedtest_url
    try:
        STATE.client.ensure_token()
        data = STATE.client.search_illust("初音ミク", sort="date_desc")
        for illust in get(data, "illusts", default=[]) or []:
            images = get(illust, "image_urls", "imageUrls", default={}) or {}
            url = images.get("large") or images.get("medium") or ""
            if url:
                STATE.speedtest_url = str(url)
                return STATE.speedtest_url
    except Exception:  # noqa: BLE001 - 测速不应因 API 失败中断
        pass
    return "https://www.pixiv.net/favicon.ico"


def _friendly_net_error(exc):
    text = str(exc or "")
    low = text.lower()
    if "prox" in low:
        return "代理连接失败"
    if "timed out" in low or "timeout" in low:
        return "连接超时（可能被屏蔽或线路不通）"
    if "ssl" in low or "certificate" in low:
        return "TLS / 证书错误"
    if "name or service not known" in low or "getaddrinfo" in low or "nodename" in low:
        return "DNS 解析失败"
    if "connection refused" in low:
        return "连接被拒绝"
    if "connection reset" in low or "aborted" in low:
        return "连接被重置"
    return "网络连接失败"


def _measure_http(session, url, headers=None, max_bytes=2 * 1024 * 1024, max_seconds=3.0):
    """测一次 HTTP：返回延迟、首字节、下载速度。"""
    started = time.monotonic()
    first_byte_ms = None
    total = 0
    try:
        response = session.get(url, headers=headers or {}, timeout=(6, 10), stream=True)
    except requests.RequestException as exc:
        return {"ok": False, "error": _friendly_net_error(exc), "latency_ms": None,
                "first_byte_ms": None, "speed_bps": 0.0, "bytes": 0, "status": None}
    try:
        if response.status_code >= 400:
            return {"ok": False, "error": f"HTTP {response.status_code}", "latency_ms": None,
                    "first_byte_ms": None, "speed_bps": 0.0, "bytes": 0,
                    "status": response.status_code}
        for chunk in response.iter_content(chunk_size=32768):
            if first_byte_ms is None:
                first_byte_ms = round((time.monotonic() - started) * 1000, 1)
            if not chunk:
                continue
            total += len(chunk)
            if total >= max_bytes or (time.monotonic() - started) >= max_seconds:
                break
        elapsed = max(0.001, time.monotonic() - started)
        return {
            "ok": total > 0,
            "error": None,
            "latency_ms": first_byte_ms,
            "first_byte_ms": first_byte_ms,
            "speed_bps": round(total / elapsed, 1),
            "bytes": total,
            "status": response.status_code,
            "elapsed_ms": round(elapsed * 1000, 1),
        }
    finally:
        try:
            response.close()
        except Exception:  # noqa: BLE001
            pass


def api_network_speedtest(payload):
    target = _speedtest_target_url()
    settings = STATE.settings
    override_mode = str(payload.get("proxy_mode") or "").strip().lower()
    override_url = str(payload.get("proxy_url") or "").strip()
    current_mode = override_mode if override_mode in ("system", "direct", "custom") else (settings.get("proxy_mode") or "system")
    current_proxy = override_url if override_mode == "custom" else (settings.get("proxy_url") or "")
    if override_mode not in ("system", "direct", "custom"):
        current_proxy = settings.get("proxy_url") or ""
    results = {}
    configs = {
        "direct": ("direct", ""),
        "current": (current_mode, current_proxy),
    }
    for key, (mode, proxy_url) in configs.items():
        session = build_http_session(mode, proxy_url)
        try:
            api_probe = _measure_http(session, API_BASE, headers=IMG_HEADERS, max_bytes=64 * 1024, max_seconds=2.0)
            download = _measure_http(session, target, headers=IMG_HEADERS)
            results[key] = {
                "mode": mode,
                "proxy_url": proxy_url if mode == "custom" else "",
                "latency_ms": api_probe.get("latency_ms"),
                "api_ok": bool(api_probe.get("ok")),
                "api_error": api_probe.get("error"),
                "speed_bps": download.get("speed_bps") or 0,
                "first_byte_ms": download.get("first_byte_ms"),
                "bytes": download.get("bytes") or 0,
                "ok": bool(download.get("ok")),
                "error": download.get("error"),
            }
        finally:
            session.close()
    return {"ok": True, "target": target, "settings": {"proxy_mode": settings.get("proxy_mode")}, "results": results}



def illust_tags(illust):
    """提取标签名列表。"""
    names = []
    for tag in get(illust, "tags", default=[]) or []:
        name = str(get(tag, "name", default="") or "").strip()
        if name:
            names.append(name)
    return names


def illust_tag_pairs(illust):
    """提取 [{name, translated_name}] 结构（写入 info.json 用）。"""
    pairs = []
    for tag in get(illust, "tags", default=[]) or []:
        name = str(get(tag, "name", default="") or "").strip()
        if not name:
            continue
        pairs.append({
            "name": name,
            "translated_name": str(get(tag, "translated_name", "translatedName", default="") or ""),
        })
    return pairs


def illust_author(illust):
    user = get(illust, "user", default={}) or {}
    if not isinstance(user, dict):
        user = {}
    return {
        "id": _int(get(user, "id", default=0)),
        "name": str(get(user, "name", default="") or ""),
        "account": str(get(user, "account", default="") or ""),
    }


def illust_thumb_url(illust):
    """取中等尺寸图用于列表缩略图，再包一层防盗链代理。"""
    images = get(illust, "image_urls", "imageUrls", default={}) or {}
    if not isinstance(images, dict):
        images = {}
    url = images.get("medium") or images.get("large") or images.get("square_medium") or ""
    if not url:
        return ""
    return "/api/thumb?u=" + urllib.parse.quote(str(url), safe="")


def build_item(illust, match_tags, score, downloaded_ids):
    """把 Pixiv 作品对象转成前端 Item 结构。"""
    work_id = _int(get(illust, "id", default=0))
    return {
        "id": work_id,
        "title": str(get(illust, "title", default="") or ""),
        "type": str(get(illust, "type", default="illust") or "illust"),
        "page_count": max(1, _int(get(illust, "page_count", "pageCount", default=1), 1)),
        "x_restrict": _int(get(illust, "x_restrict", "xRestrict", default=0)),
        "bookmarks": _int(get(illust, "total_bookmarks", "totalBookmarks", default=0)),
        "width": _int(get(illust, "width", default=0)),
        "height": _int(get(illust, "height", default=0)),
        "create_date": str(get(illust, "create_date", "createDate", default="") or ""),
        "tags": illust_tags(illust),
        "match_tags": list(match_tags or []),
        "score": round(max(0.0, min(1.0, float(score or 0.0))), 4),
        "author": illust_author(illust),
        "thumb_url": illust_thumb_url(illust),
        "already_downloaded": work_id in downloaded_ids,
    }


def build_pages(illust):
    """按顺序返回每页的 {original, fallback} 下载地址。"""
    pages = []
    meta_pages = get(illust, "meta_pages", "metaPages", default=[]) or []
    single = get(illust, "meta_single_page", "metaSinglePage", default={}) or {}
    if not isinstance(single, dict):
        single = {}
    images = get(illust, "image_urls", "imageUrls", default={}) or {}
    if not isinstance(images, dict):
        images = {}
    fallback_global = images.get("large") or images.get("medium") or ""

    if isinstance(meta_pages, list) and meta_pages:
        for entry in meta_pages:
            page_images = get(entry, "image_urls", "imageUrls", default={}) or {}
            if not isinstance(page_images, dict):
                page_images = {}
            original = page_images.get("original") or page_images.get("large") or ""
            fallback = page_images.get("large") or page_images.get("medium") or fallback_global
            if original:
                pages.append({"original": str(original), "fallback": str(fallback or "")})
    else:
        original = single.get("original_image_url") or single.get("originalImageUrl") or fallback_global
        if original:
            pages.append({"original": str(original), "fallback": str(fallback_global or "")})
    return pages


def passes_filters(illust, r18, work_type, min_bookmarks):
    """统一的预览过滤：R18 / 作品类型 / 最少收藏数。"""
    x_restrict = _int(get(illust, "x_restrict", "xRestrict", default=0))
    if not r18 and x_restrict > 0:
        return False
    illust_type = str(get(illust, "type", default="illust") or "illust").lower()
    tag_names = {str(t).strip().lower() for t in illust_tags(illust)}
    manga_like = (
        illust_type == "manga"
        or bool(tag_names & {"漫画", "マンガ", "manga", "4コマ", "4コマ漫画", "一コマ漫画"})
    )
    if work_type == "manga" and not manga_like:
        return False
    if work_type == "illust" and illust_type != "illust":
        return False
    bookmarks = _int(get(illust, "total_bookmarks", "totalBookmarks", default=0))
    if bookmarks < min_bookmarks:
        return False
    return True


# ---------------------------------------------------------------------------
# 请求参数解析
# ---------------------------------------------------------------------------

# AI 生成痕迹识别相关标签（用于判断作品是否 AI 作品）
AI_TAG_MARKERS = {
    "ai", "ai生成", "aiイラスト", "ai-generated", "aiart", "aigenerated",
    "ai画像", "ai创作", "ai創作", "生成ai", "aicg", "stable diffusion",
    "novelai", "midjourney", "comfyui", "pixai", "sd", "sdxl",
}
AI_SEARCH_SUFFIXES = ("AI生成", "AIイラスト")

# 元数据暴露情况的字段说明（用于扫描结果里的“暴露情况”描述）
EXPOSURE_KEY_LABELS = {
    "parameters": "生成参数（提示词/负面提示词/采样参数）",
    "prompt": "提示词或工作流数据",
    "workflow": "ComfyUI 工作流",
    "comment": "注释（常含 NovelAI 参数）",
    "sd-metadata": "Stable Diffusion 元数据",
    "software": "生成软件信息",
    "description": "图像描述文本",
    "imagedescription": "图像描述文本",
    "usercomment": "用户注释",
    "xpcomment": "Windows 注释",
    "xpkeywords": "Windows 关键词",
    "xptitle": "Windows 标题",
    "xpauthor": "Windows 作者",
    "title": "标题文本",
    "artist": "作者信息",
    "copyright": "版权信息",
    "source": "来源信息",
    "model_hash": "模型哈希",
    "scan:matched_strings": "文本扫描命中的生成内容",
    "format": "隐写格式标识",
    "json": "完整元数据 JSON",
    "uc": "负面提示词",
    "negative_prompt": "负面提示词",
    "negativeprompt": "负面提示词",
    "steps": "采样步数",
    "sampler": "采样器",
    "seed": "随机种子",
    "scale": "CFG / 提示词权重",
    "model": "模型信息",
    "v4_prompt": "NovelAI v4 提示词结构",
    "v4_negative_prompt": "NovelAI v4 负面提示词",
    "char_captions": "角色提示词",
    "scheduler": "调度器",
    "noise_schedule": "噪声调度",
}
HIGH_RISK_FIELD_KEYS = ("parameters", "prompt", "workflow", "sd-metadata", "comment", "matched_strings")


def is_ai_work(illust):
    """判断作品是否 AI 作品：Pixiv 的 illust_ai_type=2，或标签带明显 AI 标记。"""
    flag = _int(get(illust, "illust_ai_type", "illustAiType", "ai_type", "aiType", default=0))
    if flag == 2:
        return True
    for name in illust_tags(illust):
        low = name.strip().lower()
        if low in AI_TAG_MARKERS:
            return True
        if any(token in low for token in ("ai生成", "aiイラスト", "ai-generated", "aiart", "生成ai", "ai画像", "ai创作")):
            return True
    return False


def parse_tags(value):
    """tags 支持数组或字符串（逗号 / 空白分隔）。"""
    if value is None:
        return []
    parts = []
    if isinstance(value, str):
        parts = re.split(r"[,，、\s]+", value.strip())
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, str):
                parts.extend(re.split(r"[,，、\s]+", item.strip()))
            elif item is not None:
                parts.append(str(item).strip())
    else:
        parts = [str(value).strip()]
    result = []
    seen = set()
    for part in parts:
        part = str(part).strip().strip("#")
        if part and part.lower() not in seen:
            seen.add(part.lower())
            result.append(part)
    return result


def parse_ids(value):
    """ids 支持数组、数字、字符串（含 pixiv 链接 / 逗号分隔）。"""
    if value is None:
        return []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [int(value)] if int(value) > 0 else []
    if isinstance(value, str):
        chunks = [c for c in re.split(r"[,，\s]+", value.strip()) if c]
    elif isinstance(value, (list, tuple, set)):
        chunks = list(value)
    else:
        chunks = [value]

    result = []
    seen = set()
    for chunk in chunks:
        if isinstance(chunk, bool):
            continue
        if isinstance(chunk, (int, float)):
            work_id = int(chunk)
        else:
            text = str(chunk).strip()
            if not text:
                continue
            m = re.search(r"(?:artworks|illust_id=|/i/)(\d+)", text)
            if m:
                work_id = int(m.group(1))
            elif re.fullmatch(r"\d+", text):
                work_id = int(text)
            else:
                nums = re.findall(r"\d+", text)
                if not nums:
                    continue
                work_id = int(nums[-1])
        if work_id > 0 and work_id not in seen:
            seen.add(work_id)
            result.append(work_id)
    return result


def _is_generic_tag(name):
    return str(name or "").strip().lower() in GENERIC_TAGS


def _is_style_tag(name):
    low = str(name or "").lower()
    return any(keyword.lower() in low for keyword in STYLE_KEYWORDS)


# ---------------------------------------------------------------------------
# 预览：标签模式
# ---------------------------------------------------------------------------

def preview_by_tag(client, payload, budget, warnings):
    tags = parse_tags(payload.get("tags"))
    if not tags:
        raise PixivError("标签模式需要至少一个标签（tags）", 400)

    seed_ids = set(parse_ids(payload.get("ids")))
    r18 = _bool(payload.get("r18"), False)
    work_type = str(payload.get("work_type") or "all").lower()
    sort_key = str(payload.get("sort") or "date").lower()
    sort = "popular_desc" if sort_key.startswith("popular") else "date_desc"
    limit = _clamp_int(payload.get("limit"), 1, 100, 20)
    min_bookmarks = max(0, _int(payload.get("min_bookmarks"), 0))
    pages = _clamp_int(payload.get("pages"), 1, 10, 1)
    skip_existing = _bool(payload.get("skip_existing"), False)
    cursor_raw = payload.get("cursor")
    cursor_main = ""
    cursor_manga = ""
    if isinstance(cursor_raw, dict):
        cursor_main = str(cursor_raw.get("main") or "").strip()
        cursor_manga = str(cursor_raw.get("manga") or "").strip()
    else:
        cursor_main = str(cursor_raw or "").strip()
    is_cursor = bool(cursor_main or cursor_manga)

    word = " ".join(tags)
    raw_illusts = []
    sort_state = {"sort": sort}

    def collect_search(search_word, page_limit, page_url=None):
        """按关键词翻页收集；热度排序不可用时自动降级为最新排序。"""
        collected_next = page_url
        for page_index in range(page_limit):
            if budget.left() <= 0:
                warnings.append("预览 API 调用次数达到上限，已停止继续翻页")
                break
            try:
                data = client.search_illust(search_word, sort=sort_state["sort"], budget=budget, page_url=collected_next)
            except PixivError as exc:
                if page_index == 0 and not collected_next and sort_state["sort"] == "popular_desc":
                    warnings.append("按热度排序不可用，已自动降级为按最新排序")
                    sort_state["sort"] = "date_desc"
                    try:
                        data = client.search_illust(search_word, sort="date_desc", budget=budget)
                    except PixivError as exc2:
                        warnings.append(f"搜索「{search_word}」失败：{exc2}")
                        return None
                elif page_index == 0:
                    raise
                else:
                    warnings.append(f"「{search_word}」第 {page_index + 1} 页获取失败：{exc}")
                    break
            raw_illusts.extend(get(data, "illusts", default=[]) or [])
            collected_next = get(data, "next_url", "nextUrl", default=None)
            if not collected_next:
                break
        return collected_next

    # cursor 表示「下一批」：只从上一批的 next_url 继续一页，避免重复和变慢。
    page_limit = 1 if is_cursor else pages
    if is_cursor:
        next_url = collect_search(word, 1, page_url=cursor_main or None) if cursor_main else ""
    else:
        next_url = collect_search(word, page_limit)
    next_manga = ""

    # 漫画模式额外搜索「标签 + 漫画」：第一批补搜，翻页时继续漫画搜索的 cursor。
    if work_type == "manga":
        if is_cursor:
            next_manga = (
                collect_search(word + " 漫画", 1, page_url=cursor_manga or None)
                if cursor_manga else ""
            ) or ""
        else:
            next_manga = collect_search(word + " 漫画", min(2, pages)) or ""

    # 去重（同一作品可能重复出现）
    unique = []
    seen = set()
    for illust in raw_illusts:
        work_id = _int(get(illust, "id", default=0))
        if work_id <= 0 or work_id in seen or work_id in seed_ids:
            continue
        seen.add(work_id)
        unique.append(illust)

    candidates_count = len(unique)
    downloaded_ids = scan_downloaded_ids()
    max_bookmarks = max([_int(get(i, "total_bookmarks", "totalBookmarks", default=0)) for i in unique], default=0)

    requested_lower = {t.lower() for t in tags}
    items = []
    for illust in unique:
        if not passes_filters(illust, r18, work_type, min_bookmarks):
            continue
        bookmarks = _int(get(illust, "total_bookmarks", "totalBookmarks", default=0))
        # score 归一化到 0~1：收藏越多越靠前，但保留基础分避免全为 0
        if max_bookmarks > 0:
            score = 0.55 + 0.45 * (bookmarks / max_bookmarks)
        else:
            score = 1.0
        match_tags = [t for t in illust_tags(illust) if t.lower() in requested_lower]
        item = build_item(illust, match_tags, score, downloaded_ids)
        if skip_existing and item["already_downloaded"]:
            continue
        items.append(item)

    items.sort(key=lambda x: (-x["score"], -x["bookmarks"]))
    items = items[:limit]

    if work_type == "manga":
        cursor_out = {"main": next_url or "", "manga": next_manga or ""}
        if not cursor_out["main"] and not cursor_out["manga"]:
            cursor_out = ""
        exhausted = not bool(cursor_out)
    else:
        cursor_out = next_url or ""
        exhausted = not bool(cursor_out)

    return {
        "mode": "tag",
        "items": items,
        "seed": {"tags": [], "ids": sorted(seed_ids), "warnings": []},
        "candidates": candidates_count,
        "next_cursor": cursor_out,
        "exhausted": exhausted,
    }


# ---------------------------------------------------------------------------
# 预览：相似模式
# ---------------------------------------------------------------------------

def preview_by_similar(client, payload, budget, warnings):
    seed_ids_requested = parse_ids(payload.get("ids"))
    if not seed_ids_requested:
        raise PixivError("相似模式需要至少一个作品 ID（ids）", 400)
    seed_ids_requested = seed_ids_requested[:10]

    r18 = _bool(payload.get("r18"), False)
    work_type = str(payload.get("work_type") or "all").lower()
    limit = _clamp_int(payload.get("limit"), 1, 100, 20)
    min_bookmarks = max(0, _int(payload.get("min_bookmarks"), 0))
    seed_tag_limit = _clamp_int(payload.get("seed_tag_limit"), 1, 12, 6)
    include_related = _bool(payload.get("include_related"), True)
    skip_existing = _bool(payload.get("skip_existing"), False)

    # 1) 取种子作品详情
    seed_illusts = []
    seed_ids_used = []
    for work_id in seed_ids_requested:
        if budget.left() <= 0:
            warnings.append("预览 API 调用次数达到上限，已停止继续获取种子详情")
            break
        try:
            detail = client.illust_detail(work_id, budget=budget)
        except PixivError as exc:
            warnings.append(f"种子作品 {work_id} 详情获取失败：{exc}")
            continue
        x_restrict = _int(get(detail, "x_restrict", "xRestrict", default=0))
        if not r18 and x_restrict > 0:
            warnings.append(f"种子作品 {work_id} 属于 R18，已忽略")
            continue
        seed_illusts.append(detail)
        seed_ids_used.append(work_id)

    if not seed_illusts:
        raise PixivError("没有可用的种子作品（可能均为 R18 或获取失败）", 400)

    # 2) 抽取种子标签并计算 DF 权重
    seed_count = len(seed_illusts)
    # 作者名本身常被当成标签（如画师名），它更像“同一作者”而非画风，排除掉
    author_names = set()
    for illust in seed_illusts:
        user = get(illust, "user", default={}) or {}
        for key in ("name", "account"):
            value = str(get(user, key, default="") or "").strip().lower()
            if value:
                author_names.add(value)
    tag_seed_ids = {}  # 标签名 → 出现的种子作品 id 集合
    for illust in seed_illusts:
        work_id = _int(get(illust, "id", default=0))
        for name in illust_tags(illust):
            if _is_generic_tag(name):
                continue
            if name.strip().lower() in author_names:
                continue
            tag_seed_ids.setdefault(name, set()).add(work_id)

    if not tag_seed_ids:
        warnings.append("种子作品没有可用的特征标签，只能依赖相关推荐")
    tag_weights = {}
    for name, holders in tag_seed_ids.items():
        df = len(holders)
        weight = 0.6 + 0.8 * (df / max(1, seed_count))
        if _is_style_tag(name):
            weight += 0.5
        tag_weights[name] = min(2.0, weight)
    total_weight = sum(tag_weights.values()) or 1.0

    seed_tags = []
    for name, weight in sorted(tag_weights.items(), key=lambda kv: (-kv[1], kv[0])):
        seed_tags.append({
            "name": name,
            "weight": round(weight, 3),
            "count": len(tag_seed_ids[name]),
            "style": _is_style_tag(name),
        })

    # 3) 收集候选：相关推荐 + 高权重标签搜索
    candidates = {}  # id → {"illust": {...}, "sources": set()}

    def add_candidate(illust, source):
        work_id = _int(get(illust, "id", default=0))
        if work_id <= 0 or work_id in seed_ids_used:
            return
        entry = candidates.get(work_id)
        if entry is None:
            candidates[work_id] = {"illust": illust, "sources": {source}}
        else:
            entry["sources"].add(source)

    if include_related:
        for illust in seed_illusts:
            if budget.left() <= 0:
                warnings.append("预览 API 调用次数达到上限，已停止获取相关推荐")
                break
            work_id = _int(get(illust, "id", default=0))
            try:
                related = client.illust_related(work_id, budget=budget)
            except PixivError as exc:
                warnings.append(f"作品 {work_id} 的相关推荐获取失败：{exc}")
                continue
            for candidate in get(related, "illusts", default=[]) or []:
                add_candidate(candidate, "related")

    tag_names_by_weight = sorted(tag_weights.keys(), key=lambda n: -tag_weights[n])
    for tag in tag_names_by_weight[:seed_tag_limit]:
        if budget.left() <= 0:
            warnings.append("预览 API 调用次数达到上限，已停止标签搜索")
            break
        search_word = (tag + " 漫画") if work_type == "manga" else tag
        data = None
        try:
            data = client.search_illust(search_word, sort="popular_desc", budget=budget)
        except PixivError as exc:
            warnings.append(f"标签「{search_word}」按热度搜索失败，已降级为按最新排序（{exc}）")
            try:
                data = client.search_illust(search_word, sort="date_desc", budget=budget)
            except PixivError as exc2:
                warnings.append(f"标签「{search_word}」搜索失败：{exc2}")
                continue
        for candidate in get(data, "illusts", default=[]) or []:
            add_candidate(candidate, f"tag:{tag}")

    # 4) 打分与过滤
    downloaded_ids = scan_downloaded_ids()
    items = []
    for work_id, entry in candidates.items():
        illust = entry["illust"]
        if not passes_filters(illust, r18, work_type, min_bookmarks):
            continue
        candidate_tags = illust_tags(illust)
        matched = [t for t in candidate_tags if t in tag_weights]
        matched_weight = sum(tag_weights[t] for t in matched)
        score = 0.45 * (matched_weight / total_weight)
        if "related" in entry["sources"]:
            score += 0.35  # 相关推荐来源加成
        item = build_item(illust, matched, min(1.0, score), downloaded_ids)
        if skip_existing and item["already_downloaded"]:
            continue
        items.append(item)

    items.sort(key=lambda x: (-x["score"], -x["bookmarks"]))
    items = items[:limit]

    return {
        "mode": "similar",
        "items": items,
        "seed": {
            "tags": seed_tags[:20],
            "ids": seed_ids_used,
            "warnings": [],
        },
        "candidates": len(candidates),
    }


class RelatedCrawl:
    """按 Pixiv「相关推荐」一层层往下爬：种子 → 相关 → 相关的相关。

    每次 next_batch 只返回还没出现过的作品；frontier 保留未展开的作品，
    所以「下一批」会继续从上次停下的地方往下走，不会重复上一批。
    """

    def __init__(self, session_id, seed_ids, config):
        self.id = session_id
        self.config = config
        self.created_at = time.time()
        self.lock = threading.RLock()
        self.visited = set(int(i) for i in seed_ids)
        self.excluded = set(int(i) for i in (config.get("exclude_ids") or []))
        self.seed_ids = list(self.visited)
        self.frontier = collections.deque()
        self.pending = collections.deque()
        self.returned_ids = set()
        self.exhausted = False
        self.batch_index = 0
        self.calls = 0
        self.warnings = []
        self.seed_ids_used = []
        self._prepare_seeds(seed_ids)

    def _prepare_seeds(self, seed_ids):
        budget = ApiBudget(MAX_PREVIEW_CALLS)
        for work_id in seed_ids:
            if budget.left() <= 0:
                self.warnings.append("种子详情获取达到调用上限")
                break
            try:
                detail = STATE.client.illust_detail(work_id, budget=budget)
            except PixivError as exc:
                self.warnings.append(f"种子作品 {work_id} 详情获取失败：{exc}")
                continue
            x_restrict = _int(get(detail, "x_restrict", "xRestrict", default=0))
            if not self.config.get("r18") and x_restrict > 0:
                self.warnings.append(f"种子作品 {work_id} 属于 R18，已跳过")
                continue
            self.seed_ids_used.append(work_id)
            self.frontier.append((work_id, 0))
        if not self.frontier:
            raise PixivError("没有可用的种子作品（可能均为 R18 或获取失败）", 400)

    def _enqueue_related(self, work_id, layer, budget):
        if budget.left() <= 0:
            return
        try:
            data = STATE.client.illust_related(work_id, budget=budget)
        except PixivError as exc:
            self.warnings.append(f"作品 {work_id} 的相关推荐获取失败：{exc}")
            return
        self.calls += 1
        illusts = list(get(data, "illusts", default=[]) or [])
        # 相关推荐可能还有下一页：只补一页，避免一次展开太慢。
        next_url = str(data.get("next_url") or data.get("nextUrl") or "")
        if next_url and budget.left() > 0:
            try:
                more = STATE.client.api_get(next_url, budget=budget)
                illusts.extend(get(more, "illusts", default=[]) or [])
                self.calls += 1
            except PixivError:
                pass
        for illust in illusts:
            candidate_id = _int(get(illust, "id", default=0))
            if candidate_id <= 0 or candidate_id in self.visited:
                continue
            self.visited.add(candidate_id)
            # 不满足筛选条件的作品也继续展开，避免一票否决整条链。
            self.frontier.append((candidate_id, layer + 1))
            if passes_filters(illust, self.config["r18"], self.config["work_type"],
                              self.config["min_bookmarks"]):
                self.pending.append((illust, layer + 1, candidate_id))

    def _take_pending(self, count, items, downloaded_ids):
        while self.pending and len(items) < count:
            illust, layer, candidate_id = self.pending.popleft()
            if candidate_id in self.returned_ids:
                continue
            self.returned_ids.add(candidate_id)
            if candidate_id in self.excluded:
                continue
            if self.config.get("ai_only") and not is_ai_work(illust):
                continue
            if self.config.get("skip_existing"):
                work_id = _int(get(illust, "id", default=0))
                if work_id in downloaded_ids:
                    continue
            score = max(0.35, 0.92 - layer * 0.025)
            item = build_item(illust, [], score, downloaded_ids)
            item["layer"] = layer
            item["related"] = True
            items.append(item)

    def next_batch(self, count):
        with self.lock:
            count = max(1, min(50, int(count or 20)))
            budget = ApiBudget(max(12, min(MAX_PREVIEW_CALLS, count * 2)))
            downloaded_ids = scan_downloaded_ids()
            items = []
            self._take_pending(count, items, downloaded_ids)
            while len(items) < count and self.frontier and budget.left() > 0:
                work_id, layer = self.frontier.popleft()
                self._enqueue_related(work_id, layer, budget)
                self._take_pending(count, items, downloaded_ids)
            if not items and not self.frontier and not self.pending:
                self.exhausted = True
            self.batch_index += 1
            return {
                "items": items,
                "batch": self.batch_index,
                "exhausted": self.exhausted and not self.pending and not self.frontier,
                "stats": self.stats(),
            }

    def stats(self):
        with self.lock:
            return {
                "visited": len(self.visited),
                "frontier": len(self.frontier),
                "pending": len(self.pending),
                "returned": len(self.returned_ids),
                "calls": self.calls,
                "batch": self.batch_index,
                "seeds": len(self.seed_ids_used),
            }

    def snapshot(self):
        return {"session_id": self.id, "stats": self.stats(), "warnings": self.warnings[-8:]}


def normalize_related_config(payload):
    seed_ids = parse_ids(payload.get("ids"))[:10]
    if not seed_ids:
        raise PixivError("相关推荐模式需要至少一个种子作品 ID", 400)
    work_type = str(payload.get("work_type") or "all").lower()
    if work_type not in ("all", "manga", "illust"):
        work_type = "all"
    return {
        "ids": seed_ids,
        "exclude_ids": parse_ids(payload.get("exclude_ids"))[:500],
        "r18": _bool(payload.get("r18"), False),
        "work_type": work_type,
        "min_bookmarks": max(0, _int(payload.get("min_bookmarks"), 0)),
        "batch_size": _clamp_int(payload.get("batch_size"), 1, 50, 20),
        "skip_existing": _bool(payload.get("skip_existing"), False),
    }


def api_related_start(payload):
    config = normalize_related_config(payload)
    if not STATE.client.refresh_token and STATE.key_data.get("refresh_token"):
        STATE.client.refresh_token = STATE.key_data["refresh_token"]
    if not STATE.client.refresh_token:
        raise PixivError("尚未连接 Pixiv，请先填写 refresh_token", 401)
    STATE.client.ensure_token()
    now = time.time()
    with STATE.related_lock:
        for session_id, old in list(STATE.related_sessions.items()):
            if now - old.created_at > 3600:
                STATE.related_sessions.pop(session_id, None)
        if len(STATE.related_sessions) > 12:
            oldest = min(STATE.related_sessions.items(), key=lambda pair: pair[1].created_at)
            STATE.related_sessions.pop(oldest[0], None)
        session_id = uuid.uuid4().hex[:12]
        crawl = RelatedCrawl(session_id, config["ids"], config)
        STATE.related_sessions[session_id] = crawl
    batch = crawl.next_batch(config["batch_size"])
    return {
        "ok": True,
        "mode": "related",
        "session_id": session_id,
        "items": batch["items"],
        "batch": batch["batch"],
        "exhausted": batch["exhausted"],
        "stats": batch["stats"],
        "warnings": crawl.warnings[-8:],
        "seed": {"ids": crawl.seed_ids_used},
    }


def api_related_next(payload):
    session_id = str(payload.get("session_id") or "").strip()
    with STATE.related_lock:
        crawl = STATE.related_sessions.get(session_id)
    if crawl is None:
        raise PixivError("相关推荐会话已过期，请重新开始", 404)
    batch_size = _clamp_int(payload.get("batch_size"), 1, 50, crawl.config.get("batch_size", 20))
    batch = crawl.next_batch(batch_size)
    return {
        "ok": True,
        "mode": "related",
        "session_id": session_id,
        "items": batch["items"],
        "batch": batch["batch"],
        "exhausted": batch["exhausted"],
        "stats": batch["stats"],
        "warnings": crawl.warnings[-8:],
    }



def do_preview(payload):
    """预览入口：分发 tag / similar 两种模式。"""
    started = time.time()
    mode = str(payload.get("mode") or "tag").lower()
    if mode not in ("tag", "similar"):
        raise PixivError(f"不支持的 mode：{mode}", 400)

    # 若从未连接过但存在密钥文件，则使用内存中的 refresh_token 惰性登录
    if not STATE.client.refresh_token and STATE.key_data.get("refresh_token"):
        STATE.client.refresh_token = STATE.key_data["refresh_token"]

    budget = ApiBudget(MAX_PREVIEW_CALLS)
    warnings = []
    calls_before = STATE.client.calls

    if mode == "tag":
        result = preview_by_tag(STATE.client, payload, budget, warnings)
    else:
        result = preview_by_similar(STATE.client, payload, budget, warnings)

    elapsed_ms = int((time.time() - started) * 1000)
    api_calls = max(0, STATE.client.calls - calls_before)
    result["seed"]["warnings"] = list(warnings)
    return {
        "ok": True,
        "mode": result["mode"],
        "items": result["items"],
        "seed": result["seed"],
        "stats": {
            "candidates": result["candidates"],
            "kept": len(result["items"]),
            "api_calls": api_calls,
            "elapsed_ms": elapsed_ms,
        },
        "warnings": warnings,
        "next_cursor": result.get("next_cursor", ""),
        "exhausted": result.get("exhausted", False),
    }


# ---------------------------------------------------------------------------
# 缩略图代理（LRU 内存缓存）
# ---------------------------------------------------------------------------

class ThumbCache:
    """内存 LRU：最多 200 张 / 50MB。"""

    def __init__(self, max_items=200, max_bytes=50 * 1024 * 1024):
        self.max_items = max_items
        self.max_bytes = max_bytes
        self.lock = threading.Lock()
        self.data = OrderedDict()  # url → (content_type, bytes)
        self.total_bytes = 0

    def get(self, url):
        with self.lock:
            item = self.data.get(url)
            if item is None:
                return None
            self.data.move_to_end(url)
            return item

    def put(self, url, content_type, body):
        size = len(body)
        if size > self.max_bytes:
            return
        with self.lock:
            old = self.data.pop(url, None)
            if old is not None:
                self.total_bytes -= len(old[1])
            self.data[url] = (content_type, body)
            self.total_bytes += size
            while self.data and (len(self.data) > self.max_items or self.total_bytes > self.max_bytes):
                _, evicted = self.data.popitem(last=False)
                self.total_bytes -= len(evicted[1])


THUMB_CACHE = ThumbCache()


def fetch_thumb(url):
    """下载缩略图/原图（带防盗链头），返回 (content_type, bytes)。"""
    cached = THUMB_CACHE.get(url)
    if cached is not None:
        return cached

    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        raise PixivError("缩略图地址无效", 400) from None
    if parsed.scheme != "https" or parsed.hostname not in THUMB_ALLOWED_HOSTS:
        raise PixivError("只允许代理 i.pximg.net / i-cf.pximg.net 的图片", 400)

    try:
        resp = STATE.thumb_session.get(url, headers=IMG_HEADERS, timeout=20)
    except requests.RequestException as exc:
        raise PixivError(f"缩略图下载失败：{exc}", 502) from exc
    if resp.status_code != 200:
        raise PixivError(f"缩略图下载失败：HTTP {resp.status_code}", 404)

    ctype = (resp.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
    if not ctype.startswith("image/"):
        ctype = "image/jpeg"
    body = resp.content
    if not body:
        raise PixivError("缩略图内容为空", 404)
    THUMB_CACHE.put(url, ctype, body)
    return ctype, body


# ---------------------------------------------------------------------------
# 下载任务
# ---------------------------------------------------------------------------

class WorkCancelled(Exception):
    """作品下载被取消。"""


class DownloadJob:
    """一个异步下载任务。"""

    def __init__(self, job_id, works, concurrency=4, pages_limit=0, skip_existing=True):
        self.id = job_id
        self.output_dir = STATE.output_dir
        self.concurrency = concurrency
        self.pages_limit = pages_limit
        self.skip_existing = skip_existing
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.stop_event = threading.Event()
        self.session = build_http_session()  # 图片下载专用（不带 API 限速）

        created = now_ms()
        self.state = "running"
        self.phase = "preparing"
        self.created_at = created
        self.started_at = created
        self.finished_at = None
        self.total_works = len(works)
        self.done_works = 0
        self.skipped_works = 0
        self.failed_works = 0
        self.total_pages = 0
        self.done_pages = 0
        self.total_bytes = 0
        self.speed_bps = 0.0
        self.speed_pages = 0.0
        self.eta_seconds = None
        self.speed_series = []
        self.current = []
        self.errors = []
        self.log = []
        self._items = []
        for work in works:
            page_count = _int(work.get("page_count"), 0)
            self._items.append({
                "id": _int(work.get("id"), 0),
                "title": str(work.get("title") or ""),
                "state": "queued",
                "pages": page_count,
                "pages_done": 0,
                "bytes": 0,
                "dir": None,
                "error": None,
                "_known_pages": page_count,
                "_detail": None,
                "_pages": [],
                "_tags": [],
                "_type": "",
            })

    # -- 日志 --------------------------------------------------------------

    def _log(self, level, text):
        entry = {"t": now_ms(), "level": str(level), "text": str(text)}
        with self.lock:
            self.log.append(entry)
            if len(self.log) > 80:
                del self.log[:-80]
        safe_print(f"[{time.strftime('%H:%M:%S')}] [{self.id}] [{level}] {text}", flush=True)

    # -- 状态 --------------------------------------------------------------

    def is_running(self):
        with self.lock:
            return self.state == "running"

    def snapshot(self):
        """生成前端轮询用的完整快照。"""
        with self.lock:
            current_time = now_ms()
            elapsed = round(max(0.0, ((self.finished_at or current_time) - self.started_at) / 1000.0), 2)
            items = [{
                "id": item["id"],
                "title": item["title"],
                "state": item["state"],
                "pages": item["pages"],
                "pages_done": item["pages_done"],
                "bytes": item["bytes"],
                "dir": item["dir"],
                "error": item["error"],
            } for item in self._items]
            return {
                "id": self.id,
                "state": self.state,
                "phase": self.phase,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "total_works": self.total_works,
                "done_works": self.done_works,
                "skipped_works": self.skipped_works,
                "failed_works": self.failed_works,
                "total_pages": self.total_pages,
                "done_pages": self.done_pages,
                "total_bytes": self.total_bytes,
                "speed_bps": round(self.speed_bps, 1),
                "speed_pages": round(self.speed_pages, 2),
                "eta_seconds": self.eta_seconds,
                "elapsed_seconds": elapsed,
                "speed_series": [dict(sample) for sample in self.speed_series[-60:]],
                "current": [dict(entry) for entry in self.current],
                "items": items,
                "errors": [dict(entry) for entry in self.errors],
                "log": [dict(entry) for entry in self.log[-80:]],
                "output_dir": self.output_dir,
            }

    # -- 速度采样 ----------------------------------------------------------

    def _sampler_loop(self):
        """每 0.5s 采样一次，按最近 2s 窗口计算速度、ETA 与速度曲线。"""
        samples = deque()  # (monotonic, done_pages, total_bytes)
        while not self.stop_event.wait(0.5):
            mono = time.monotonic()
            stamp = now_ms()
            with self.lock:
                pages = self.done_pages
                total_bytes = self.total_bytes
            samples.append((mono, pages, total_bytes))
            while len(samples) > 2 and mono - samples[0][0] > 2.0:
                samples.popleft()
            bps = 0.0
            pps = 0.0
            if len(samples) >= 2:
                dt = samples[-1][0] - samples[0][0]
                if dt > 0:
                    bps = max(0.0, (samples[-1][2] - samples[0][2]) / dt)
                    pps = max(0.0, (samples[-1][1] - samples[0][1]) / dt)
            with self.lock:
                remaining = max(0, self.total_pages - pages)
                if pps > 0 and remaining > 0:
                    eta = int(math.ceil(remaining / pps))
                elif remaining == 0:
                    eta = 0
                else:
                    eta = None
                self.speed_bps = bps
                self.speed_pages = pps
                self.eta_seconds = eta
                self.speed_series.append({"t": stamp, "bps": round(bps, 1), "pps": round(pps, 2)})
                if len(self.speed_series) > 60:
                    del self.speed_series[:-60]

    # -- 跳过 / 失败 -------------------------------------------------------

    def _maybe_skip(self, item, expected_pages):
        """已存在判定：目录存在 + info.json 存在 + 已下载页数 ≥ 应抓页数。"""
        if not self.skip_existing or expected_pages <= 0:
            return False
        work_dir = find_work_dir(item["id"])
        if not work_dir:
            return False
        if not os.path.isfile(os.path.join(work_dir, "info.json")):
            return False
        have = count_page_files(work_dir, item["id"])
        if have < expected_pages:
            return False
        with self.lock:
            item["state"] = "skipped"
            item["dir"] = work_dir
            item["pages"] = expected_pages
            item["pages_done"] = have
            self.skipped_works += 1
        self._log("info", f"已存在，跳过 {item['id']}（{have}/{expected_pages} 页）")
        return True

    def _fail(self, item, message):
        with self.lock:
            item["state"] = "failed"
            item["error"] = str(message)
            self.failed_works += 1
            self.errors.append({"id": item["id"], "message": str(message)})
        self._log("error", f"作品 {item['id']} 失败：{message}")

    # -- 准备阶段 ----------------------------------------------------------

    def _prepare(self):
        self._log("info", f"开始准备 {len(self._items)} 个作品")
        for item in self._items:
            if self.cancel_event.is_set():
                return
            work_id = item["id"]
            if work_id <= 0:
                self._fail(item, "作品 ID 无效")
                continue

            # 已知页数时先做一次免 API 的跳过检查
            if item["_known_pages"] > 0:
                expected_known = item["_known_pages"]
                if self.pages_limit > 0:
                    expected_known = min(expected_known, self.pages_limit)
                if self._maybe_skip(item, expected_known):
                    continue

            try:
                detail = STATE.client.illust_detail(work_id)
            except PixivError as exc:
                self._fail(item, f"获取详情失败：{exc}")
                continue
            except Exception as exc:  # noqa: BLE001
                self._fail(item, f"获取详情异常：{exc}")
                continue

            item["_detail"] = detail
            item["_type"] = str(get(detail, "type", default="illust") or "illust").lower()
            title = str(get(detail, "title", default="") or "").strip()
            if title:
                item["title"] = title
            item["_tags"] = illust_tag_pairs(detail)

            if item["_type"] == "ugoira":
                with self.lock:
                    item["state"] = "skipped"
                    item["pages"] = 0
                    item["error"] = "动图（ugoira）暂不支持下载"
                    self.skipped_works += 1
                self._log("warn", f"跳过动图作品 {work_id}《{item['title']}》：暂不支持 ugoira")
                continue

            pages = build_pages(detail)
            if not pages:
                self._fail(item, "未找到可下载的图片地址")
                continue
            total = len(pages)
            if self.pages_limit > 0:
                total = min(total, self.pages_limit)
            if total <= 0:
                self._fail(item, "页数为 0")
                continue

            # 页数之前未知时，拿到详情后再做一次跳过检查
            if item["_known_pages"] <= 0 and self._maybe_skip(item, total):
                continue

            with self.lock:
                item["_pages"] = pages[:total]
                item["pages"] = total
                self.total_pages += total
            self._log("info", f"准备完成 {work_id}《{item['title']}》（{total} 页）")

        with self.lock:
            total_pages = self.total_pages
        self._log("info", f"解析完成，共 {total_pages} 页待下载")

    # -- 下载阶段 ----------------------------------------------------------

    def _download_all(self):
        queued = [item for item in self._items if item["state"] == "queued"]
        if not queued:
            self._log("info", "没有需要下载的作品")
            return
        self.phase = "downloading"
        self._log("info", f"开始下载：{len(queued)} 个作品，并发 {self.concurrency}")
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = [pool.submit(self._download_work, item) for item in queued]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:  # noqa: BLE001
                    self._log("error", f"下载线程异常：{exc}")

    def _download_work(self, item):
        if self.cancel_event.is_set():
            return
        work_id = item["id"]
        current = {
            "id": work_id,
            "title": item["title"],
            "pages_done": 0,
            "pages_total": item["pages"],
        }
        with self.lock:
            item["state"] = "downloading"
            self.current.append(current)

        work_dir = None
        try:
            work_dir = os.path.join(self.output_dir, f"{work_id}_{safe_title(item['title'])}")
            os.makedirs(work_dir, exist_ok=True)
            item["dir"] = work_dir
            for index, page in enumerate(item["_pages"]):
                if self.cancel_event.is_set():
                    raise WorkCancelled()
                written = self._fetch_page(work_id, index, page, work_dir)
                with self.lock:
                    item["pages_done"] = index + 1
                    item["bytes"] += written
                    current["pages_done"] = index + 1
                    self.done_pages += 1
            with self.lock:
                item["state"] = "done"
                self.done_works += 1
            self._log("info", f"完成 {work_id}《{item['title']}》（{item['pages']} 页 / {format_bytes(item['bytes'])}）")
        except WorkCancelled:
            with self.lock:
                item["state"] = "failed"
                item["error"] = "已取消"
                self.failed_works += 1
            self._log("warn", f"已取消 {work_id}《{item['title']}》")
        except Exception as exc:  # noqa: BLE001
            self._fail(item, str(exc))
        finally:
            with self.lock:
                self.current = [entry for entry in self.current if entry is not current]
            self._write_info(item, work_dir)

    def _fetch_page(self, work_id, index, page, work_dir):
        """下载单页，支持 .part 断点续传；失败重试 2 次；原图失败回退 large。"""
        urls = [page["original"]]
        if page.get("fallback") and page["fallback"] != page["original"]:
            urls.append(page["fallback"])

        timeout_setting = max(5, int(STATE.settings.get("download_timeout") or 25))
        last_error = ""
        for url in urls:
            ext = guess_ext("", url)
            final_path = os.path.join(work_dir, f"{work_id}_p{index:02d}{ext}")
            part_path = final_path + ".part"
            for attempt in range(3):  # 首次 + 2 次重试
                if self.cancel_event.is_set():
                    raise WorkCancelled()
                existing = 0
                try:
                    if os.path.isfile(part_path):
                        existing = os.path.getsize(part_path)
                except OSError:
                    existing = 0
                headers = dict(IMG_HEADERS)
                if existing > 0:
                    headers["Range"] = f"bytes={existing}-"
                try:
                    resp = self.session.get(
                        url, headers=headers, timeout=(10, timeout_setting), stream=True
                    )
                except requests.RequestException as exc:
                    last_error = f"网络错误：{exc}"
                    if attempt < 2:
                        time.sleep(0.8 * (attempt + 1))
                        continue
                    break

                try:
                    status = resp.status_code
                    if status == 416:
                        # 本地 .part 与远端不匹配，丢掉后重试整页
                        _silent_remove(part_path)
                        last_error = "HTTP 416（续传范围无效）"
                        if attempt < 2:
                            time.sleep(0.5 * (attempt + 1))
                            continue
                        break
                    if status in (200, 206):
                        mode = "ab" if (status == 206 and existing > 0) else "wb"
                        written = existing if mode == "ab" else 0
                        try:
                            with open(part_path, mode) as handle:
                                for chunk in resp.iter_content(chunk_size=65536):
                                    if self.cancel_event.is_set():
                                        raise WorkCancelled()
                                    if not chunk:
                                        continue
                                    handle.write(chunk)
                                    written += len(chunk)
                                    with self.lock:
                                        self.total_bytes += len(chunk)
                            if written <= 0:
                                raise RuntimeError("响应内容为空")
                            os.replace(part_path, final_path)
                            return written
                        except WorkCancelled:
                            raise
                        except Exception as exc:  # noqa: BLE001 - 写入失败可重试
                            last_error = f"写入失败：{exc}"
                            if attempt < 2:
                                time.sleep(0.7 * (attempt + 1))
                                continue
                            break

                    if status in (403, 404, 410):
                        # 原图可能被限制：换 fallback（large）再试
                        last_error = f"HTTP {status}"
                        break
                    if status == 429 or status >= 500:
                        last_error = f"HTTP {status}"
                        if attempt < 2:
                            time.sleep(1.0 * (attempt + 1))
                            continue
                        break
                    last_error = f"HTTP {status}"
                    break
                finally:
                    try:
                        resp.close()
                    except Exception:  # noqa: BLE001
                        pass

        raise RuntimeError(f"第 {index + 1} 页下载失败（{last_error or '未知错误'}）")

    def _write_info(self, item, work_dir):
        """写 info.json（含全部元数据与原图地址），失败只记日志。"""
        if not work_dir or not item.get("_detail"):
            return
        detail = item["_detail"]
        info = {
            "id": item["id"],
            "title": item["title"],
            "type": item["_type"],
            "page_count": len(item["_pages"]),
            "pages_downloaded": item["pages_done"],
            "x_restrict": _int(get(detail, "x_restrict", "xRestrict", default=0)),
            "total_bookmarks": _int(get(detail, "total_bookmarks", "totalBookmarks", default=0)),
            "width": _int(get(detail, "width", default=0)),
            "height": _int(get(detail, "height", default=0)),
            "create_date": str(get(detail, "create_date", "createDate", default="") or ""),
            "tags": item["_tags"],
            "author": illust_author(detail),
            "original_urls": [
                {"index": index, "url": page["original"], "fallback": page["fallback"]}
                for index, page in enumerate(item["_pages"])
            ],
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        }
        path = os.path.join(work_dir, "info.json")
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(info, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except OSError as exc:
            _silent_remove(tmp)
            self._log("warn", f"写入 info.json 失败 {os.path.basename(work_dir)}：{exc}")

    # -- 主流程 ------------------------------------------------------------

    def run(self):
        threading.Thread(target=self._sampler_loop, name=f"speed-{self.id}", daemon=True).start()
        try:
            # 下载前先确保登录状态可用，失败直接让整个任务进入 error
            STATE.client.ensure_token()
            self._prepare()
            if not self.cancel_event.is_set():
                self._download_all()
        except PixivError as exc:
            with self.lock:
                self.state = "error"
            self._log("error", f"无法连接 Pixiv：{exc}")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            with self.lock:
                self.state = "error"
            self._log("error", f"任务异常：{exc}")
        finally:
            with self.lock:
                self.stop_event.set()
                if self.state == "running":
                    self.state = "cancelled" if self.cancel_event.is_set() else "done"
                self.phase = "finished"
                self.finished_at = now_ms()
                self.speed_bps = 0.0
                self.speed_pages = 0.0
                self.eta_seconds = 0
                if not self.speed_series:
                    elapsed = max((self.finished_at - self.started_at) / 1000.0, 0.001)
                    self.speed_series.append({
                        "t": self.finished_at,
                        "bps": round(self.total_bytes / elapsed, 1),
                        "pps": round(self.done_pages / elapsed, 2),
                    })
                self.current = []
                final_state = self.state
            self._log("info", f"任务结束（{final_state}）：成功 {self.done_works}，跳过 {self.skipped_works}，失败 {self.failed_works}")
            with STATE.jobs_lock:
                if STATE.active_job is self:
                    STATE.active_job = None


# ---------------------------------------------------------------------------
# 任务注册表辅助
# ---------------------------------------------------------------------------

def normalize_download_works(payload):
    """解析下载请求中的 items / ids，返回 [{id,title,page_count}]。"""
    works = []
    seen = set()
    raw_items = payload.get("items")
    if isinstance(raw_items, list) and raw_items:
        for entry in raw_items:
            if isinstance(entry, dict):
                work_id = _int(entry.get("id"), 0)
                title = str(entry.get("title") or "")
                page_count = _int(entry.get("page_count") or entry.get("pages"), 0)
            else:
                work_id = _int(entry, 0)
                title = ""
                page_count = 0
            if work_id <= 0 or work_id in seen:
                continue
            seen.add(work_id)
            works.append({"id": work_id, "title": title, "page_count": page_count})
    if not works:
        for work_id in parse_ids(payload.get("ids")):
            if work_id <= 0 or work_id in seen:
                continue
            seen.add(work_id)
            works.append({"id": work_id, "title": "", "page_count": 0})
    return works


def prune_jobs(keep=30):
    """只保留最近 keep 个任务（内存友好）。"""
    with STATE.jobs_lock:
        if len(STATE.jobs) <= keep:
            return
        finished = [(job_id, job) for job_id, job in STATE.jobs.items() if not job.is_running()]
        finished.sort(key=lambda pair: pair[1].created_at)
        for job_id, job in finished[: len(STATE.jobs) - keep]:
            if STATE.active_job is job:
                continue
            STATE.jobs.pop(job_id, None)


# ---------------------------------------------------------------------------
# AI 元数据扫描任务（持续批次）
# ---------------------------------------------------------------------------

AI_SCAN_DIR_NAME = "AI元数据扫描"
IMAGE_FILE_RE = re.compile(r"^\d+_p\d+\.(?:jpg|jpeg|png|webp|gif)$", re.IGNORECASE)


class ScanJob:
    """AI 元数据扫描：持续发现 AI 作品 → 每批直接下载 → 检查原图元数据。"""

    def __init__(self, scan_id, config):
        self.id = scan_id
        self.config = config
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.state = "running"
        self.phase = "preparing"
        self.error = None
        self.created_at = now_ms()
        self.started_at = self.created_at
        self.finished_at = None
        self.batch_size = int(config.get("batch_size") or 10)
        self.batch_index = 0
        self.inspected_total = 0
        self.downloaded_total = 0
        self.hits_total = 0
        self.failed_total = 0
        self.seen_ids = set()
        self.seed_ids = set(config.get("ids") or [])
        self.current_batch = []
        self.downloader = None
        self.batches = []
        self.works = []
        self.hits = []
        self.log = []
        self.session_dir = ""
        self.session_rel = ""
        self.report_path = ""
        self._words = []
        self._word_cursor = 0
        self._word_next = {}
        self._pool = []
        self._pool_ids = set()
        self._related_crawl = None
        self._related_pending = []

    # -- 日志 / 状态 -------------------------------------------------------

    def _log(self, level, text):
        entry = {"t": now_ms(), "level": str(level), "text": str(text)}
        with self.lock:
            self.log.append(entry)
            if len(self.log) > 120:
                del self.log[:-120]
        safe_print(f"[{time.strftime('%H:%M:%S')}] [扫描 {self.id}] [{level}] {text}", flush=True)

    def is_running(self):
        with self.lock:
            return self.state == "running"

    def stop(self):
        self.cancel_event.set()
        downloader = self.downloader
        if downloader is not None:
            downloader.cancel_event.set()

    def snapshot(self):
        with self.lock:
            current_time = now_ms()
            elapsed = round(max(0.0, ((self.finished_at or current_time) - self.started_at) / 1000.0), 2)
            downloader = self.downloader
            download = None
            if downloader is not None:
                try:
                    ds = downloader.snapshot()
                    download = {
                        key: ds.get(key)
                        for key in ("state", "done_pages", "total_pages", "done_works", "total_works",
                                    "total_bytes", "speed_bps", "speed_pages", "current")
                    }
                except Exception:  # noqa: BLE001
                    download = None
            return {
                "id": self.id,
                "state": self.state,
                "phase": self.phase,
                "error": self.error,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "elapsed_seconds": elapsed,
                "batch_size": self.batch_size,
                "batch_index": self.batch_index,
                "inspected_total": self.inspected_total,
                "downloaded_total": self.downloaded_total,
                "hits_total": self.hits_total,
                "failed_total": self.failed_total,
                "current_batch": [dict(entry) for entry in self.current_batch],
                "download": download,
                "hits": [dict(entry) for entry in self.hits[-60:]],
                "batches": [dict(entry) for entry in self.batches],
                "log": [dict(entry) for entry in self.log[-80:]],
                "session_dir": self.session_dir,
                "session_rel": self.session_rel,
                "hits_rel": self._hits_rel(),
                "report_path": self.report_path,
                "output_dir": STATE.output_dir,
                "config": {
                    "mode": self.config.get("mode"),
                    "tags": list(self.config.get("tags") or []),
                    "ids": list(self.config.get("ids") or []),
                    "r18": bool(self.config.get("r18")),
                    "min_bookmarks": int(self.config.get("min_bookmarks") or 0),
                    "pages_limit": int(self.config.get("pages_limit") or 0),
                    "concurrency": int(self.config.get("concurrency") or 4),
                    "seed_tag_limit": int(self.config.get("seed_tag_limit") or 6),
                    "include_related": bool(self.config.get("include_related")),
                    "max_batches": int(self.config.get("max_batches") or 0),
                    "max_disk_gb": float(self.config.get("max_disk_gb") or 0),
                },
            }

    # -- 准备 --------------------------------------------------------------

    def _hits_rel(self):
        if not self.session_dir:
            return ""
        path = os.path.join(self.session_dir, "命中作品")
        if not os.path.isdir(path):
            return ""
        return os.path.relpath(path, STATE.output_dir).replace("\\", "/")

    def get_work(self, work_id):
        with self.lock:
            for work in self.works:
                if _int(work.get("id"), 0) == _int(work_id, 0):
                    return work
        return None

    def _describe_exposure(self, file_results, fields, markers):
        """把命中字段归纳成人类可读的“暴露情况”。"""
        categories = []
        seen_categories = set()
        sources = set()
        keys = []
        for field_key in fields.keys():
            module_key = field_key.split(":", 1)[1] if ":" in field_key else field_key
            parts = module_key.split(":")
            if parts:
                sources.add(str(parts[0]).upper())
            key = parts[-1].lower() if parts else module_key.lower()
            keys.append(key)
            label = EXPOSURE_KEY_LABELS.get(key)
            if not label:
                if key.startswith("xp"):
                    label = "Windows 文本字段"
                elif key in ("software",):
                    label = "生成软件信息"
                else:
                    label = f"{key} 字段"
            if label not in seen_categories:
                seen_categories.add(label)
                categories.append(label)

        marker_text = " ".join(str(marker).lower() for marker in markers)
        high_risk_tokens = (
            "stable diffusion", "novelai", "comfyui", "midjourney", "<lora:",
            "model_hash", "negative prompt", "steps", "sampler", "cfg scale", "parameters",
        )
        is_high = any(key in HIGH_RISK_FIELD_KEYS for key in keys) or any(
            token in marker_text for token in high_risk_tokens
        )
        level = "高" if is_high else ("中" if fields else "低")

        source_text = "、".join(sorted(sources)) or "图片"
        file_count = len({entry.get("file") for entry in file_results if entry.get("file")})
        if categories:
            summary = (
                f"在 {source_text} 元数据中发现 {len(fields)} 个残留字段"
                f"（涉及 {file_count} 个文件）：{'、'.join(categories[:6])}。"
            )
        else:
            summary = "发现可疑图片元数据，但未能归类具体字段。"
        if is_high:
            summary += "这些内容可能暴露完整提示词、采样器/步数/种子、模型或 LoRA 名称，以及生成流程。"
        else:
            summary += "这些内容可能暴露使用的生成软件或文本注释信息。"

        return {
            "level": level,
            "summary": summary,
            "categories": categories[:8],
            "field_count": len(fields),
            "sources": sorted(sources),
            "files": file_count,
        }

    def _write_metadata_record(self, work_dir, record):
        try:
            path = os.path.join(work_dir, "metadata_scan.json")
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(record, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except OSError as exc:
            self._log("warn", f"写入 metadata_scan.json 失败 {record.get('id')}：{exc}")
            _silent_remove(os.path.join(work_dir, "metadata_scan.json.tmp"))

    def _relocate_hit(self, record):
        """把命中作品从 batch 目录移到会话的「命中作品」文件夹，和普通作品隔离。"""
        src = os.path.join(STATE.output_dir, str(record.get("dir") or "").replace("/", os.sep))
        if not os.path.isdir(src):
            return
        hits_root = os.path.join(self.session_dir, "命中作品")
        try:
            os.makedirs(hits_root, exist_ok=True)
        except OSError as exc:
            self._log("warn", f"创建命中作品目录失败：{exc}")
            return
        base = os.path.basename(src.rstrip("\\/"))
        dest = os.path.join(hits_root, base)
        suffix = 2
        while os.path.exists(dest):
            dest = os.path.join(hits_root, f"{base}_{suffix}")
            suffix += 1
        try:
            shutil.move(src, dest)
        except OSError as exc:
            self._log("warn", f"移动命中作品 {record.get('id')} 失败，保留在批次目录：{exc}")
            return
        record["dir"] = os.path.relpath(dest, STATE.output_dir).replace("\\", "/")
        record["isolated"] = True
        self._write_metadata_record(dest, record)

    def _prepare(self):
        STATE.client.ensure_token()
        root = os.path.join(STATE.output_dir, AI_SCAN_DIR_NAME)
        os.makedirs(root, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        session_name = f"{stamp}_{self.id[:6]}"
        self.session_dir = os.path.join(root, session_name)
        os.makedirs(self.session_dir, exist_ok=True)
        self.session_rel = os.path.relpath(self.session_dir, STATE.output_dir).replace("\\", "/")
        self.report_path = os.path.join(self.session_dir, "report.json")
        self._load_previous_scanned()
        self._load_words()
        self._log("info", f"扫描会话目录：{self.session_dir}")

    def _load_previous_scanned(self):
        """把历史扫描报告里的作品 ID 载入 seen，避免重启后重复扫同一批。"""
        if not self.config.get("skip_scanned", True):
            return
        root = os.path.join(STATE.output_dir, AI_SCAN_DIR_NAME)
        if not os.path.isdir(root):
            return
        try:
            sessions = [entry.path for entry in os.scandir(root) if entry.is_dir()]
        except OSError:
            return
        sessions.sort(key=lambda path: os.path.basename(path), reverse=True)
        loaded = 0
        for path in sessions[:8]:
            report = os.path.join(path, "report.json")
            if not os.path.isfile(report):
                continue
            try:
                with open(report, encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                continue
            for work in data.get("works", []) or []:
                work_id = _int(work.get("id"), 0)
                if work_id > 0:
                    self.seen_ids.add(work_id)
                    loaded += 1
        if loaded:
            self._log("info", f"已跳过历史扫描过的作品 {len(self.seen_ids)} 个")

    def _collect_seed_tags(self):
        """按作品找相似时，从种子作品提取画风标签，并收集相关推荐里的 AI 作品。"""
        seed_illusts = []
        author_names = set()
        for work_id in list(self.config.get("ids") or [])[:10]:
            try:
                detail = STATE.client.illust_detail(work_id)
            except PixivError as exc:
                self._log("warn", f"种子作品 {work_id} 详情获取失败：{exc}")
                continue
            seed_illusts.append(detail)
            user = get(detail, "user", default={}) or {}
            for key in ("name", "account"):
                value = str(get(user, key, default="") or "").strip().lower()
                if value:
                    author_names.add(value)

        holders = {}
        for illust in seed_illusts:
            work_id = _int(get(illust, "id", default=0))
            for name in illust_tags(illust):
                if _is_generic_tag(name) or name.strip().lower() in author_names:
                    continue
                holders.setdefault(name, set()).add(work_id)
        seed_count = max(1, len(seed_illusts))
        ranked = []
        for name, works in holders.items():
            weight = 0.6 + 0.8 * (len(works) / seed_count)
            if _is_style_tag(name):
                weight += 0.5
            ranked.append((min(2.0, weight), name))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]))

        if self.config.get("include_related"):
            for illust in seed_illusts:
                work_id = _int(get(illust, "id", default=0))
                try:
                    related = STATE.client.illust_related(work_id)
                except PixivError as exc:
                    self._log("warn", f"种子 {work_id} 相关推荐失败：{exc}")
                    continue
                for candidate in get(related, "illusts", default=[]) or []:
                    self._add_pool_candidate(candidate)
        return [name for _weight, name in ranked]

    def _add_pool_candidate(self, illust):
        work_id = _int(get(illust, "id", default=0))
        if work_id <= 0 or work_id in self.seen_ids or work_id in self._pool_ids or work_id in self.seed_ids:
            return
        if not is_ai_work(illust):
            return
        if not passes_filters(illust, bool(self.config.get("r18")), "all", int(self.config.get("min_bookmarks") or 0)):
            return
        self._pool_ids.add(work_id)
        self._pool.append(illust)

    def _load_words(self):
        mode = self.config.get("mode") or "tag"
        if mode == "related":
            self._words = []
            seed_ids = list(self.config.get("ids") or [])[:10]
            crawl_config = {
                "r18": bool(self.config.get("r18")),
                "work_type": "all",
                "min_bookmarks": int(self.config.get("min_bookmarks") or 0),
                "batch_size": self.batch_size,
                "skip_existing": False,
                "ai_only": True,
            }
            self._related_crawl = RelatedCrawl(
                f"{self.id}-related", seed_ids, crawl_config
            )
            self._related_pending = []
            self._log("info", f"相关推荐扫描：从 {len(self._related_crawl.seed_ids_used)} 个种子开始")
            return
        words = []
        if mode == "similar":
            tags = self._collect_seed_tags()
            limit = int(self.config.get("seed_tag_limit") or 6)
            for tag in tags[:limit]:
                words.append(f"{tag} AI生成")
            for tag in tags[: max(1, limit // 2)]:
                words.append(f"{tag} AIイラスト")
        else:
            tags = list(self.config.get("tags") or [])
            base = " ".join(tags)
            if any(token in base.lower() for token in ("ai生成", "aiイラスト")):
                words.append(base)
            else:
                words.extend(f"{base} {suffix}" for suffix in AI_SEARCH_SUFFIXES)
                words.append(base)
                if len(tags) > 1:
                    for tag in tags[:4]:
                        words.append(f"{tag} AI生成")

        deduped = []
        seen_words = set()
        for word in words:
            word = str(word or "").strip()
            if not word or word.lower() in seen_words:
                continue
            seen_words.add(word.lower())
            deduped.append(word)
        if not deduped:
            deduped = ["AI生成"]
        self._words = deduped
        preview = " / ".join(deduped[:6]) + (" …" if len(deduped) > 6 else "")
        self._log("info", f"搜索词：{preview}")

    # -- 发现 --------------------------------------------------------------

    def _drain_pool(self, batch):
        while self._pool and len(batch) < self.batch_size:
            illust = self._pool.pop(0)
            work_id = _int(get(illust, "id", default=0))
            if work_id in self.seen_ids or work_id in self.seed_ids:
                continue
            self.seen_ids.add(work_id)
            batch.append(illust)

    def _discover_related_batch(self, batch):
        """相关推荐模式：沿 related 队列找 AI 作品，供扫描批次使用。"""
        if self._related_crawl is None:
            return batch
        attempts = 0
        pending = self._related_pending
        while len(batch) < self.batch_size and not self.cancel_event.is_set():
            while pending and len(batch) < self.batch_size:
                illust = pending.pop(0)
                work_id = _int(get(illust, "id", default=0))
                if work_id <= 0 or work_id in self.seen_ids or work_id in self.seed_ids:
                    continue
                self.seen_ids.add(work_id)
                batch.append(illust)
            if len(batch) >= self.batch_size:
                break
            data = self._related_crawl.next_batch(max(30, self.batch_size * 4))
            items = data.get("items") or []
            if not items and data.get("exhausted"):
                self._log("info", "相关推荐队列已走完")
                break
            pending.extend(items)
            attempts += 1
            if attempts > max(6, self.batch_size):
                break
            if not items:
                self.cancel_event.wait(0.8)
        return batch

    def _discover_batch(self):
        batch = []
        if self.config.get("mode") == "related":
            return self._discover_related_batch(batch)
        self._drain_pool(batch)
        attempts = 0
        max_attempts = max(10, self.batch_size * 2)
        while len(batch) < self.batch_size and not self.cancel_event.is_set() and attempts < max_attempts:
            self._drain_pool(batch)
            if len(batch) >= self.batch_size:
                break
            word = self._words[self._word_cursor % len(self._words)]
            self._word_cursor += 1
            next_url = self._word_next.get(word)
            try:
                data = STATE.client.search_illust(word, sort="date_desc", page_url=next_url)
            except PixivError as exc:
                self._log("warn", f"搜索「{word}」失败：{exc}")
                self._word_next[word] = None
                attempts += 1
                self.cancel_event.wait(2.0)
                continue
            self._word_next[word] = get(data, "next_url", "nextUrl", default=None)
            illusts = get(data, "illusts", default=[]) or []
            if not illusts:
                self._word_next[word] = None
            for illust in illusts:
                self._add_pool_candidate(illust)
            self._drain_pool(batch)
            attempts += 1
            if len(batch) < self.batch_size:
                self.cancel_event.wait(0.6)
        return batch

    # -- 下载 + 检查 -------------------------------------------------------

    def _run_batch(self, illusts):
        self.batch_index += 1
        index = self.batch_index
        batch_dir = os.path.join(self.session_dir, f"batch_{index:03d}")
        os.makedirs(batch_dir, exist_ok=True)
        works = [{
            "id": _int(get(illust, "id", default=0)),
            "title": str(get(illust, "title", default="") or ""),
            "page_count": _int(get(illust, "page_count", "pageCount", default=0), 0),
        } for illust in illusts]

        with self.lock:
            self.current_batch = [{
                "id": work["id"], "title": work["title"], "state": "queued",
                "pages": work["page_count"], "pages_done": 0, "hit": False,
            } for work in works]
            self.phase = "downloading"
        self._log("info", f"第 {index} 批：下载 {len(works)} 个 AI 作品")

        job = DownloadJob(
            f"scan-{self.id}-{index}",
            works,
            concurrency=int(self.config.get("concurrency") or 4),
            pages_limit=int(self.config.get("pages_limit") or 0),
            skip_existing=False,
        )
        job.output_dir = batch_dir
        job._log = lambda level, text: self._log(level, f"[批次{index}] {text}")  # noqa: E731
        self.downloader = job
        try:
            job.run()
        finally:
            self.downloader = None

        with self.lock:
            self.phase = "inspecting"
            self.downloaded_total += job.done_works
            self.failed_total += job.failed_works

        records = []
        batch_hits = 0
        item_hit = {}
        for item in list(job._items):
            if item.get("state") == "done" and item.get("dir"):
                record = self._inspect_work(item, index)
                if record is None:
                    continue
                records.append(record)
                item_hit[record["id"]] = bool(record.get("has_metadata"))
                with self.lock:
                    self.inspected_total += 1
                    if record.get("has_metadata"):
                        self._relocate_hit(record)
                        self.hits_total += 1
                        batch_hits += 1
                        self.hits.append(self._hit_summary(record))
                        exposure = record.get("exposure") or {}
                        self._log("warn", f"命中元数据 {record['id']}《{record['title'][:24]}》：{exposure.get('summary') or ', '.join(record.get('fields', {}).keys())[:80]}")
            elif item.get("state") == "failed":
                self._log("warn", f"作品 {item['id']} 下载失败：{item.get('error') or '未知错误'}")

        with self.lock:
            self.works.extend(records)
            self.batches.append({
                "index": index,
                "dir": os.path.relpath(batch_dir, STATE.output_dir).replace("\\", "/"),
                "works": len(works),
                "downloaded": job.done_works,
                "hits": batch_hits,
            })
            for entry in self.current_batch:
                entry["hit"] = item_hit.get(entry["id"], False)
                job_item = next((it for it in job._items if it["id"] == entry["id"]), None)
                if job_item is not None:
                    entry["state"] = job_item.get("state") or entry["state"]
                    entry["pages"] = job_item.get("pages") or entry["pages"]
                    entry["pages_done"] = job_item.get("pages_done") or 0
                if entry["hit"]:
                    entry["state"] = "hit"
        self._write_report()
        self._log("info", f"第 {index} 批完成：下载 {job.done_works}，命中 {batch_hits}")

    def _inspect_work(self, item, batch_index):
        work_id = item["id"]
        work_dir = item["dir"]
        detail = item.get("_detail") or {}
        try:
            files = sorted(
                name for name in os.listdir(work_dir)
                if IMAGE_FILE_RE.match(name) and not name.endswith(".part")
            )
        except OSError as exc:
            self._log("warn", f"检查 {work_id} 时无法读取目录：{exc}")
            return None

        file_results = []
        markers = set()
        fields = {}
        evidence = ""
        for name in files:
            path = os.path.join(work_dir, name)
            if _inspect_image is None:
                result = {"ok": False, "error": "metadata_inspect.py 未加载", "format": "unknown",
                          "has_metadata": False, "generation_markers": [], "fields": {}, "evidence": ""}
            else:
                try:
                    result = _inspect_image(path)
                except Exception as exc:  # noqa: BLE001
                    result = {"ok": False, "error": str(exc), "format": "unknown",
                              "has_metadata": False, "generation_markers": [], "fields": {}, "evidence": ""}
            has = bool(result.get("has_metadata"))
            file_markers = [str(marker) for marker in (result.get("generation_markers") or [])]
            markers.update(file_markers)
            result_fields = result.get("fields") or {}
            for key, value in list(result_fields.items())[:12]:
                full_key = f"{name}:{key}"
                if len(fields) < 16 and full_key not in fields:
                    fields[full_key] = str(value)[:4000]
            if has and not evidence:
                evidence = str(result.get("evidence") or "")[:300]
            file_results.append({
                "file": name,
                "format": result.get("format"),
                "has_metadata": has,
                "markers": file_markers[:12],
                "fields": list(result_fields.keys())[:12],
                "evidence": str(result.get("evidence") or "")[:300],
                "error": result.get("error"),
            })

        has_metadata = any(entry["has_metadata"] for entry in file_results)
        tags = [pair.get("name") for pair in illust_tag_pairs(detail)]
        sorted_markers = sorted(markers)
        exposure = self._describe_exposure(file_results, fields, sorted_markers) if has_metadata else {
            "level": "无", "summary": "", "categories": [], "field_count": 0, "sources": [], "files": 0,
        }
        record = {
            "id": work_id,
            "title": str(item.get("title") or ""),
            "author": illust_author(detail),
            "type": str(get(detail, "type", default="illust") or "illust"),
            "ai_type": _int(get(detail, "illust_ai_type", "illustAiType", default=0)),
            "page_count": _int(get(detail, "page_count", "pageCount", default=len(file_results)), len(file_results)),
            "x_restrict": _int(get(detail, "x_restrict", "xRestrict", default=0)),
            "tags": tags[:30],
            "batch": batch_index,
            "dir": os.path.relpath(work_dir, STATE.output_dir).replace("\\", "/"),
            "thumb_url": illust_thumb_url(detail),
            "has_metadata": has_metadata,
            "markers": sorted_markers,
            "fields": fields,
            "evidence": evidence,
            "exposure": exposure,
            "files": file_results,
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        }
        self._write_metadata_record(work_dir, record)
        return record

    def _hit_summary(self, record):
        return {
            "id": record["id"],
            "title": record["title"],
            "author": record.get("author") or {},
            "ai_type": record.get("ai_type"),
            "x_restrict": record.get("x_restrict"),
            "batch": record.get("batch"),
            "thumb_url": record.get("thumb_url") or "",
            "markers": list(record.get("markers") or [])[:8],
            "field_keys": list((record.get("fields") or {}).keys())[:6],
            "field_count": len(record.get("fields") or {}),
            "evidence": record.get("evidence") or "",
            "exposure": record.get("exposure") or {},
            "dir": record.get("dir") or "",
            "isolated": bool(record.get("isolated")),
            "page_count": record.get("page_count"),
        }

    # -- 报告 --------------------------------------------------------------

    @staticmethod
    def _atomic_write_text(path, text):
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, path)
        except OSError:
            _silent_remove(tmp)

    def _write_report(self):
        if not self.session_dir:
            return
        with self.lock:
            works = list(self.works)
            batches = list(self.batches)
            stats = {
                "inspected": self.inspected_total,
                "downloaded": self.downloaded_total,
                "hits": self.hits_total,
                "failed": self.failed_total,
                "batches": self.batch_index,
            }
            config = {
                "mode": self.config.get("mode"),
                "tags": list(self.config.get("tags") or []),
                "ids": list(self.config.get("ids") or []),
                "r18": bool(self.config.get("r18")),
                "min_bookmarks": int(self.config.get("min_bookmarks") or 0),
                "pages_limit": int(self.config.get("pages_limit") or 0),
                "batch_size": self.batch_size,
            }
        payload = {
            "scan_id": self.id,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.started_at / 1000.0)),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "state": self.state,
            "session": self.session_rel,
            "config": config,
            "stats": stats,
            "batches": batches,
            "works": works,
        }
        self._atomic_write_text(
            self.report_path,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        self._atomic_write_text(os.path.join(self.session_dir, "report.md"), self._build_markdown(payload))

    def _build_markdown(self, payload):
        lines = [
            "# AI 元数据扫描报告",
            "",
            f"- 开始时间：{payload['started_at']}",
            f"- 扫描方向：{'按作品找相似' if payload['config']['mode'] == 'similar' else '按标签搜索'}",
            f"- 条件：{json.dumps(payload['config'], ensure_ascii=False)}",
            f"- 批次：{payload['stats']['batches']}，下载 {payload['stats']['downloaded']} 个，检查 {payload['stats']['inspected']} 个，命中 {payload['stats']['hits']} 个",
            "",
            "## 命中作品",
            "",
        ]
        hits = [work for work in payload["works"] if work.get("has_metadata")]
        if not hits:
            lines.append("本次没有发现残留生成参数。")
        for work in hits:
            lines.append(f"### [{work['id']}](https://www.pixiv.net/artworks/{work['id']}) {work.get('title') or ''}")
            lines.append("")
            lines.append(f"- 作者：{(work.get('author') or {}).get('name') or '未知'}")
            lines.append(f"- 页数：{work.get('page_count')}　批次：{work.get('batch')}")
            lines.append(f"- 目录：{work.get('dir')}")
            exposure = work.get("exposure") or {}
            if exposure.get("summary"):
                lines.append(f"- 暴露情况（{exposure.get('level') or '?'}）：{exposure['summary']}")
            if work.get("markers"):
                lines.append(f"- 特征：{', '.join(work['markers'])}")
            if work.get("fields"):
                lines.append(f"- 字段：{', '.join(list(work['fields'].keys())[:12])}")
                lines.append("- 原始字段值（截断）：")
                for key, value in list(work["fields"].items())[:12]:
                    cleaned = str(value)[:800].replace("\n", " ").replace("\r", " ")
                    lines.append(f"  - `{key}`：{cleaned}")
            if work.get("evidence"):
                lines.append(f"- 证据：{work['evidence']}")
            lines.append("")
        lines.append("## 未命中的作品")
        lines.append("")
        misses = [work for work in payload["works"] if not work.get("has_metadata")]
        if not misses:
            lines.append("无。")
        for work in misses:
            lines.append(f"- {work['id']} {work.get('title') or ''}")
        lines.append("")
        return "\n".join(lines)

    # -- 主流程 ------------------------------------------------------------

    def _session_size_bytes(self):
        total = 0
        try:
            for root, _dirs, files in os.walk(self.session_dir):
                for name in files:
                    try:
                        total += os.path.getsize(os.path.join(root, name))
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    def run(self):
        try:
            self._prepare()
            while not self.cancel_event.is_set():
                max_batches = int(self.config.get("max_batches") or 0)
                if max_batches and self.batch_index >= max_batches:
                    self._log("info", f"已达到设置的最大批次 {max_batches}，停止扫描")
                    break
                max_disk_gb = float(self.config.get("max_disk_gb") or 0)
                if max_disk_gb and self._session_size_bytes() >= max_disk_gb * 1024 ** 3:
                    self._log("warn", f"扫描目录已达到 {max_disk_gb:g} GB 上限，停止扫描")
                    break
                self.phase = "discovering"
                batch = self._discover_batch()
                if self.cancel_event.is_set():
                    break
                if not batch:
                    self._log("warn", "本轮没有发现新的 AI 作品，10 秒后重试")
                    self.phase = "waiting"
                    self.cancel_event.wait(10)
                    continue
                self._run_batch(batch)
                self.cancel_event.wait(1.5)
        except PixivError as exc:
            with self.lock:
                self.state = "error"
                self.error = str(exc)
            self._log("error", f"扫描中止：{exc}")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            with self.lock:
                self.state = "error"
                self.error = str(exc)
            self._log("error", f"扫描异常：{exc}")
        finally:
            downloader = self.downloader
            if downloader is not None:
                downloader.cancel_event.set()
            with self.lock:
                if self.state == "running":
                    self.state = "stopped" if self.cancel_event.is_set() else "done"
                self.phase = "finished"
                self.finished_at = now_ms()
                self.downloader = None
            try:
                self._write_report()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            self._log("info", f"扫描结束：下载 {self.downloaded_total} 个，检查 {self.inspected_total} 个，命中 {self.hits_total} 个")
            with STATE.scans_lock:
                if STATE.active_scan is self:
                    STATE.active_scan = None


def normalize_scan_config(payload):
    mode = str(payload.get("mode") or "tag").lower()
    if mode not in ("tag", "similar", "related"):
        raise PixivError(f"不支持的扫描方向：{mode}", 400)
    tags = parse_tags(payload.get("tags"))
    ids = parse_ids(payload.get("ids"))[:10]
    if mode == "tag" and not tags:
        raise PixivError("AI 扫描需要至少一个标签", 400)
    if mode in ("similar", "related") and not ids:
        raise PixivError("AI 扫描需要至少一个种子作品 ID", 400)
    default_batch = _clamp_int(STATE.settings.get("scan_batch_size"), 1, 50, 10)
    max_batches = _clamp_int(
        payload.get("max_batches", STATE.settings.get("scan_max_batches")), 0, 1000,
        int(STATE.settings.get("scan_max_batches") or 0),
    )
    try:
        max_disk_gb = max(0.0, float(payload.get("max_disk_gb", STATE.settings.get("scan_max_disk_gb", 0))))
    except (TypeError, ValueError):
        max_disk_gb = float(STATE.settings.get("scan_max_disk_gb") or 0)
    return {
        "mode": mode,
        "tags": tags[:10],
        "ids": ids,
        "r18": _bool(payload.get("r18"), False),
        "min_bookmarks": max(0, _int(payload.get("min_bookmarks"), 0)),
        "seed_tag_limit": _clamp_int(payload.get("seed_tag_limit"), 1, 12, 6),
        "include_related": _bool(payload.get("include_related"), True),
        "pages_limit": max(0, _int(payload.get("pages_limit"), 0)),
        "concurrency": _clamp_int(payload.get("concurrency"), 1, 8, 4),
        "batch_size": _clamp_int(payload.get("batch_size"), 1, 50, default_batch),
        "max_batches": max_batches,
        "max_disk_gb": max_disk_gb,
        "skip_scanned": _bool(payload.get("skip_scanned"), True),
    }


def api_scan_start(payload):
    config = normalize_scan_config(payload)
    if not STATE.client.refresh_token and not STATE.key_data.get("refresh_token"):
        raise PixivError("尚未连接 Pixiv，请先填写 refresh_token", 401)
    with STATE.jobs_lock:
        active = STATE.active_job
        if active is not None and active.is_running():
            raise PixivError("普通下载任务进行中，请先等待完成", 409)
    with STATE.scans_lock:
        scan = STATE.active_scan
        if scan is not None and scan.is_running():
            raise PixivError("已有 AI 元数据扫描在运行", 409)
        scan_id = uuid.uuid4().hex[:12]
        scan = ScanJob(scan_id, config)
        STATE.scans[scan_id] = scan
        STATE.active_scan = scan
        finished = [(sid, item) for sid, item in STATE.scans.items() if not item.is_running()]
        finished.sort(key=lambda pair: pair[1].created_at)
        for sid, _item in finished[: max(0, len(STATE.scans) - 10)]:
            STATE.scans.pop(sid, None)
    threading.Thread(target=scan.run, name=f"scan-{scan_id}", daemon=True).start()
    safe_print(f"[扫描] 创建 AI 元数据扫描 {scan_id}", flush=True)
    return {"ok": True, "scan_id": scan_id}


def api_scan_snapshot(scan_id):
    with STATE.scans_lock:
        scan = STATE.scans.get(scan_id)
    if scan is None:
        raise PixivError("扫描任务不存在", 404)
    return {"ok": True, "scan": scan.snapshot()}


def api_scan_stop(scan_id):
    with STATE.scans_lock:
        scan = STATE.scans.get(scan_id)
    if scan is None:
        raise PixivError("扫描任务不存在", 404)
    if not scan.is_running():
        raise PixivError("扫描已经结束", 400)
    scan.stop()
    return {"ok": True}


def api_scan_active():
    with STATE.scans_lock:
        scan = STATE.active_scan
    if scan is None:
        return {"ok": True, "scan_id": None, "scan": None}
    return {"ok": True, "scan_id": scan.id, "scan": scan.snapshot()}


def api_scan_hit(scan_id, work_id):
    """按需返回单个命中作品的完整元数据，供前端展开查看。"""
    with STATE.scans_lock:
        scan = STATE.scans.get(scan_id)
    if scan is None:
        raise PixivError("扫描任务不存在", 404)
    record = scan.get_work(work_id)
    if record is None:
        raise PixivError("该扫描记录里没有这个作品", 404)
    return {"ok": True, "hit": record}


# --- 历史扫描 ---------------------------------------------------------------

def _scan_history_root():
    return os.path.join(STATE.output_dir, "AI元数据扫描")


def _validate_scan_session(session):
    name = str(session or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise PixivError("非法的扫描会话名", 400)
    root = os.path.abspath(_scan_history_root())
    path = os.path.abspath(os.path.join(root, name))
    if not path.lower().startswith(root.lower() + os.sep):
        raise PixivError("非法的扫描会话路径", 400)
    if not os.path.isdir(path):
        raise PixivError("扫描会话不存在", 404)
    return name, path


def _load_scan_report(session):
    name, path = _validate_scan_session(session)
    report = os.path.join(path, "report.json")
    if not os.path.isfile(report):
        raise PixivError("该扫描会话没有 report.json", 404)
    try:
        with open(report, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise PixivError(f"读取扫描报告失败：{exc}", 500) from exc
    if not isinstance(data, dict):
        raise PixivError("扫描报告格式不正确", 500)
    return name, path, data


def _report_hit_summary(work):
    return {
        "id": _int(work.get("id"), 0),
        "title": str(work.get("title") or ""),
        "author": work.get("author") or {},
        "batch": work.get("batch"),
        "thumb_url": work.get("thumb_url") or "",
        "markers": list(work.get("markers") or [])[:8],
        "field_keys": list((work.get("fields") or {}).keys())[:6],
        "field_count": len(work.get("fields") or {}),
        "evidence": work.get("evidence") or "",
        "exposure": work.get("exposure") or {},
        "dir": work.get("dir") or "",
        "page_count": work.get("page_count"),
        "ai_type": work.get("ai_type"),
        "x_restrict": work.get("x_restrict"),
    }


def api_scan_history():
    root = _scan_history_root()
    sessions = []
    try:
        entries = [entry for entry in os.scandir(root) if entry.is_dir()]
    except OSError:
        entries = []
    entries.sort(key=lambda entry: entry.name, reverse=True)
    limit = _clamp_int(STATE.settings.get("history_limit"), 5, 200, 30)
    for entry in entries[:limit]:
        report = os.path.join(entry.path, "report.json")
        if not os.path.isfile(report):
            continue
        try:
            with open(report, encoding="utf-8") as handle:
                data = json.load(handle)
            stats = data.get("stats") or {}
            config = data.get("config") or {}
            sessions.append({
                "session": entry.name,
                "started_at": data.get("started_at") or "",
                "updated_at": data.get("updated_at") or "",
                "state": data.get("state") or "",
                "stats": stats,
                "mode": config.get("mode") or "",
                "tags": config.get("tags") or [],
                "ids": config.get("ids") or [],
                "batch_size": config.get("batch_size") or 0,
            })
        except (OSError, ValueError):
            continue
    return {"ok": True, "sessions": sessions}


def api_scan_history_hits(session, query, offset=0, limit=20, level=""):
    name, path, data = _load_scan_report(session)
    works = [work for work in (data.get("works") or []) if work.get("has_metadata")]
    needle = str(query or "").strip().lower()
    if needle:
        def match(work):
            blob = " ".join([
                str(work.get("title") or ""),
                str(work.get("id") or ""),
                " ".join((work.get("fields") or {}).keys()),
                " ".join(work.get("markers") or []),
                str(work.get("evidence") or ""),
            ]).lower()
            return needle in blob
        works = [work for work in works if match(work)]
    if level:
        works = [work for work in works
                 if str((work.get("exposure") or {}).get("level") or "") == level]
    works.sort(key=lambda work: _int(work.get("id"), 0))
    total = len(works)
    offset = max(0, min(offset, total))
    limit = max(1, min(limit, 100))
    page = works[offset:offset + limit]
    return {
        "ok": True,
        "session": name,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [_report_hit_summary(work) for work in page],
        "report": {
            "started_at": data.get("started_at") or "",
            "stats": data.get("stats") or {},
            "mode": (data.get("config") or {}).get("mode") or "",
        },
    }


def api_scan_history_hit(session, work_id):
    _name, _path, data = _load_scan_report(session)
    for work in data.get("works") or []:
        if _int(work.get("id"), 0) == _int(work_id, 0):
            return {"ok": True, "hit": work}
    raise PixivError("该扫描报告里没有这个作品", 404)


def api_scan_history_export(session, fmt="csv"):
    _name, _path, data = _load_scan_report(session)
    works = [work for work in (data.get("works") or []) if work.get("has_metadata")]
    fmt = (fmt or "csv").lower()
    if fmt == "json":
        return {
            "ok": True,
            "filename": f"{session}_hits.json",
            "content": json.dumps(works, ensure_ascii=False, indent=2),
            "content_type": "application/json; charset=utf-8",
        }
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "title", "author", "level", "batch", "field_count",
                     "fields", "markers", "exposure", "dir", "pixiv_url"])
    for work in works:
        exposure = work.get("exposure") or {}
        writer.writerow([
            work.get("id"),
            work.get("title") or "",
            (work.get("author") or {}).get("name") or "",
            exposure.get("level") or "",
            work.get("batch") or "",
            len(work.get("fields") or {}),
            " | ".join((work.get("fields") or {}).keys()),
            " | ".join(work.get("markers") or []),
            exposure.get("summary") or "",
            work.get("dir") or "",
            f"https://www.pixiv.net/artworks/{work.get('id')}",
        ])
    return {
        "ok": True,
        "filename": f"{session}_hits.csv",
        "content": output.getvalue(),
        "content_type": "text/csv; charset=utf-8",
    }


def api_job_retry(job_id):
    with STATE.jobs_lock:
        job = STATE.jobs.get(job_id)
        if job is None:
            raise PixivError("任务不存在", 404)
        if job.is_running():
            raise PixivError("任务还在运行，不能重试", 409)
        failed = [item for item in job._items if item.get("state") == "failed" and item.get("id")]
        if not failed:
            raise PixivError("没有需要重试的失败作品", 400)
        active = STATE.active_job
        if active is not None and active.is_running():
            raise PixivError("已有任务在运行", 409)
        works = [{
            "id": item["id"],
            "title": item.get("title") or "",
            "page_count": item.get("pages") or 0,
        } for item in failed]
        new_id = uuid.uuid4().hex[:12]
        new_job = DownloadJob(
            new_id, works,
            concurrency=job.concurrency,
            pages_limit=job.pages_limit,
            skip_existing=False,
        )
        STATE.jobs[new_id] = new_job
        STATE.active_job = new_job
    threading.Thread(target=new_job.run, name=f"job-{new_id}", daemon=True).start()
    safe_print(f"[任务] 重试 {len(works)} 个失败作品，新任务 {new_id}", flush=True)
    return {"ok": True, "job_id": new_id, "retry_count": len(works)}


# ---------------------------------------------------------------------------
# 业务处理函数（供 HTTP 层调用）
# ---------------------------------------------------------------------------

def api_config():
    key_data = STATE.key_data or {}
    token = str(key_data.get("refresh_token") or "")
    account = str(key_data.get("account") or "")
    user = STATE.client.user or None
    return {
        "ok": True,
        "user": user,
        "has_key": bool(token),
        "key_file": STATE.key_path or KEY_FILE_IN_DIR,
        "output_dir": STATE.output_dir,
        "version": APP_VERSION,
        "default_token": token,
        "key_account": account,
        "api_token": STATE.api_token,
        "settings": settings_snapshot(),
    }


def api_connect(payload):
    token = str(payload.get("refresh_token") or "").strip()
    if not token:
        raise PixivError("请填写 refresh_token", 400)
    remember = _bool(payload.get("remember"), False)
    user = STATE.client.login(token)
    saved_path = None
    if remember:
        saved_path = save_key_file(STATE.client.refresh_token or token, user.get("account") or "")
    display = user.get("name") or user.get("account") or ""
    return {
        "ok": True,
        "user": user,
        "message": f"已连接 {display}".strip(),
        "key_file": saved_path or STATE.key_path,
    }


# --- 通行密钥提取（OAuth2 PKCE + 本机工具缓存导入） -----------------------

TOKEN_EXTRACT_LOGIN_URL = "https://app-api.pixiv.net/web/v1/login"
TOKEN_EXTRACT_CALLBACK_URI = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
TOKEN_LOGIN_HELPER = os.path.join(BASE_DIR, "token_login.py")
TOKEN_EXTRACT_HEADERS = {
    "User-Agent": "PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)",
    "app-os-version": "14.6",
    "app-os": "ios",
    "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8",
}


def _generate_pkce():
    verifier = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _parse_auth_code(text):
    pasted = str(text or "").strip()
    if not pasted:
        raise PixivError("请粘贴授权码或回调 URL", 400)
    if "code=" in pasted:
        query = pasted.split("?", 1)[1] if "?" in pasted else pasted
        values = urllib.parse.parse_qs(query).get("code") or []
        code = values[0].strip() if values else ""
    else:
        code = pasted
    if not code or any(character.isspace() for character in code):
        raise PixivError("没有在粘贴内容里找到授权码（code），请复制完整回调 URL 或 code 值", 400)
    return code


def _new_pkce_session():
    """创建一个 PKCE 会话，返回 (session_id, login_url)。"""
    now = time.time()
    with STATE.pkce_lock:
        for session_id, old in list(STATE.pkce_sessions.items()):
            if now - old["created_at"] > 1200:
                STATE.pkce_sessions.pop(session_id, None)
        verifier, challenge = _generate_pkce()
        session_id = uuid.uuid4().hex
        STATE.pkce_sessions[session_id] = {"verifier": verifier, "created_at": now}
    params = urllib.parse.urlencode({
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "client": "pixiv-android",
    })
    return session_id, f"{TOKEN_EXTRACT_LOGIN_URL}?{params}"


def _extract_key_from_code(code_text, verifier):
    """用授权码 + code_verifier 换 refresh_token（手动/内置登录窗口共用）。"""
    code = _parse_auth_code(code_text)
    http = build_http_session()
    try:
        response = http.post(
            OAUTH_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "include_policy": "true",
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
                "redirect_uri": TOKEN_EXTRACT_CALLBACK_URI,
            },
            headers=TOKEN_EXTRACT_HEADERS,
            timeout=25,
        )
    except requests.RequestException as exc:
        raise PixivError(f"连接 Pixiv 失败：{exc}", 502) from exc
    finally:
        http.close()
    try:
        body = response.json()
    except ValueError as exc:
        raise PixivError(f"Pixiv 返回了非 JSON 响应（HTTP {response.status_code}）", 502) from exc
    if response.status_code != 200 or not body.get("access_token"):
        system_error = ((body.get("errors") or {}).get("system") or {}).get("message") or ""
        reason = body.get("error") or system_error or f"HTTP {response.status_code}"
        raise PixivError(f"授权码换取通行密钥失败（{reason}）。code 约 30 秒内有效，请重新登录再试。", 400)
    refresh_token = str(body.get("refresh_token") or "").strip()
    if not refresh_token:
        raise PixivError("Pixiv 没有返回 refresh_token，请重试", 502)
    user = normalize_user(body.get("user") or {}) or {}
    display = user.get("name") or user.get("account") or "Pixiv 账号"
    return {
        "ok": True,
        "refresh_token": refresh_token,
        "access_token": str(body.get("access_token") or ""),
        "expires_in": int(body.get("expires_in") or 0),
        "user": user,
        "message": f"已提取 {display} 的通行密钥",
    }


def api_token_extract_start(payload):
    """生成一次手动 PKCE 提取会话，返回需要在浏览器打开的 Pixiv 授权地址。"""
    session_id, login_url = _new_pkce_session()
    return {
        "ok": True,
        "session_id": session_id,
        "login_url": login_url,
        "expires_in": 1200,
    }


def api_token_extract_finish(payload):
    """用浏览器登录后拿到的授权码换取 refresh_token。"""
    session_id = str(payload.get("session_id") or "").strip()
    code_text = str(payload.get("code") or payload.get("url") or "").strip()
    if not session_id:
        raise PixivError("提取会话已失效，请重新打开 Pixiv 登录页", 400)
    with STATE.pkce_lock:
        pkce = STATE.pkce_sessions.pop(session_id, None)
    if pkce is None:
        raise PixivError("提取会话不存在或已过期，请重新打开 Pixiv 登录页", 400)
    return _extract_key_from_code(code_text, pkce["verifier"])


# --- 内置登录窗口（pywebview，一键抓取授权码） --------------------------

def _cleanup_auto_logins(now=None):
    now = time.time() if now is None else now
    with STATE.auto_login_lock:
        for session_id, record in list(STATE.auto_logins.items()):
            if now - record["created_at"] <= 1200:
                continue
            proc = record.get("proc")
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except OSError:
                    pass
            STATE.auto_logins.pop(session_id, None)


def _watch_auto_login(session_id, proc):
    captured = ""
    helper_error = ""
    try:
        if proc.stdout is not None:
            for raw in proc.stdout:
                line = str(raw).strip()
                if line.startswith("CODE:"):
                    captured = line[5:].strip()
                    break
                if line.startswith("ERROR:"):
                    helper_error = line[6:].strip()
    except (OSError, ValueError):
        pass
    finally:
        try:
            proc.wait(timeout=8)
        except (subprocess.TimeoutExpired, OSError):
            try:
                proc.terminate()
            except OSError:
                pass
    with STATE.auto_login_lock:
        record = STATE.auto_logins.get(session_id)
    if record is None:
        return
    if not captured:
        if record.get("state") != "error":
            record["state"] = "error"
            record["error"] = helper_error or "登录窗口已关闭，还没有完成 Pixiv 登录"
        return
    try:
        result = _extract_key_from_code(captured, record["verifier"])
    except PixivError as exc:
        record["state"] = "error"
        record["error"] = exc.message
        return
    except Exception as exc:  # noqa: BLE001
        record["state"] = "error"
        record["error"] = f"提取失败：{exc}"
        return
    record["state"] = "done"
    record["result"] = result


def api_token_extract_auto_start(payload):
    """启动内置 pywebview 登录窗口，登录完成后自动抓取授权码。"""
    if not os.path.isfile(TOKEN_LOGIN_HELPER):
        raise PixivError("内置登录窗口脚本缺失，请用「从本机工具导入」或手动粘贴", 501)
    if importlib.util.find_spec("webview") is None:
        raise PixivError("未安装 pywebview，无法打开内置登录窗口；请用「从本机工具导入」或手动粘贴", 501)
    _cleanup_auto_logins()
    session_id, login_url = _new_pkce_session()
    with STATE.pkce_lock:
        pkce = STATE.pkce_sessions.pop(session_id, None)
    if not pkce:
        raise PixivError("创建登录会话失败，请重试", 500)

    with STATE.auto_login_lock:
        for old_id, old in list(STATE.auto_logins.items()):
            proc = old.get("proc")
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except OSError:
                    pass
            STATE.auto_logins.pop(old_id, None)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            proc = subprocess.Popen(
                [sys.executable, "-u", TOKEN_LOGIN_HELPER, login_url],
                cwd=BASE_DIR,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
        except OSError as exc:
            raise PixivError(f"无法启动登录窗口：{exc}", 500) from exc
        STATE.auto_logins[session_id] = {
            "state": "running",
            "error": "",
            "result": None,
            "verifier": pkce["verifier"],
            "created_at": time.time(),
            "proc": proc,
        }
        STATE.auto_login_proc = proc
    threading.Thread(target=_watch_auto_login, args=(session_id, proc),
                     name=f"auto-login-{session_id[:8]}", daemon=True).start()
    safe_print(f"[密钥] 已打开内置 Pixiv 登录窗口（{session_id[:8]}）", flush=True)
    return {
        "ok": True,
        "session_id": session_id,
        "login_url": login_url,
        "expires_in": 600,
        "message": "登录窗口已打开",
    }


def _auto_login_public(session_id):
    with STATE.auto_login_lock:
        record = STATE.auto_logins.get(session_id)
        if record is None:
            raise PixivError("登录会话不存在或已过期，请重新打开登录窗口", 404)
        state = record["state"]
        if state == "running":
            return {"ok": True, "state": "running"}
        if state == "error":
            return {"ok": False, "state": "error",
                    "error": record.get("error") or "登录未完成"}
        result = record.get("result") or {}
        return {
            "ok": True,
            "state": "done",
            "refresh_token": result.get("refresh_token") or "",
            "user": result.get("user") or {},
            "message": result.get("message") or "已提取通行密钥",
        }


def api_token_extract_auto_status(session_id):
    return _auto_login_public(str(session_id or "").strip())


def api_token_extract_auto_cancel(session_id):
    with STATE.auto_login_lock:
        record = STATE.auto_logins.get(str(session_id or "").strip())
        if record is None:
            return {"ok": True}
        proc = record.get("proc")
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
        record["state"] = "error"
        record["error"] = "已取消登录"
    return {"ok": True}


def _refresh_token_from_json(data, depth=0):
    if depth > 2 or not isinstance(data, dict):
        return None
    for key in ("refresh_token", "refreshToken", "refresh-token", "RefreshToken"):
        value = data.get(key)
        if isinstance(value, str) and len(value.strip()) >= 8:
            return value.strip()
    for value in data.values():
        if isinstance(value, dict):
            found = _refresh_token_from_json(value, depth + 1)
            if found:
                return found
    return None


def _token_account_from_json(data):
    if not isinstance(data, dict):
        return ""
    user = data.get("user")
    if isinstance(user, dict):
        for key in ("account", "name"):
            value = str(user.get(key) or "").strip()
            if value:
                return value
    for key in ("account", "user_account", "user_name", "username", "name"):
        value = str(data.get(key) or "").strip()
        if value:
            return value
    return ""


def _token_source_files():
    home = os.path.expanduser("~")
    appdata = os.environ.get("APPDATA") or ""
    localappdata = os.environ.get("LOCALAPPDATA") or ""
    desktop = os.path.join(home, "Desktop")
    exact = [
        os.path.join(BASE_DIR, "pixiv_通行密钥.json"),
        os.path.join(BASE_DIR, "pixiv_auth.json"),
        os.path.join(desktop, "pixiv_通行密钥.json"),
        os.path.join(desktop, "pixiv_auth.json"),
        os.path.join(home, ".pixiv-token", "token.json"),
        os.path.join(appdata, "osu-Ez2Lazer", "pixiv_auth.json") if appdata else "",
        os.path.join(home, ".config", "pixiv-token-getter", "tokens", "default.token.json"),
    ]
    patterns = [
        os.path.join(home, ".config", "gppt", "*.token.json"),
        os.path.join(home, ".pixiv-token", "*.json"),
        os.path.join(home, ".config", "pixiv-token-getter", "tokens", "*.token.json"),
        os.path.join(appdata, "pixiv-token-getter", "tokens", "*.token.json") if appdata else "",
        os.path.join(appdata, "gppt", "*.token.json") if appdata else "",
        os.path.join(localappdata, "pixiv-token-getter", "tokens", "*.token.json") if localappdata else "",
        os.path.join(desktop, "*", "pixiv_通行密钥.json"),
        os.path.join(desktop, "*", "pixiv_auth.json"),
    ]
    paths = []
    seen = set()
    for path in exact:
        if path and path not in seen and os.path.isfile(path):
            seen.add(path)
            paths.append(path)
    for pattern in patterns:
        if not pattern:
            continue
        for path in sorted(glob.glob(pattern)):
            if path not in seen and os.path.isfile(path):
                seen.add(path)
                paths.append(path)
    return paths


def _token_source_kind(path):
    low = path.lower()
    if "gppt" in low:
        return "gppt"
    if "pixiv-token-getter" in low:
        return "pixiv-token-getter"
    if ".pixiv-token" in low:
        return "pixiv-token"
    if "ez2lazer" in low:
        return "Ez2Lazer"
    if os.path.basename(path) == "pixiv_通行密钥.json":
        return "密钥文件"
    return "密钥文件"


def api_token_sources():
    """扫描本机常见工具的 refresh_token 缓存，供一键导入。"""
    items = []
    seen_tokens = set()
    scanned = 0
    for path in _token_source_files():
        scanned += 1
        try:
            if os.path.getsize(path) > 2 * 1024 * 1024:
                continue
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        token = _refresh_token_from_json(data)
        if not token or token in seen_tokens:
            continue
        seen_tokens.add(token)
        try:
            modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
        except OSError:
            modified = ""
        items.append({
            "source": path,
            "name": os.path.basename(path),
            "kind": _token_source_kind(path),
            "account": _token_account_from_json(data),
            "refresh_token": token,
            "masked": f"{token[:4]}…{token[-4:]}" if len(token) > 10 else "…",
            "modified": modified,
        })
        if len(items) >= 12:
            break
    return {"ok": True, "items": items, "scanned": scanned}


def api_lookup(payload):
    """按 ID 批量取作品摘要，用于「按作品找相似」左侧的种子作品预览。"""
    ids = parse_ids(payload.get("ids"))[:10]
    if not ids:
        raise PixivError("请提供作品 ID", 400)
    if not STATE.client.refresh_token and STATE.key_data.get("refresh_token"):
        STATE.client.refresh_token = STATE.key_data["refresh_token"]
    budget = ApiBudget(len(ids) + 2)
    downloaded_ids = scan_downloaded_ids()
    items = []
    errors = []
    for work_id in ids:
        try:
            detail = STATE.client.illust_detail(work_id, budget=budget)
        except PixivError as exc:
            errors.append({"id": work_id, "error": exc.message})
            continue
        items.append(build_item(detail, [], 1.0, downloaded_ids))
    return {"ok": True, "items": items, "errors": errors}


def api_download(payload):
    works = normalize_download_works(payload)
    if not works:
        raise PixivError("请提供要下载的作品（items 或 ids）", 400)
    if len(works) > 500:
        raise PixivError("一次最多下载 500 个作品", 400)
    if not STATE.client.refresh_token and not STATE.key_data.get("refresh_token"):
        raise PixivError("尚未连接 Pixiv，请先填写 refresh_token", 401)

    concurrency = _clamp_int(payload.get("concurrency"), 1, 8, 4)
    pages_limit = max(0, _int(payload.get("pages_limit"), 0))
    skip_existing = _bool(payload.get("skip_existing"), True)

    with STATE.scans_lock:
        active_scan = STATE.active_scan
        if active_scan is not None and active_scan.is_running():
            raise PixivError("AI 元数据扫描进行中，请先停止扫描", 409)

    with STATE.jobs_lock:
        active = STATE.active_job
        if active is not None and active.is_running():
            raise PixivError("已有任务在运行", 409)
        job_id = uuid.uuid4().hex[:12]
        job = DownloadJob(
            job_id, works,
            concurrency=concurrency,
            pages_limit=pages_limit,
            skip_existing=skip_existing,
        )
        STATE.jobs[job_id] = job
        STATE.active_job = job
    threading.Thread(target=job.run, name=f"job-{job_id}", daemon=True).start()
    prune_jobs()
    safe_print(f"[任务] 创建下载任务 {job_id}，作品 {len(works)} 个，并发 {concurrency}", flush=True)
    return {"ok": True, "job_id": job_id}


def api_job_snapshot(job_id):
    with STATE.jobs_lock:
        job = STATE.jobs.get(job_id)
    if job is None:
        raise PixivError("任务不存在", 404)
    return {"ok": True, "job": job.snapshot()}


def api_job_cancel(job_id):
    with STATE.jobs_lock:
        job = STATE.jobs.get(job_id)
    if job is None:
        raise PixivError("任务不存在", 404)
    if not job.is_running():
        raise PixivError("任务已结束，无法取消", 400)
    job.cancel_event.set()
    job._log("warn", "收到取消请求，正在停止…")
    return {"ok": True}


def api_open_output(payload):
    if not hasattr(os, "startfile"):
        raise PixivError("当前平台不支持自动打开文件夹（仅 Windows）", 400)
    subdir = str(payload.get("subdir") or "").strip()
    target = os.path.abspath(os.path.join(STATE.output_dir, subdir)) if subdir else os.path.abspath(STATE.output_dir)
    root = os.path.abspath(STATE.output_dir)
    if not (target == root or target.lower().startswith(root.lower() + os.sep)):
        raise PixivError("非法的子目录", 400)
    if not os.path.isdir(target):
        raise PixivError("目录不存在", 404)
    try:
        os.startfile(target)  # type: ignore[attr-defined]
    except OSError as exc:
        raise PixivError(f"打开目录失败：{exc}", 500) from exc
    return {"ok": True, "dir": target}


def api_output_stats():
    works = 0
    total_bytes = 0
    try:
        with os.scandir(STATE.output_dir) as it:
            for entry in it:
                if not entry.is_dir():
                    continue
                works += 1
                for root, _dirs, files in os.walk(entry.path):
                    for name in files:
                        try:
                            total_bytes += os.path.getsize(os.path.join(root, name))
                        except OSError:
                            pass
    except OSError as exc:
        raise PixivError(f"读取输出目录失败：{exc}", 500) from exc
    return {"ok": True, "dir": STATE.output_dir, "works": works, "bytes": total_bytes}


# ---------------------------------------------------------------------------
# 下载库：扫描 output 下的作品目录，提供筛选 / 分类 / 查看
# ---------------------------------------------------------------------------

LIBRARY_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
_library_lock = threading.RLock()
_library_cache = {"at": 0.0, "items": [], "facets": {}}
_library_thumb_lock = threading.RLock()
_library_thumbs = OrderedDict()
_library_thumb_bytes = 0
LIBRARY_THUMB_MAX_ITEMS = 120
LIBRARY_THUMB_MAX_BYTES = 60 * 1024 * 1024


def _library_tags(value):
    names = []
    if isinstance(value, list):
        for tag in value:
            if isinstance(tag, dict):
                name = str(tag.get("name") or "").strip()
            else:
                name = str(tag or "").strip()
            if name and name not in names:
                names.append(name)
    return names


def _library_exposure(record):
    exposure = record.get("exposure") if isinstance(record, dict) else None
    if not isinstance(exposure, dict):
        return {}
    return {
        "level": exposure.get("level") or "",
        "summary": exposure.get("summary") or "",
        "field_count": _int(exposure.get("field_count"), 0),
    }


def _library_source(rel_parts):
    if not rel_parts or rel_parts[0] != "AI元数据扫描":
        return "download", "", ""
    session = rel_parts[1] if len(rel_parts) > 1 else ""
    if len(rel_parts) > 2 and rel_parts[2] == "命中作品":
        return "hit", session, ""
    if len(rel_parts) > 2 and str(rel_parts[2]).startswith("batch_"):
        return "scan", session, rel_parts[2]
    return "scan", session, ""


def _library_images(work_dir, work_id, files):
    images = []
    for name in files:
        ext = os.path.splitext(name)[1].lower()
        if ext not in LIBRARY_IMAGE_EXTS:
            continue
        if name.startswith("."):
            continue
        images.append(name)

    def page_key(name):
        m = re.search(r"_p(\d+)", name, re.I)
        return (int(m.group(1)) if m else 9999, name.lower())

    images.sort(key=page_key)
    result = []
    for index, name in enumerate(images):
        rel = os.path.relpath(os.path.join(work_dir, name), STATE.output_dir).replace("\\", "/")
        quoted = urllib.parse.quote(rel, safe="")
        result.append({
            "page": index,
            "name": name,
            "url": f"/api/library/file?path={quoted}",
            "thumb": f"/api/library/file?path={quoted}&amp;thumb=1".replace("&amp;", "&"),
        })
    return result


def _library_scan(force=False):
    now = time.time()
    with _library_lock:
        if not force and _library_cache["items"] and now - _library_cache["at"] < 8:
            return _library_cache["items"], _library_cache["facets"]

    items = []
    facets = {
        "sources": {}, "types": {}, "sessions": {}, "tags": {}, "authors": {},
        "r18": {"yes": 0, "no": 0}, "hit": {"yes": 0, "no": 0},
    }
    root = os.path.abspath(STATE.output_dir)
    if os.path.isdir(root):
        for current, dirs, files in os.walk(root):
            rel_dir = os.path.relpath(current, root)
            rel_parts = [] if rel_dir == "." else rel_dir.replace("\\", "/").split("/")
            # 不进入隐藏目录/缩略图缓存
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            if "info.json" not in files:
                continue
            dirs[:] = []
            info = {}
            try:
                with open(os.path.join(current, "info.json"), encoding="utf-8") as handle:
                    info = json.load(handle)
            except (OSError, ValueError):
                info = {}
            if not isinstance(info, dict):
                info = {}
            work_id = _int(info.get("id"), 0)
            if work_id <= 0:
                m = re.match(r"(\d{4,12})_", os.path.basename(current))
                work_id = int(m.group(1)) if m else 0
            if work_id <= 0:
                continue

            source, session, batch = _library_source(rel_parts)
            meta_path = os.path.join(current, "metadata_scan.json")
            meta = {}
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, encoding="utf-8") as handle:
                        meta = json.load(handle)
                except (OSError, ValueError):
                    meta = {}
            if not isinstance(meta, dict):
                meta = {}
            is_hit = source == "hit" or bool(meta.get("has_metadata"))
            if is_hit:
                source = "hit"
            exposure = _library_exposure(meta)
            tags = _library_tags(info.get("tags")) or _library_tags(meta.get("tags"))
            author = info.get("author") if isinstance(info.get("author"), dict) else {}
            if not author:
                author = meta.get("author") if isinstance(meta.get("author"), dict) else {}
            images = _library_images(current, work_id, files)
            if not images:
                continue
            downloaded_at = str(info.get("downloaded_at") or meta.get("checked_at") or "")
            if not downloaded_at:
                try:
                    downloaded_at = time.strftime(
                        "%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(current))
                    )
                except OSError:
                    downloaded_at = ""
            total_bytes = 0
            for image in images:
                try:
                    total_bytes += os.path.getsize(
                        os.path.join(current, image["name"])
                    )
                except OSError:
                    pass
            item = {
                "id": work_id,
                "title": str(info.get("title") or meta.get("title") or f"作品 {work_id}"),
                "type": str(info.get("type") or meta.get("type") or "illust"),
                "page_count": max(1, len(images)),
                "declared_page_count": _int(info.get("page_count"), 0),
                "x_restrict": _int(info.get("x_restrict"), 0),
                "bookmarks": _int(info.get("total_bookmarks"), 0),
                "tags": tags,
                "author": {
                    "id": _int(author.get("id"), 0),
                    "name": str(author.get("name") or ""),
                    "account": str(author.get("account") or ""),
                },
                "create_date": str(info.get("create_date") or ""),
                "downloaded_at": downloaded_at,
                "source": source,
                "session": session,
                "batch": batch,
                "hit": is_hit,
                "exposure": exposure,
                "field_count": _int(exposure.get("field_count"), 0),
                "dir": rel_dir.replace("\\", "/"),
                "images": images,
                "cover": images[0]["thumb"],
                "bytes": total_bytes,
            }
            items.append(item)
            # 统计 facets
            facets["sources"][source] = facets["sources"].get(source, 0) + 1
            facets["types"][item["type"]] = facets["types"].get(item["type"], 0) + 1
            if session:
                facets["sessions"][session] = facets["sessions"].get(session, 0) + 1
            facets["r18"]["yes" if item["x_restrict"] > 0 else "no"] += 1
            facets["hit"]["yes" if is_hit else "no"] += 1
            for tag in tags:
                facets["tags"][tag] = facets["tags"].get(tag, 0) + 1
            author_name = item["author"]["name"] or "未知作者"
            facets["authors"][author_name] = facets["authors"].get(author_name, 0) + 1

    items.sort(key=lambda item: (item.get("downloaded_at") or "", item["id"]), reverse=True)
    for key in ("tags", "authors"):
        ordered = sorted(facets[key].items(), key=lambda pair: (-pair[1], pair[0]))
        facets[key] = [{"name": name, "count": count} for name, count in ordered[:60]]
    with _library_lock:
        _library_cache["at"] = now
        _library_cache["items"] = items
        _library_cache["facets"] = facets
    return items, facets


def api_library(query):
    items, facets = _library_scan(force=_bool((query.get("refresh") or ["0"])[0], False))
    q = str((query.get("q") or [""])[0] or "").strip().lower()
    source = str((query.get("source") or [""])[0] or "").strip().lower()
    work_type = str((query.get("type") or [""])[0] or "").strip().lower()
    r18 = str((query.get("r18") or [""])[0] or "").strip().lower()
    hit = str((query.get("hit") or [""])[0] or "").strip().lower()
    tag = str((query.get("tag") or [""])[0] or "").strip().lower()
    author = str((query.get("author") or [""])[0] or "").strip().lower()
    session = str((query.get("session") or [""])[0] or "").strip()
    sort = str((query.get("sort") or ["newest"])[0] or "newest").strip().lower()
    offset = _clamp_int((query.get("offset") or ["0"])[0], 0, 100000, 0)
    limit = _clamp_int((query.get("limit") or ["60"])[0], 1, 200, 60)

    filtered = []
    for item in items:
        if q:
            blob = " ".join([
                item["title"], str(item["id"]), " ".join(item["tags"]),
                item["author"]["name"], item["author"]["account"],
            ]).lower()
            if q not in blob:
                continue
        if source and source != "all" and item["source"] != source:
            continue
        if work_type and work_type != "all" and item["type"] != work_type:
            continue
        if r18 == "yes" and item["x_restrict"] <= 0:
            continue
        if r18 == "no" and item["x_restrict"] > 0:
            continue
        if hit == "yes" and not item["hit"]:
            continue
        if hit == "no" and item["hit"]:
            continue
        if tag and not any(tag == t.lower() for t in item["tags"]):
            continue
        if author and author not in item["author"]["name"].lower():
            continue
        if session and item["session"] != session:
            continue
        filtered.append(item)

    if sort == "oldest":
        filtered.sort(key=lambda item: (item.get("downloaded_at") or "", item["id"]))
    elif sort == "title":
        filtered.sort(key=lambda item: (item["title"].lower(), item["id"]))
    elif sort == "pages":
        filtered.sort(key=lambda item: (-item["page_count"], item["id"]))
    elif sort == "bookmarks":
        filtered.sort(key=lambda item: (-item["bookmarks"], item["id"]))
    elif sort == "size":
        filtered.sort(key=lambda item: (-item["bytes"], item["id"]))
    else:
        filtered.sort(key=lambda item: (item.get("downloaded_at") or "", item["id"]), reverse=True)

    total = len(filtered)
    page = filtered[offset:offset + limit]
    return {
        "ok": True,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": page,
        "facets": facets,
        "output_dir": STATE.output_dir,
        "scanned_at": int(time.time()),
    }


def _resolve_library_path(rel_path):
    rel_path = str(rel_path or "").replace("\\", "/").strip()
    if not rel_path or rel_path.startswith("/") or ".." in rel_path.split("/"):
        raise PixivError("非法的文件路径", 400)
    root = os.path.abspath(STATE.output_dir)
    target = os.path.abspath(os.path.join(root, rel_path))
    if not (target == root or target.lower().startswith(root.lower() + os.sep)):
        raise PixivError("非法的文件路径", 400)
    if not os.path.isfile(target):
        raise PixivError("文件不存在", 404)
    if os.path.splitext(target)[1].lower() not in LIBRARY_IMAGE_EXTS:
        raise PixivError("只允许读取图片文件", 400)
    return target


def _library_thumb(target):
    key = (target, os.path.getmtime(target), os.path.getsize(target))
    with _library_thumb_lock:
        if key in _library_thumbs:
            data, content_type = _library_thumbs.pop(key)
            _library_thumbs[key] = (data, content_type)
            return data, content_type
    try:
        from PIL import Image  # noqa: PLC0415 - 可选依赖
    except Exception:  # noqa: BLE001
        with open(target, "rb") as handle:
            return handle.read(), MIME_TYPES.get(os.path.splitext(target)[1].lower(), "image/jpeg")
    try:
        with Image.open(target) as image:
            image.seek(0)
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, (246, 242, 233))
                background.paste(image, mask=image.split()[-1])
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((520, 520), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=84, optimize=True)
            data = output.getvalue()
    except Exception:  # noqa: BLE001
        with open(target, "rb") as handle:
            return handle.read(), MIME_TYPES.get(os.path.splitext(target)[1].lower(), "image/jpeg")
    content_type = "image/jpeg"
    with _library_thumb_lock:
        global _library_thumb_bytes
        _library_thumbs[key] = (data, content_type)
        _library_thumb_bytes += len(data)
        while _library_thumbs and (
            len(_library_thumbs) > LIBRARY_THUMB_MAX_ITEMS
            or _library_thumb_bytes > LIBRARY_THUMB_MAX_BYTES
        ):
            _old_key, (old_data, _old_type) = _library_thumbs.popitem(last=False)
            _library_thumb_bytes -= len(old_data)
    return data, content_type


def api_library_file(rel_path, thumb=False):
    target = _resolve_library_path(rel_path)
    if thumb:
        data, content_type = _library_thumb(target)
        return data, content_type
    ext = os.path.splitext(target)[1].lower()
    content_type = MIME_TYPES.get(ext) or mimetypes.guess_type(target)[0] or "application/octet-stream"
    with open(target, "rb") as handle:
        return handle.read(), content_type



class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def map_pixiv_status(exc):
    status = _int(getattr(exc, "status", 0), 0)
    if status in (401, 403):
        return 401
    if status in (400, 404, 409, 429):
        return status
    return 502


class Handler(BaseHTTPRequestHandler):
    server_version = f"PixivCollector/{APP_VERSION}"
    protocol_version = "HTTP/1.1"

    # -- 基础响应 ----------------------------------------------------------

    def log_message(self, fmt, *args):  # noqa: A003 - 覆写基类方法
        # 静音默认访问日志（前端轮询很频繁），仅保留任务自身的日志
        pass

    def _common_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")

    def _guard_api(self, path):
        """校验 Host / Origin / 一次性 API Token，避免其它网页调用本地接口。"""
        port = self.server.server_port
        allowed_hosts = {
            f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}",
        }
        host = (self.headers.get("Host") or "").strip().lower()
        if host not in allowed_hosts:
            raise ApiError(403, "非法的 Host，只允许本机访问")
        origin = (self.headers.get("Origin") or "").strip().lower()
        allowed_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        if origin and origin not in allowed_origins:
            raise ApiError(403, "非法的来源")
        if path in ("/api/config", "/api/thumb", "/api/library/file"):
            return
        token = self.headers.get("X-API-Token") or ""
        if not secrets.compare_digest(token, STATE.api_token):
            raise ApiError(403, "API Token 无效，请刷新页面")

    def _send_json(self, payload, status=200):
        try:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeEncodeError):
            body = b'{"ok":false,"error":"\\u54cd\\u5e94\\u5e8f\\u5217\\u5316\\u5931\\u8d25"}'
            status = 500
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self._common_headers()
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _send_bytes(self, body, content_type, status=200, cache="no-cache"):
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self._common_headers()
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _read_json(self):
        length = _int(self.headers.get("Content-Length"), 0)
        if length <= 0:
            return {}
        if length > 8 * 1024 * 1024:
            raise ApiError(413, "请求体过大")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ApiError(400, f"请求体不是合法 JSON：{exc}") from exc
        if not isinstance(data, dict):
            raise ApiError(400, "请求体必须是 JSON 对象")
        return data

    # -- 分发 --------------------------------------------------------------

    def do_OPTIONS(self):  # noqa: N802 - BaseHTTPRequestHandler 命名约定
        self.send_response(204)
        self._common_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        try:
            parsed = urllib.parse.urlsplit(self.path)
            path = urllib.parse.unquote(parsed.path)
            query = urllib.parse.parse_qs(parsed.query)
            if path.startswith("/api/"):
                self._guard_api(path)
                self._handle_api_get(path, query)
            else:
                self._serve_static(path)
        except ApiError as exc:
            self._send_json({"ok": False, "error": exc.message}, exc.status)
        except PixivError as exc:
            self._send_json({"ok": False, "error": exc.message}, map_pixiv_status(exc))
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json({"ok": False, "error": f"服务器内部错误：{exc}"}, 500)

    def do_POST(self):  # noqa: N802
        try:
            parsed = urllib.parse.urlsplit(self.path)
            path = urllib.parse.unquote(parsed.path)
            if not path.startswith("/api/"):
                raise ApiError(404, "接口不存在")
            self._guard_api(path)
            self._handle_api_post(path)
        except ApiError as exc:
            self._send_json({"ok": False, "error": exc.message}, exc.status)
        except PixivError as exc:
            self._send_json({"ok": False, "error": exc.message}, map_pixiv_status(exc))
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json({"ok": False, "error": f"服务器内部错误：{exc}"}, 500)

    # -- API ---------------------------------------------------------------

    def _handle_api_get(self, path, query):
        if path == "/api/config":
            self._send_json(api_config())
            return
        if path == "/api/thumb":
            url = (query.get("u") or [""])[0].strip()
            if not url:
                raise ApiError(400, "缺少 u 参数")
            try:
                content_type, body = fetch_thumb(url)
            except PixivError as exc:
                raise ApiError(404 if exc.status in (404, 502, 500) else 400, exc.message) from exc
            self._send_bytes(body, content_type, cache="public, max-age=86400")
            return
        if path == "/api/output":
            self._send_json(api_output_stats())
            return
        if path == "/api/library":
            self._send_json(api_library(query))
            return
        if path == "/api/library/file":
            rel_path = (query.get("path") or [""])[0]
            thumb = _bool((query.get("thumb") or ["0"])[0], False)
            try:
                body, content_type = api_library_file(rel_path, thumb=thumb)
            except PixivError as exc:
                raise ApiError(404 if exc.status in (404, 502, 500) else 400, exc.message) from exc
            self._send_bytes(body, content_type, cache="public, max-age=3600")
            return
        if path == "/api/settings":
            self._send_json(api_get_settings())
            return
        if path == "/api/token/extract/auto/status":
            self._send_json(api_token_extract_auto_status((query.get("session_id") or [""])[0]))
            return
        if path == "/api/token/sources":
            self._send_json(api_token_sources())
            return
        if path == "/api/scan/active":
            self._send_json(api_scan_active())
            return
        if path == "/api/scan/history":
            self._send_json(api_scan_history())
            return
        m = re.fullmatch(r"/api/scan/history/([A-Za-z0-9_-]+)/hits", path)
        if m:
            self._send_json(api_scan_history_hits(
                m.group(1),
                (query.get("q") or [""])[0],
                _clamp_int((query.get("offset") or ["0"])[0], 0, 100000, 0),
                _clamp_int((query.get("limit") or ["20"])[0], 1, 100, 20),
                (query.get("level") or [""])[0],
            ))
            return
        m = re.fullmatch(r"/api/scan/history/([A-Za-z0-9_-]+)/hit/(\d+)", path)
        if m:
            self._send_json(api_scan_history_hit(m.group(1), int(m.group(2))))
            return
        m = re.fullmatch(r"/api/scan/history/([A-Za-z0-9_-]+)/export", path)
        if m:
            self._send_json(api_scan_history_export(m.group(1), (query.get("format") or ["csv"])[0]))
            return
        m = re.fullmatch(r"/api/scan/([A-Za-z0-9_-]+)/hit/(\d+)", path)
        if m:
            self._send_json(api_scan_hit(m.group(1), int(m.group(2))))
            return
        m = re.fullmatch(r"/api/scan/([A-Za-z0-9_-]+)", path)
        if m:
            self._send_json(api_scan_snapshot(m.group(1)))
            return
        m = re.fullmatch(r"/api/jobs/([A-Za-z0-9_-]+)", path)
        if m:
            self._send_json(api_job_snapshot(m.group(1)))
            return
        raise ApiError(404, f"接口不存在：GET {path}")

    def _handle_api_post(self, path):
        if path == "/api/connect":
            self._send_json(api_connect(self._read_json()))
            return
        if path == "/api/token/extract/start":
            self._send_json(api_token_extract_start(self._read_json()))
            return
        if path == "/api/token/extract/finish":
            self._send_json(api_token_extract_finish(self._read_json()))
            return
        if path == "/api/token/extract/auto/start":
            self._send_json(api_token_extract_auto_start(self._read_json()))
            return
        if path == "/api/token/extract/auto/cancel":
            self._send_json(api_token_extract_auto_cancel((self._read_json().get("session_id") or "")))
            return
        if path == "/api/preview":
            self._send_json(do_preview(self._read_json()))
            return
        if path == "/api/related/start":
            self._send_json(api_related_start(self._read_json()))
            return
        if path == "/api/related/next":
            self._send_json(api_related_next(self._read_json()))
            return
        if path == "/api/lookup":
            self._send_json(api_lookup(self._read_json()))
            return
        if path == "/api/download":
            self._send_json(api_download(self._read_json()))
            return
        if path == "/api/open-output":
            self._send_json(api_open_output(self._read_json()))
            return
        if path == "/api/scan/start":
            self._send_json(api_scan_start(self._read_json()))
            return
        if path == "/api/settings":
            self._send_json(api_save_settings(self._read_json()))
            return
        if path == "/api/network/speedtest":
            self._send_json(api_network_speedtest(self._read_json()))
            return
        m = re.fullmatch(r"/api/jobs/([A-Za-z0-9_-]+)/retry", path)
        if m:
            self._read_json()
            self._send_json(api_job_retry(m.group(1)))
            return
        m = re.fullmatch(r"/api/scan/([A-Za-z0-9_-]+)/stop", path)
        if m:
            self._read_json()  # 消费请求体，避免 keep-alive 下残留到下一个请求
            self._send_json(api_scan_stop(m.group(1)))
            return
        m = re.fullmatch(r"/api/jobs/([A-Za-z0-9_-]+)/cancel", path)
        if m:
            self._read_json()
            self._send_json(api_job_cancel(m.group(1)))
            return
        raise ApiError(404, f"接口不存在：POST {path}")

    # -- 静态文件 ----------------------------------------------------------

    def _serve_static(self, path):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        if rel.endswith("/"):
            rel += "index.html"
        root = os.path.abspath(WEB_DIR)
        full = os.path.abspath(os.path.join(root, rel.replace("/", os.sep)))
        # 防目录穿越
        if not (full == root or full.lower().startswith(root.lower() + os.sep)):
            raise ApiError(404, "文件不存在")
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            if path in ("", "/"):
                # web/index.html 尚未就绪时给一个提示页，方便前端联调
                placeholder = (
                    "<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\">"
                    "<title>Pixiv 漫画采集器</title>"
                    "<body style=\"font-family:system-ui,Segoe UI;padding:40px;color:#333\">"
                    "<h2>后端已启动</h2>"
                    "<p>web/index.html 尚未就绪：请把前端文件放到 <code>web/</code> 目录。</p>"
                    "<p>API 健康检查：<a href=\"/api/config\">/api/config</a></p>"
                    "</body></html>"
                )
                self._send_bytes(placeholder.encode("utf-8"), "text/html; charset=utf-8")
                return
            raise ApiError(404, "文件不存在")
        try:
            with open(full, "rb") as handle:
                body = handle.read()
        except OSError as exc:
            raise ApiError(404, f"读取文件失败：{exc}") from exc
        ext = os.path.splitext(full)[1].lower()
        content_type = MIME_TYPES.get(ext) or mimetypes.guess_type(full)[0] or "application/octet-stream"
        self._send_bytes(body, content_type, cache="no-cache")


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------

def load_key_file(cli_key_file=None):
    """按约定顺序查找密钥文件并载入内存。"""
    candidates = []
    if cli_key_file:
        candidates.append(os.path.abspath(cli_key_file))
    candidates.append(KEY_FILE_IN_DIR)
    candidates.append(DESKTOP_KEY_PATH)
    candidates.append(CONFIG_FILE_IN_DIR)

    for path in candidates:
        if not os.path.isfile(path):
            continue
        data = read_key_file(path)
        if not data.get("refresh_token"):
            continue
        STATE.key_path = path
        STATE.key_data = data
        STATE.client.refresh_token = data["refresh_token"]
        return path, data

    # 一个都没找到：记住“将要保存”的位置，供 config 展示
    STATE.key_path = os.path.abspath(cli_key_file) if cli_key_file else KEY_FILE_IN_DIR
    STATE.key_data = {}
    return None, {}


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    """浏览器刷新/关闭连接时不要往控制台打印无意义的 ConnectionResetError。"""

    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

    parser = argparse.ArgumentParser(description=f"{APP_NAME} 本地后端服务 v{APP_VERSION}")
    parser.add_argument("--port", type=int, default=8765, help="监听端口（默认 8765）")
    parser.add_argument("--key-file", default=None, help="通行密钥文件路径（默认自动查找）")
    parser.add_argument("--open", action="store_true", dest="open_browser", help="启动后自动打开浏览器")
    args = parser.parse_args(argv)

    os.makedirs(WEB_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    STATE.output_dir = OUTPUT_DIR
    STATE.settings = load_settings()
    apply_current_network()

    key_path, key_data = load_key_file(args.key_file)
    url = f"http://127.0.0.1:{args.port}"

    safe_print("=" * 62)
    safe_print(f"  {APP_NAME}  v{APP_VERSION}  （后端服务）")
    safe_print("=" * 62)
    safe_print(f"  本地地址 : {url}")
    safe_print(f"  静态目录 : {WEB_DIR}")
    safe_print(f"  输出目录 : {OUTPUT_DIR}")
    safe_print(f"  网络模式 : {STATE.settings.get('proxy_mode')} {STATE.settings.get('proxy_url') or ''}".rstrip())
    safe_print(f"  日志文件 : {os.path.join(LOG_DIR, 'app.log')}")
    if key_path:
        account = key_data.get("account") or "未标注账号"
        safe_print(f"  密钥文件 : {key_path}  （{account}）")
    else:
        safe_print(f"  密钥文件 : 未找到，可在页面中手动填写 refresh_token（将保存到 {STATE.key_path}）")
    safe_print("  按 Ctrl+C 停止服务")
    safe_print("=" * 62)

    try:
        httpd = QuietThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        safe_print(f"[错误] 端口 {args.port} 无法监听：{exc}")
        safe_print("       请换一个端口：python server.py --port 8766")
        return 1
    httpd.daemon_threads = True

    if args.open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        safe_print("\n[停止] 正在关闭服务…")
    finally:
        try:
            httpd.server_close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
