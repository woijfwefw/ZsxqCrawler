#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识星球请求画像构造工具。"""

import random
import time
import uuid
from typing import Dict, Optional


MOBILE_USER_AGENTS = [
    (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 "
        "Mobile Safari/537.36 MicroMessenger/8.0.49.2600(0x28003133) "
        "NetType/WIFI Language/zh_CN"
    ),
    (
        "Mozilla/5.0 (Linux; Android 13; M2012K11AC) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 "
        "Mobile Safari/537.36"
    ),
]


def _mobile_platform_for_user_agent(user_agent: str) -> str:
    """根据 UA 返回 Client Hints 平台值。"""
    if "iPhone" in user_agent or "iPad" in user_agent:
        return '"iOS"'
    return '"Android"'


def _mobile_sec_ch_ua(user_agent: str) -> str:
    """生成与移动端 UA 匹配的 Sec-CH-UA。"""
    if "Chrome/125" in user_agent:
        return '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"'
    if "Chrome/124" in user_agent:
        return '"Google Chrome";v="124", "Chromium";v="124", "Not.A/Brand";v="24"'
    return '"Chromium";v="125", "Not.A/Brand";v="24", "Google Chrome";v="125"'


def build_zsxq_mobile_headers(
    cookie: str,
    group_id: Optional[str] = None,
    *,
    referer: Optional[str] = None,
    include_host: bool = True,
) -> Dict[str, str]:
    """构造移动端 H5 请求头，用于只允许手机端的文件链接接口。"""
    selected_ua = random.choice(MOBILE_USER_AGENTS)
    request_id = str(uuid.uuid4())
    resolved_referer = referer or (
        f"https://wx.zsxq.com/dweb2/index/group/{group_id}"
        if group_id
        else "https://wx.zsxq.com/"
    )

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Cookie": cookie,
        "Origin": "https://wx.zsxq.com",
        "Pragma": "no-cache",
        "Referer": resolved_referer,
        "Sec-Ch-Ua": _mobile_sec_ch_ua(selected_ua),
        "Sec-Ch-Ua-Mobile": "?1",
        "Sec-Ch-Ua-Platform": _mobile_platform_for_user_agent(selected_ua),
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": selected_ua,
        "X-Requested-With": "XMLHttpRequest",
        "X-Request-Id": request_id,
        "X-Timestamp": str(int(time.time())),
        "X-Version": "2.77.0",
    }

    if include_host:
        headers["Host"] = "api.zsxq.com"

    return headers


def build_zsxq_file_stream_headers(
    cookie: str,
    group_id: Optional[str] = None,
    *,
    include_cookie: bool = False,
) -> Dict[str, str]:
    """构造真实文件流下载请求头，避免把 api.zsxq.com Host 带到 CDN。"""
    headers = build_zsxq_mobile_headers(cookie, group_id, include_host=False)
    headers.update(
        {
            "Accept": "*/*",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
        }
    )
    headers.pop("Origin", None)
    headers.pop("Host", None)
    if not include_cookie:
        headers.pop("Cookie", None)
    return headers


def is_mobile_only_error(error_code: object, message: Optional[str] = None) -> bool:
    """判断是否命中仅手机端下载限制。"""
    normalized_code = str(error_code).strip()
    normalized_message = (message or "").lower()
    return normalized_code == "1030" or any(
        marker in normalized_message
        for marker in ("手机", "mobile", "app", "客户端")
    )
