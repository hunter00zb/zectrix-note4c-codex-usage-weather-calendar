"""日历面板（NOTE4C 四色，400×300）.

版式：上方大字日期 + 星期 + 今日天气 + 地区；下方当月小日历网格（今天黄底高亮）。
天气数据复用 open-meteo（同天气面板）。
"""

import calendar
import datetime
import logging
import os
import sys

from PIL import Image, ImageDraw

from .fourcolor_base import FourColorPanel
from .panel_weather import CITY, WEEKDAYS, WMO, fetch_weather

logger = logging.getLogger(__name__)

PROJECT_DIR = "/Users/hunter.zong/Work/Test Pj/NOTE4C/Codex 今日用量显示/renderer"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import note4c_render as R  # noqa: E402

CN_MONTH = ["一月", "二月", "三月", "四月", "五月", "六月",
            "七月", "八月", "九月", "十月", "十一月", "十二月"]


def render_calendar(weather, device_status=None):
    now = datetime.datetime.now()
    updated = now.strftime("%H:%M")
    cur = (weather or {}).get("current", {})
    daily = (weather or {}).get("daily", {})
    temp = cur.get("temperature_2m")
    code = int(cur.get("weather_code") or 0)
    desc = WMO.get(code, "未知")
    hi = (daily.get("temperature_2m_max") or [None])[0]
    lo = (daily.get("temperature_2m_min") or [None])[0]

    img = Image.new("RGB", (R.W, R.H), R.WHITE)
    d = ImageDraw.Draw(img)

    # 标题栏
    d.rectangle([0, 0, R.W, 26], fill=R.BLACK)
    d.text((10, 5), f"{now.year}年{now.month}月", font=R.font(15, bold=True), fill=R.WHITE)
    right = f"{now.strftime('%m-%d')} 更新 {updated}"
    tw = d.textlength(right, font=R.font(12, bold=True))
    d.text((R.W - 10 - tw, 7), right, font=R.font(12, bold=True), fill=R.WHITE)

    # 左：大日期 + 星期
    d.text((16, 32), str(now.day), font=R.font(72, bold=True), fill=R.BLACK)
    day_w = d.textlength(str(now.day), font=R.font(72, bold=True))
    d.text((16 + day_w + 6, 44), CN_MONTH[now.month - 1], font=R.font(14, bold=True), fill=R.BLACK)
    d.text((18, 112), WEEKDAYS[now.weekday()], font=R.font(16, bold=True), fill=R.RED)

    # 右：地区 + 天气
    d.text((18, 140), f"{CITY} · {desc}", font=R.font(14, bold=True), fill=R.BLACK)
    R.draw_weather_icon(d, 236, 96, 64, code)
    temp_txt = f"{temp:.0f}°" if temp is not None else "--°"
    d.text((272, 62), temp_txt, font=R.font(40, bold=True), fill=R.BLACK)
    hi_txt = f"高 {hi:.0f}°" if hi is not None else "高 --"
    lo_txt = f"低 {lo:.0f}°" if lo is not None else "低 --"
    d.text((272, 110), f"{hi_txt}  {lo_txt}", font=R.font(12, bold=True), fill=R.BLACK)

    # 分隔线
    d.line([8, 164, R.W - 8, 164], fill=R.BLACK, width=2)

    # 月历网格（周一开头，7 列）
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(now.year, now.month)
    headers = ["一", "二", "三", "四", "五", "六", "日"]
    grid_x, grid_y = 12, 166
    cell_w, cell_h = 52, 15
    for i, h in enumerate(headers):
        cx = grid_x + i * cell_w + cell_w // 2
        d.text((cx - 5, grid_y), h, font=R.font(11, bold=True),
               fill=R.RED if i >= 5 else R.BLACK)

    for wi, week in enumerate(weeks[:6]):
        for di, day in enumerate(week):
            if day == 0:
                continue
            x0 = grid_x + di * cell_w
            y0 = grid_y + 16 + wi * cell_h
            if day == now.day:
                d.rectangle([x0 + 2, y0, x0 + cell_w - 4, y0 + cell_h - 2], fill=R.YELLOW,
                            outline=R.BLACK, width=1)
                color = R.BLACK
            else:
                color = R.RED if di >= 5 else R.BLACK
            label = str(day)
            lw = d.textlength(label, font=R.font(11, bold=True))
            d.text((x0 + (cell_w - lw) / 2, y0 + 1), label, font=R.font(11, bold=True), fill=color)

    R.draw_footer(d, updated, device_status)
    return img


class CalendarPanelPlugin(FourColorPanel):
    """日历面板."""

    BASENAME = "calendar_panel"
    OUTPUT_SUBDIR = "calendar_panel"
    AUTO_REGISTER = True
    REGISTRY_ORDER = 30
    REFRESH_INTERVAL = 1800
    DISPLAY_NAME = "日历"

    def render_panel(self):
        try:
            weather = fetch_weather()
        except Exception as exc:  # 天气失败不影响日历主体
            logger.warning("CalendarPanelPlugin: 天气获取失败 %s", exc)
            weather = None
        return render_calendar(weather, self.device_status())
