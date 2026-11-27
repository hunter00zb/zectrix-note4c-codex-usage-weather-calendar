"""照片面板（NOTE4C 四色，400×300）.

取 Bing 每日壁纸，裁切缩放后做四色误差扩散抖动，全屏铺满（对齐官方演示的照片浏览样式）。
优先复用 BYOS Bing 插件已下载的资产，缺失时直接调用 Bing 接口。
"""

import datetime
import io
import json
import logging
import os
import sys
import urllib.request

from PIL import Image

from .fourcolor_base import FourColorPanel

logger = logging.getLogger(__name__)

PROJECT_DIR = "/Users/hunter.zong/Work/Test Pj/NOTE4C/Codex 今日用量显示/renderer"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import note4c_render as R  # noqa: E402

SERVER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOCAL_BING = os.path.join(SERVER_ROOT, "var", "generated", "bing", "bing_wallpaper.png")


def _load_from_local():
    if os.path.exists(LOCAL_BING) and os.path.getsize(LOCAL_BING) > 10000:
        with open(LOCAL_BING, "rb") as f:
            return Image.open(io.BytesIO(f.read())).convert("RGB")
    return None


def _load_from_bing():
    api = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=zh-CN"
    req = urllib.request.Request(api, headers={"User-Agent": "note4c-panel/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    url = "https://www.bing.com" + data["images"][0]["urlbase"] + "_1920x1080.jpg"
    req2 = urllib.request.Request(url, headers={"User-Agent": "note4c-panel/1.0"})
    with urllib.request.urlopen(req2, timeout=20) as resp:
        return Image.open(io.BytesIO(resp.read())).convert("RGB")


def load_photo():
    img = _load_from_local()
    if img is None:
        img = _load_from_bing()
    return img


def render_photo(photo):
    """全屏铺满裁切 → 400×300，四色抖动。"""
    target_w, target_h = R.W, R.H
    src_w, src_h = photo.size
    scale = max(target_w / src_w, target_h / src_h)
    new_size = (max(1, int(src_w * scale + 0.5)), max(1, int(src_h * scale + 0.5)))
    resized = photo.resize(new_size, Image.LANCZOS)
    left = (new_size[0] - target_w) // 2
    top = (new_size[1] - target_h) // 2
    cropped = resized.crop((left, top, left + target_w, top + target_h))
    return R.quantize_bwry_dithered(cropped)


class PhotoPanelPlugin(FourColorPanel):
    """照片面板（Bing 每日壁纸）."""

    BASENAME = "photo_panel"
    OUTPUT_SUBDIR = "photo_panel"
    AUTO_REGISTER = True
    REGISTRY_ORDER = 30
    REFRESH_INTERVAL = 3600
    DISPLAY_NAME = "照片"

    def render_panel(self):
        return render_photo(load_photo())
