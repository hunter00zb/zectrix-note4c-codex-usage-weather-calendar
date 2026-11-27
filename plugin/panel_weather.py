"""天气面板（NOTE4C 四色，400×300）.

数据源: open-meteo.com（免 API Key），默认长沙。
可用环境变量覆盖: WEATHER_CITY / WEATHER_LAT / WEATHER_LON
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

PROJECT_DIR = "/Users/hunter.zong/Work/Test Pj/NOTE4C/Codex 今日用量显示/renderer"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import note4c_render as R  # noqa: E402

CITY = os.getenv("WEATHER_CITY", "长沙")
LAT = os.getenv("WEATHER_LAT", "28.23")
LON = os.getenv("WEATHER_LON", "112.94")

# WMO 天气码 → (中文描述, 用于强调的颜色)
WMO = {
    0: ("晴", R.YELLOW), 1: ("晴间多云", R.YELLOW), 2: ("多云", R.BLACK), 3: ("阴", R.BLACK),
    45: ("雾", R.BLACK), 48: ("雾凇", R.BLACK),
    51: ("小毛毛雨", R.BLACK), 53: ("毛毛雨", R.BLACK), 55: ("大毛毛雨", R.BLACK),
    61: ("小雨", R.BLACK), 63: ("中雨", R.BLACK), 65: ("大雨", R.RED),
    66: ("冻雨", R.RED), 67: ("强冻雨", R.RED),
    71: ("小雪", R.BLACK), 73: ("中雪", R.BLACK), 75: ("大雪", R.RED), 77: ("米雪", R.BLACK),
    80: ("阵雨", R.BLACK), 81: ("强阵雨", R.BLACK), 82: ("暴雨", R.RED),
    85: ("阵雪", R.BLACK), 86: ("强阵雪", R.RED),
    95: ("雷阵雨", R.RED), 96: ("雷雨冰雹", R.RED), 99: ("强雷雨冰雹", R.RED),
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


def render_weather(data, device_status=None):
    cur = data.get("current", {})
    daily = data.get("daily", {})
    temp = cur.get("temperature_2m")
    code = int(cur.get("weather_code") or 0)
    desc, accent = WMO.get(code, ("未知", R.BLACK))
    humidity = cur.get("relative_humidity_2m")
    wind = cur.get("wind_speed_10m")
    hi = (daily.get("temperature_2m_max") or [None])[0]
    lo = (daily.get("temperature_2m_min") or [None])[0]
    rain = (daily.get("precipitation_probability_max") or [None])[0]
    updated = datetime.datetime.now().strftime("%H:%M")

    img = Image.new("RGB", (R.W, R.H), R.WHITE)
    d = ImageDraw.Draw(img)

    # 标题栏
    d.rectangle([0, 0, R.W, 26], fill=R.BLACK)
    d.text((10, 5), f"天气 · {CITY}", font=R.font(15, bold=True), fill=R.WHITE)
    right = f"{datetime.datetime.now().strftime('%m-%d')} 更新 {updated}"
    tw = d.textlength(right, font=R.font(12, bold=True))
    d.text((R.W - 10 - tw, 7), right, font=R.font(12, bold=True), fill=R.WHITE)

    # 当前温度（超大字）
    temp_txt = f"{temp:.0f}°" if temp is not None else "--"
    d.text((14, 34), temp_txt, font=R.font(64, bold=True), fill=R.BLACK)
    temp_w = d.textlength(temp_txt, font=R.font(64, bold=True))

    # 天气描述：晴天用黄底强调
    desc_x = 14 + temp_w + 12
    if accent == R.YELLOW:
        desc_w = d.textlength(desc, font=R.font(20, bold=True))
        d.rectangle([desc_x - 6, 46, desc_x + desc_w + 6, 74], fill=R.YELLOW)
        d.text((desc_x, 48), desc, font=R.font(20, bold=True), fill=R.BLACK)
    else:
        d.text((desc_x, 48), desc, font=R.font(20, bold=True), fill=accent)

    # 今日详情
    d.text((desc_x, 82), f"最高 {hi:.0f}°  最低 {lo:.0f}°" if hi is not None else "",
           font=R.font(12, bold=True), fill=R.BLACK)
    extra = []
    if humidity is not None:
        extra.append(f"湿度 {humidity:.0f}%")
    if wind is not None:
        extra.append(f"风 {wind:.0f}km/h")
    if rain is not None:
        extra.append(f"降水 {rain:.0f}%")
    if extra:
        d.text((desc_x, 100), "  ".join(extra), font=R.font(12, bold=True), fill=R.BLACK)

    # 分隔线
    d.line([10, 122, R.W - 10, 122], fill=R.BLACK, width=2)

    # 未来三天
    dates = daily.get("time") or []
    codes = daily.get("weather_code") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    label_map = {1: "明天", 2: "后天", 3: "大后天"}
    for i in range(1, min(4, len(dates))):
        y = 130 + (i - 1) * 48
        label = label_map.get(i, dates[i][5:])
        d.text((14, y + 2), label, font=R.font(14, bold=True), fill=R.BLACK)
        c = int(codes[i]) if i < len(codes) and codes[i] is not None else 0
        cdesc, cacc = WMO.get(c, ("未知", R.BLACK))
        d.text((80, y + 2), cdesc, font=R.font(14, bold=True), fill=cacc)
        rng = f"{lows[i]:.0f}° ~ {highs[i]:.0f}°" if i < len(lows) and i < len(highs) else "--"
        rng_w = d.textlength(rng, font=R.font(14, bold=True))
        d.text((R.W - 14 - rng_w, y + 2), rng, font=R.font(14, bold=True), fill=R.BLACK)

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
