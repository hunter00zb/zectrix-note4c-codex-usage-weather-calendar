"""天气面板（NOTE4C 四色，400×300）—— 版式参照官方 NOTE4C 天气卡.

结构：左侧大图标 + 超大温度；右侧日期/星期（红色强调）/天气/高低温；
中部三张未来天气卡；底部黑色提醒条 + 设备状态条。

数据源: open-meteo.com（免 API Key），默认长沙。
环境变量覆盖: WEATHER_CITY / WEATHER_LAT / WEATHER_LON
"""

import datetime
import json
import logging
import os
import sys
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw

from .fourcolor_base import FourColorPanel

logger = logging.getLogger(__name__)

PROJECT_DIR = "/Users/hunter.zong/Work/Test Pj/NOTE4C/Codex 用量-日历-天气显示/renderer"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import note4c_render as R  # noqa: E402

CITY = os.getenv("WEATHER_CITY", "长沙")
LAT = os.getenv("WEATHER_LAT", "28.23")
LON = os.getenv("WEATHER_LON", "112.94")

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

WMO = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "雾", 48: "雾凇",
    51: "毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪",
    80: "阵雨", 81: "强阵雨", 82: "暴雨", 85: "阵雪", 86: "强阵雪",
    95: "雷阵雨", 96: "雷雨冰雹", 99: "强雷雨冰雹",
}


def fetch_weather():
    params = {
        "latitude": LAT, "longitude": LON,
        "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max",
        "timezone": "Asia/Shanghai",
        "forecast_days": 4,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "note4c-panel/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _advice(data):
    """底部黑色提醒条文案：返回 (前缀, 高亮词, 后缀)。"""
    daily = data.get("daily", {})
    codes = daily.get("weather_code") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    rain_today = bool(codes) and int(codes[0] or 0) >= 51
    rain_next = len(codes) > 1 and int(codes[1] or 0) >= 51
    if rain_today:
        return "提醒", "今天有雨", "· 出门记得带伞"
    if rain_next:
        return "提醒", "明天有雨", "· 提前备好雨具"
    if highs and highs[0] is not None and highs[0] >= 33:
        return "提醒", "高温天气", "· 注意防暑补水"
    if lows and lows[0] is not None and lows[0] <= 2:
        return "提醒", "气温偏低", "· 注意保暖"
    return "提示", "适宜出行", "· 天气平稳"


def render_weather(data, device_status=None):
    cur = data.get("current", {})
    daily = data.get("daily", {})
    temp = cur.get("temperature_2m")
    code = int(cur.get("weather_code") or 0)
    desc = WMO.get(code, "未知")
    hi = (daily.get("temperature_2m_max") or [None])[0]
    lo = (daily.get("temperature_2m_min") or [None])[0]
    now = datetime.datetime.now()
    updated = now.strftime("%H:%M")

    img = Image.new("RGB", (R.W, R.H), R.WHITE)
    d = ImageDraw.Draw(img)

    # 顶部：标题 + 更新时间
    d.text((8, 6), f"{CITY}天气", font=R.font(15, bold=True), fill=R.BLACK)
    right = f"{now.strftime('%m-%d')} 更新 {updated}"
    tw = d.textlength(right, font=R.font(11, bold=True))
    d.text((R.W - 8 - tw, 8), right, font=R.font(11, bold=True), fill=R.BLACK)

    # 左侧：大图标 + 超大温度
    R.draw_weather_icon(d, 72, 74, 96, code)
    temp_txt = f"{temp:.0f}°" if temp is not None else "--°"
    d.text((126, 34), temp_txt, font=R.font(58, bold=True), fill=R.BLACK)

    # 右侧：日期 / 星期（红）/ 天气 / 高低温
    col_x = 262
    d.line([col_x - 12, 28, col_x - 12, 116], fill=R.BLACK, width=1)
    d.text((col_x, 30), f"{now.month}月{now.day}日", font=R.font(15, bold=True), fill=R.BLACK)
    d.text((col_x, 50), WEEKDAYS[now.weekday()], font=R.font(15, bold=True), fill=R.RED)
    d.text((col_x, 76), desc, font=R.font(14, bold=True), fill=R.BLACK)
    hl = f"高 {hi:.0f}°" if hi is not None else "高 --"
    ll = f"低 {lo:.0f}°" if lo is not None else "低 --"
    d.text((col_x, 96), f"{hl} | {ll}", font=R.font(13, bold=True), fill=R.BLACK)

    # 中线
    d.line([8, 126, R.W - 8, 126], fill=R.BLACK, width=2)

    # 中部：三天卡片
    dates = daily.get("time") or []
    codes = daily.get("weather_code") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    labels = ["今天", "明天", "后天"]
    card_w, card_h, gap = 122, 72, 8
    for i in range(min(3, len(dates))):
        x0 = 8 + i * (card_w + gap)
        y0 = 134
        d.rectangle([x0, y0, x0 + card_w, y0 + card_h], outline=R.BLACK, width=2)
        d.text((x0 + 7, y0 + 4), labels[i], font=R.font(12, bold=True), fill=R.BLACK)
        c = int(codes[i]) if i < len(codes) and codes[i] is not None else 0
        R.draw_weather_icon(d, x0 + 34, y0 + 44, 40, c)
        h_txt = f"{highs[i]:.0f}°" if i < len(highs) and highs[i] is not None else "--"
        l_txt = f"{lows[i]:.0f}°" if i < len(lows) and lows[i] is not None else "--"
        d.text((x0 + 64, y0 + 22), h_txt, font=R.font(17, bold=True), fill=R.BLACK)
        d.text((x0 + 64, y0 + 44), l_txt, font=R.font(14, bold=True), fill=R.BLACK)

    # 底部黑色提醒条
    d.rectangle([8, 214, R.W - 8, 272], fill=R.BLACK)
    prefix, highlight, suffix = _advice(data)
    x = 20
    d.text((x, 229), prefix, font=R.font(13, bold=True), fill=R.YELLOW)
    x += d.textlength(prefix, font=R.font(13, bold=True)) + 10
    d.text((x, 227), highlight, font=R.font(15, bold=True), fill=R.YELLOW)
    x += d.textlength(highlight, font=R.font(15, bold=True)) + 8
    d.text((x, 230), suffix, font=R.font(12, bold=True), fill=R.WHITE)

    R.draw_footer(d, updated, device_status)
    return img


class WeatherPanelPlugin(FourColorPanel):
    """天气面板."""

    BASENAME = "weather_panel"
    OUTPUT_SUBDIR = "weather_panel"
    AUTO_REGISTER = True
    REGISTRY_ORDER = 20
    REFRESH_INTERVAL = 900
    DISPLAY_NAME = "天气"

    def render_panel(self):
        return render_weather(fetch_weather(), self.device_status())
