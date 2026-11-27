"""四色面板插件基类：统一 400×300 4 色索引 PNG 输出 + 内容哈希去重.

NOTE4C（SSD2683 四色）必须走 PNG 通道，调色板顺序 = 设备颜色码：
黑 0 / 白 1 / 黄 2 / 红 3
"""

import asyncio
import hashlib
import logging
import os
import sys
from typing import Optional

from PIL import Image

from .base import PluginBase, PluginOutput

logger = logging.getLogger(__name__)


class FourColorPanel(PluginBase):
    """子类只需实现 render_panel() 返回精确四色 RGB 图像。"""

    PANEL_SIZE = (400, 300)
    AUTO_REGISTER = False  # 基类不参与注册，仅子类暴露为插件

    def render_panel(self) -> Image.Image:  # pragma: no cover - 由子类实现
        raise NotImplementedError

    async def run(self, **kwargs) -> Optional[PluginOutput]:
        output_dir = kwargs.get("output_dir")
        basename = kwargs.get("basename", self.BASENAME)
        return await asyncio.to_thread(self._run_sync, output_dir, basename)

    def _run_sync(self, output_dir: Optional[str], basename: str) -> PluginOutput:
        os.makedirs(output_dir, exist_ok=True)
        try:
            image = self.render_panel()
            ok = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: 渲染失败（%s），使用错误占位页", self.name, exc)
            image = self.render_error_page(str(exc))
            ok = False

        image = image.convert("RGB")
        if image.size != self.PANEL_SIZE:
            image = image.resize(self.PANEL_SIZE, Image.LANCZOS)

        digest = hashlib.sha256(image.tobytes()).hexdigest()[:16]
        hash_file = os.path.join(output_dir, f"{basename}.hash")
        old = None
        if os.path.exists(hash_file):
            with open(hash_file) as f:
                old = f.read().strip()
        if old == digest:
            logger.info("%s: 内容未变化 (hash=%s)，跳过写入", self.name, digest)
            safe = os.path.basename(basename)
            return PluginOutput(
                monochrome_path=os.path.abspath(os.path.join(output_dir, f"{safe}.bmp")),
                grayscale_path=os.path.abspath(os.path.join(output_dir, f"{safe}.png")),
            )

        result = self.save_assets(image, output_dir, basename)
        with open(hash_file, "w") as f:
            f.write(digest)
        logger.info("%s: 资产已更新 (hash=%s)%s", self.name, digest, "" if ok else " [占位页]")
        return result

    def save_assets(self, image: Image.Image, output_dir: str, basename: str,
                    dither_mode=None) -> PluginOutput:
        """写 4 色索引 PNG（固件正路）+ 24-bit BMP 兜底。"""
        os.makedirs(output_dir, exist_ok=True)
        safe_name = os.path.basename(basename) or self.BASENAME
        bmp_path = os.path.abspath(os.path.join(output_dir, f"{safe_name}.bmp"))
        png_path = os.path.abspath(os.path.join(output_dir, f"{safe_name}.png"))

        # 先做调色板量化（PIL 文字有抗锯齿灰边，必须映射到四色，否则灰边会被判成黑而吃掉笔画）
        renderer_dir = os.getenv("NOTE4C_RENDERER_DIR") or os.path.abspath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "renderer"))
        if renderer_dir not in sys.path:
            sys.path.insert(0, renderer_dir)
        import note4c_render as R
        image = R.quantize_bwry(image)

        image.save(bmp_path, format="BMP")

        palette = []
        for rgb in ((0, 0, 0), (255, 255, 255), (255, 255, 0), (255, 0, 0)):
            palette.extend(rgb)
        lut = {(0, 0, 0): 0, (255, 255, 255): 1, (255, 255, 0): 2, (255, 0, 0): 3}

        p = Image.new("P", image.size, 1)
        p.putpalette(palette + [0] * (768 - len(palette)))
        px = image.load()
        pp = p.load()
        for y in range(image.height):
            for x in range(image.width):
                rgb = px[x, y][:3]
                pp[x, y] = lut.get(rgb, 0)
        p.save(png_path, format="PNG", optimize=True)
        return PluginOutput(monochrome_path=bmp_path, grayscale_path=png_path)

    def render_error_page(self, reason: str) -> Image.Image:
        from PIL import ImageDraw
        import note4c_render as R

        img = Image.new("RGB", self.PANEL_SIZE, (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 400, 26], fill=(255, 0, 0))
        d.text((10, 5), self.get_display_name(), font=R.font(15, bold=True), fill=(255, 255, 255))
        d.rectangle([20, 100, 380, 200], outline=(255, 0, 0), width=3)
        d.text((40, 120), "数据获取失败", font=R.font(24, bold=True), fill=(255, 0, 0))
        d.text((40, 160), reason[:28], font=R.font(12, bold=True), fill=(0, 0, 0))
        return img

    @staticmethod
    def device_status():
        """读取设备最近一次上报的电量/RSSI。"""
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
        except Exception:  # noqa: BLE001
            return None
