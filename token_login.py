#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内置 Pixiv 登录窗口。

由 server.py 以子进程方式启动：
    python -u token_login.py <login_url>

用户在弹出的窗口里完成 Pixiv 登录后，页面会跳转 pixiv://account/login?code=...
本脚本拦截这次导航，把回调 URL 打印到 stdout（CODE:...），然后关闭窗口。
server.py 读取 CODE 并完成授权码换 refresh_token；本脚本不接触任何密钥。
"""

from __future__ import annotations

import os
import sys
import threading
import time


def emit(text):
    try:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
    except Exception:
        pass


def main():
    if len(sys.argv) < 2:
        emit("ERROR:缺少登录地址")
        return 2
    login_url = sys.argv[1]
    try:
        import webview
    except Exception as exc:  # noqa: BLE001
        emit(f"ERROR:未安装 pywebview（{exc}）")
        return 3

    state = {"captured": False}
    window_holder = {"window": None}

    # Windows 的 WebView2 后端会在 NavigationStarting 里拿到 pixiv:// 回调。
    # 这里挂一层轻量补丁，不修改 pywebview 安装文件。
    try:
        from webview.platforms import edgechromium

        original = edgechromium.EdgeChrome.on_navigation_start

        def patched(self, sender, args):
            try:
                uri = str(args.Uri)
            except Exception:
                uri = ""
            if not state["captured"] and uri.startswith("pixiv://") and "code=" in uri:
                state["captured"] = True
                emit("CODE:" + uri)
                window = window_holder.get("window")
                if window is not None:
                    threading.Timer(0.35, window.destroy).start()
                # window.destroy() 在部分 WebView2 组合下不一定能结束 pywebview.start，
                # 再用一个兜底定时器确保子进程退出（server 已经从 stdout 拿到 CODE）。
                threading.Timer(1.0, lambda: os._exit(0)).start()
            return original(self, sender, args)

        edgechromium.EdgeChrome.on_navigation_start = patched
    except Exception as exc:  # noqa: BLE001
        emit(f"ERROR:当前环境无法拦截 Pixiv 回调（{exc}）")
        return 4

    try:
        window = webview.create_window(
            "Pixiv 登录 · 完成后自动提取通行密钥",
            login_url,
            width=540,
            height=780,
            resizable=True,
        )
        window_holder["window"] = window
        # 最多等 10 分钟，避免忘记关闭后一直挂着。
        threading.Timer(600, window.destroy).start()
        webview.start(debug=False)
    except Exception as exc:  # noqa: BLE001
        emit(f"ERROR:登录窗口启动失败（{exc}）")
        return 5

    if not state["captured"]:
        emit("CLOSED")
    time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
