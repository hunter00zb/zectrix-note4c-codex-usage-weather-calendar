#!/usr/bin/env python3
"""NOTE4C 四色渲染核心模块.

供 render_codex.py（独立推送脚本）和 BYOS CodexPlugin（服务端插件）共用。
"""

import datetime
import json
import urllib.request

from PIL import Image, ImageDraw, ImageFont

MONITOR_URL = "http://127.0.0.1:18741/api/snapshot"
W, H = 400, 300

# 精确四色调色板 (RGB) —— 墨水屏 BWRY
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)
RED = (255, 0, 0)
PALETTE = [BLACK, WHITE, YELLOW, RED]
DEVICE_CODE = {BLACK: 0, WHITE: 1, YELLOW: 2, RED: 3}  # 2bpp 设备颜色码

CHANNEL_NAMES = {
    "local": "Codex 本地",
    "feishu": "飞书",
    "wecom": "企业微信",
    "unknown": "未归属",
}

FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_REGULAR = 0  # W3
FONT_BOLD = 2     # W6


def font(size, bold=False):
    return ImageFont.truetype(FONT_PATH, size, index=FONT_BOLD if bold else FONT_REGULAR)


def fmt_tokens(n):
    """91.5M / 171.3K / 0 格式化"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def state_color(state):
    """只有真正的异常才用红色；unknown（待确认）与 connected 同为正常态。"""
    return RED if state in ("reconnecting", "offline") else BLACK


def state_text(key, ch):
    if key == "unknown":
        return "来源待确认"
    if key == "local" and ch["state"] == "connected":
        return "桌面应用运行中"
    return {
        "connected": "连接正常",
        "reconnecting": "断开或重连",
        "offline": "进程未运行",
        "unknown": "运行中·待确认",
    }.get(ch["state"], "状态待确认")


def fetch_snapshot():
    req = urllib.request.Request(MONITOR_URL, headers={"Cache-Control": "no-store"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _draw_bars(d, x, y_base, filled, total=5, bar_w=5, gap=2, height=7, color=None):
    """画 5 格强度条：等高等宽，filled 实心（颜色随强度告警），其余空心描边。"""
    if color is None:
        color = WHITE
    for i in range(total):
        bx = x + i * (bar_w + gap)
        rect = [bx, y_base - height, bx + bar_w - 1, y_base]
        if i < filled:
            d.rectangle(rect, fill=color)
        else:
            d.rectangle(rect, outline=WHITE, width=1)
    return x + total * (bar_w + gap)


def _bar_color(bars):
    """2 格=黄色预警，1 格=红色告警。"""
    if bars <= 1:
        return RED
    if bars == 2:
        return YELLOW
    return WHITE


def _battery_bars(pct):
    return max(1, min(5, int((pct + 19.9) // 20)))


def _wifi_bars(rssi):
    if rssi >= -55:
        return 5
    if rssi >= -65:
        return 4
    if rssi >= -75:
        return 3
    if rssi >= -85:
        return 2
    return 1


def draw_footer(d, updated, device_status):
    """通用底部状态条：左=电量/WiFi 五格，右=数据时间。"""
    d.rectangle([0, H - 22, W, H], fill=BLACK)
    y_base = H - 5
    x = 10
    if device_status:
        pct = device_status.get("battery_pct")
        if pct is not None:
            d.text((x, H - 18), "电量", font=font(12, bold=True), fill=WHITE)
            x += 30
            b_bars = _battery_bars(pct)
            x = _draw_bars(d, x, y_base - 4, b_bars, color=_bar_color(b_bars))
            d.text((x + 1, H - 18), f"{pct:.0f}%", font=font(12, bold=True), fill=WHITE)
            x += d.textlength(f"{pct:.0f}%", font=font(12, bold=True)) + 10
        rssi = device_status.get("rssi")
        if rssi is not None:
            d.text((x, H - 18), "WiFi", font=font(12, bold=True), fill=WHITE)
            x += 32
            w_bars = _wifi_bars(rssi)
            _draw_bars(d, x, y_base - 4, w_bars, color=_bar_color(w_bars))
    right = f"数据 {updated}"
    tw2 = d.textlength(right, font=font(12, bold=True))
    d.text((W - 10 - tw2, H - 18), right, font=font(12, bold=True), fill=WHITE)


def render(snapshot, device_status=None):
    """渲染 400×300 监控面板，返回精确四色 PIL 图像。

    device_status: 可选 dict，含 battery_pct / rssi，用于底部设备状态栏。
    """
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    now = datetime.datetime.now().strftime("%H:%M")
    updated = snapshot.get("updated_at", "")[11:16]

    # 顶部黑条：右上=本次更新时间（渲染时刻）
    d.rectangle([0, 0, W, 26], fill=BLACK)
    d.text((10, 5), "Codex 今日用量", font=font(15, bold=True), fill=WHITE)
    header_right = f"{datetime.datetime.now().strftime('%m-%d')} 更新 {now}"
    tw = d.textlength(header_right, font=font(12, bold=True))
    d.text((W - 10 - tw, 7), header_right, font=font(12, bold=True), fill=WHITE)

    margin, gap = 8, 8
    top = 34
    card_w = (W - margin * 2 - gap) // 2
    card_h = (H - top - 26 - gap) // 2

    channels = snapshot.get("channels", {})
    keys = ["local", "feishu", "wecom"]
    today_total = sum(c.get("usage", {}).get("1", {}).get("total_tokens", 0)
                      for c in channels.values())

    cells = [(k, channels.get(k)) for k in keys] + [("__today__", None)]

    for idx, (key, ch) in enumerate(cells):
        col, row = idx % 2, idx // 2
        x0 = margin + col * (card_w + gap)
        y0 = top + row * (card_h + gap)
        x1, y1 = x0 + card_w, y0 + card_h

        if key == "__today__":
            # 今日合计：黄底强调（黄色改作"重点信息"语义，不再做告警色）
            d.rectangle([x0, y0, x1, y1], fill=YELLOW, outline=BLACK, width=2)
            name, state_line = "今日合计", "全部渠道"
            total = today_total
            month_total = sum(c.get("usage", {}).get("30", {}).get("total_tokens", 0)
                              for c in channels.values())
            stripe = None
            sub = f"30天 {fmt_tokens(month_total)}"
        else:
            d.rectangle([x0, y0, x1, y1], outline=BLACK, width=2)
            stripe = state_color(ch.get("state", "offline"))
            name = CHANNEL_NAMES.get(key, key)
            state_line = state_text(key, ch)
            total = ch.get("usage", {}).get("1", {}).get("total_tokens", 0)
            month_total = ch.get("usage", {}).get("30", {}).get("total_tokens", 0)
            sub = f"30天 {fmt_tokens(month_total)}"

        if stripe:
            d.rectangle([x0, y0, x0 + 6, y1], fill=stripe)
        d.text((x0 + 15, y0 + 6), name, font=font(15, bold=True), fill=BLACK)
        d.text((x0 + 15, y0 + 27), state_line, font=font(12, bold=True), fill=BLACK)
        d.text((x0 + 15, y0 + 47), fmt_tokens(total), font=font(28, bold=True), fill=BLACK)
        d.text((x0 + 15, y0 + 85), sub, font=font(12, bold=True), fill=BLACK)

    # 底部状态条
    draw_footer(d, updated, device_status)

    return img


def render_offline():
    """监控服务不可用时的红色告警页。"""
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 26], fill=RED)
    d.text((10, 5), "Codex 用量监控", font=font(15, bold=True), fill=WHITE)
    d.rectangle([20, 90, W - 20, 190], outline=RED, width=3)
    d.text((40, 110), "监控服务离线", font=font(26, bold=True), fill=RED)
    d.text((40, 152), "127.0.0.1:18741 无响应", font=font(13, bold=True), fill=BLACK)
    d.rectangle([0, H - 22, W, H], fill=BLACK)
    now = datetime.datetime.now().strftime("%m-%d %H:%M")
    d.text((10, H - 18), f"告警 {now}", font=font(12, bold=True), fill=WHITE)
    return img


def render_or_fallback():
    """拉快照渲染；失败时返回告警页。返回 (image, ok)。"""
    try:
        return render(fetch_snapshot()), True
    except Exception:
        return render_offline(), False


def quantize_bwry(img):
    """逐像素映射到调色板色。

    近灰像素（含文字抗锯齿边）单独走亮度阈值，阈值取 105：
    黑底白字的小字笔画不会被吃掉，白底黑字仍保持实心。
    """
    px = img.load()
    out = Image.new("RGB", (W, H), WHITE)
    op = out.load()
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            if mx - mn <= 28:  # 近灰
                luma = 0.299 * r + 0.587 * g + 0.114 * b
                op[x, y] = WHITE if luma > 105 else BLACK
                continue
            best, bd = BLACK, 1 << 30
            for c in PALETTE:
                dist = (0.299 * (r - c[0]) ** 2 +
                        0.587 * (g - c[1]) ** 2 +
                        0.114 * (b - c[2]) ** 2)
                if dist < bd:
                    bd, best = dist, c
            op[x, y] = best
    return out


def quantize_bwry_dithered(img):
    """Floyd–Steinberg 误差扩散到四色调色板（照片类内容用，观感更像图片）。"""
    src = img.convert("RGB")
    w, h = src.size
    px = [[list(src.getpixel((x, y))) for x in range(w)] for y in range(h)]
    out = Image.new("RGB", (w, h), WHITE)
    op = out.load()

    def nearest(r, g, b):
        best, bd = BLACK, 1 << 30
        for c in PALETTE:
            dist = (0.299 * (r - c[0]) ** 2 + 0.587 * (g - c[1]) ** 2 + 0.114 * (b - c[2]) ** 2)
            if dist < bd:
                bd, best = dist, c
        return best

    for y in range(h):
        for x in range(w):
            r, g, b = px[y][x]
            r = max(0, min(255, r)); g = max(0, min(255, g)); b = max(0, min(255, b))
            c = nearest(r, g, b)
            op[x, y] = c
            er, eg, eb = r - c[0], g - c[1], b - c[2]
            for dx, dy, f in ((1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    px[ny][nx][0] += er * f
                    px[ny][nx][1] += eg * f
                    px[ny][nx][2] += eb * f
    return out


def pack_2bpp(img):
    """400×300 四色图 → 30000 字节 2bpp 原始数据（设备 /upload 用）。"""
    codes = {BLACK: 0, WHITE: 1, YELLOW: 2, RED: 3}
    px = img.load()
    buf = bytearray(W * H // 4)
    for i in range(W * H):
        x, y = i % W, i // W
        buf[i >> 2] |= codes[px[x, y]] << (6 - (i & 3) * 2)
    return bytes(buf)
