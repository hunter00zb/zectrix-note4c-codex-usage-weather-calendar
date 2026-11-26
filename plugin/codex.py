"""Codex 用量监控插件 —— 为 NOTE4C 四色屏提供 400×300 精确四色面板.

数据源: 本机 Codex 监控服务 /api/snapshot
输出: 24-bit 彩色 BMP（黑/白/黄/红精确调色板）+ PNG 预览
    绕过 BYOS 默认的 1-bit 黑白管线，四色信息直达设备端
"""

import asyncio
import logging
import os
import sys
from typing import Optional

from PIL import Image

from .base import PluginBase, PluginOutput

logger = logging.getLogger(__name__)

PROJECT_DIR = "/Users/hunter.zong/Work/Test Pj/NOTE4C/Codex 今日用量显示/renderer"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import note4c_render  # noqa: E402


class CodexPlugin(PluginBase):
    """本机 Codex 用量监控面板（NOTE4C 四色专用）."""

    BASENAME = "codex"
    OUTPUT_SUBDIR = "codex"
    REGISTRY_ORDER = 10
    REFRESH_INTERVAL = 300  # 与设备轮询周期对齐（5 分钟）
    DISPLAY_NAME = "Codex 用量监控"

    async def run(self, **kwargs) -> Optional[PluginOutput]:
        output_dir = kwargs.get("output_dir")
        basename = kwargs.get("basename", self.BASENAME)
        return await asyncio.to_thread(self._run_sync, output_dir, basename)

    def _run_sync(self, output_dir: Optional[str], basename: str) -> PluginOutput:
        os.makedirs(output_dir, exist_ok=True)
        device_status = self._device_status()
        try:
            snapshot = note4c_render.fetch_snapshot()
            image = note4c_render.render(snapshot, device_status)
            ok = True
        except Exception as exc:
            logger.warning("CodexPlugin: 监控服务不可用（%s），渲染离线告警页", exc)
            image, ok = note4c_render.render_offline(), False
        if ok:
            logger.info("CodexPlugin: 面板渲染完成（真实数据）")
        quantized = note4c_render.quantize_bwry(image)

        # 内容哈希去重：数据没变就保留旧资产（filename 稳定 → 设备跳过刷屏）
        import hashlib
        digest = hashlib.sha256(note4c_render.pack_2bpp(quantized)).hexdigest()[:16]
        hash_file = os.path.join(output_dir, f"{basename}.hash")
        old = None
        if os.path.exists(hash_file):
            with open(hash_file) as f:
                old = f.read().strip()
        if old == digest:
            logger.info("CodexPlugin: 内容未变化 (hash=%s)，跳过资产写入", digest)
            safe = os.path.basename(basename)
            return PluginOutput(
                monochrome_path=os.path.abspath(os.path.join(output_dir, f"{safe}.bmp")),
                grayscale_path=os.path.abspath(os.path.join(output_dir, f"{safe}.png")),
            )
        result = self.save_assets(quantized, output_dir, basename)
        with open(hash_file, "w") as f:
            f.write(digest)
        return result

    @staticmethod
    def _device_status():
        """读取设备最近一次上报的电量/RSSI（BYOS 在 /api/display 请求头里采集）。"""
        try:
            from .. import models, utils
            rows = models.get_battery_history(limit=1)
            if not rows:
                return None
            latest = rows[0]
            return {
                "battery_pct": utils.get_battery_state(latest.voltage),
                "rssi": int(latest.rssi),
                "voltage": latest.voltage,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("CodexPlugin: 设备状态读取失败: %s", exc)
            return None

    def save_assets(self, image: Image.Image, output_dir: str, basename: str,
                    dither_mode=None) -> PluginOutput:
        """写 4 色索引 PNG（固件 png_draw_4clr 正路）+ 24-bit BMP 兜底。"""
        os.makedirs(output_dir, exist_ok=True)
        safe_name = os.path.basename(basename) or self.BASENAME
        bmp_path = os.path.abspath(os.path.join(output_dir, f"{safe_name}.bmp"))
        png_path = os.path.abspath(os.path.join(output_dir, f"{safe_name}.png"))

        image.save(bmp_path, format="BMP")  # 兜底通道

        # 4 色索引 PNG：调色板顺序 = 设备码 black0/white1/yellow2/red3
        palette = []
        for rgb in note4c_render.PALETTE:
            palette.extend(rgb)
        lut = {note4c_render.BLACK: 0, note4c_render.WHITE: 1,
               note4c_render.YELLOW: 2, note4c_render.RED: 3}
        p = Image.new("P", image.size, 1)
        p.putpalette(palette + [0] * (768 - len(palette)))
        px = image.load()
        pp = p.load()
        for y in range(image.height):
            for x in range(image.width):
                pp[x, y] = lut[px[x, y]]
        p.save(png_path, format="PNG", optimize=True)

        logger.info("CodexPlugin: 已保存资产 %s / %s (%dx%d, 4色索引 PNG)",
                    bmp_path, png_path, image.width, image.height)
        return PluginOutput(monochrome_path=bmp_path, grayscale_path=png_path)
