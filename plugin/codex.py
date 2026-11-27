"""Codex 用量监控面板（NOTE4C 四色，400×300）.

数据源: 本机 Codex 监控服务 /api/snapshot
"""

import logging
import sys

from PIL import Image

from .fourcolor_base import FourColorPanel

logger = logging.getLogger(__name__)

PROJECT_DIR = "/Users/hunter.zong/Work/Test Pj/NOTE4C/Codex 今日用量显示/renderer"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import note4c_render  # noqa: E402


class CodexPlugin(FourColorPanel):
    """Codex 今日用量面板."""

    BASENAME = "codex"
    OUTPUT_SUBDIR = "codex"
    AUTO_REGISTER = True
    REGISTRY_ORDER = 10
    REFRESH_INTERVAL = 300
    DISPLAY_NAME = "Codex 用量监控"

    def render_panel(self) -> Image.Image:
        snapshot = note4c_render.fetch_snapshot()
        return note4c_render.render(snapshot, self.device_status())
