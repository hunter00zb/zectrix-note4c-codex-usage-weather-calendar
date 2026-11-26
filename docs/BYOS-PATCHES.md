# 对 BYOS 的三处改动

基础服务：`usetrmnl/byos_fastapi`（仓库根目录的 `server/byos_fastapi`）。
以下改动均针对 **四色墨水屏 + TRMNL 固件** 的实测问题，灰阶设备不需要。

---

## 1. `/api/display` 的 filename token 改为内容哈希驱动

**文件**：`trmnl_server/routes/api.py`（`display` 处理函数内，构建 `response` 之前）

**问题**：原实现把请求序号、请求计数混入 salt，导致每次轮询 token 都变，设备据此判定「图变了」→ 每次轮询都整屏重刷，对四色面板是很重的损耗。

**改动**：

```python
entry_hash = device_state.get('last_entry_hash') or str(entry_idx)
# 内容签名驱动 filename：内容不变 → token 不变 → 设备跳过刷屏（保护墨水屏）
content_sig = ''
try:
    _meta = (state.rotation_master().get('meta') or [])
    if 0 <= int(entry_idx) < len(_meta):
        content_sig = str(_meta[int(entry_idx)].get('hash') or '')
except Exception:
    content_sig = ''
salt = f"{device_id}-{content_sig or entry_hash}"
token = sha256(salt.encode('utf-8')).hexdigest()[:16]
```

**配套**：插件侧也要做内容去重（`plugin/codex.py` 的 `.hash` 文件比对），数据没变就不重写资产，条目内容哈希才不会变。

---

## 2. 轮播条目只保留 Codex

**文件**：`trmnl_server/services/state.py`（`_select_next_playlist_entry`）

**问题**：播放列表条目 id 形如 `CodexPlugin:/generated/codex/codex.bmp|...png#1`，后缀是动态的；服务重启后持久化的播放列表会对不上，设备开始轮播 Bing 壁纸 / XKCD / Hacker News。

**改动**（`if not playlist_indexes:` 之前插入）：

```python
master = rotation_master()
meta_all = master.get('meta') or []
codex_indexes = [
    i for i in playlist_indexes
    if 0 <= i < len(meta_all) and 'codex' in str(meta_all[i].get('plugin', '')).lower()
]
if codex_indexes:
    playlist_indexes = codex_indexes
```

---

## 3. 图片只走 PNG 通道

**文件**：同 `trmnl_server/routes/api.py`

**问题**：四色固件对 BMP 走的是「按 1-bit 位图写 plane + PARTIAL 刷新」的老路径，在 SSD2683 四色面板上等于空操作——**屏幕完全不闪、也不报错**，表现为「拉了图但屏幕没动」。PNG 才会进 `png_to_epd → png_draw_4clr` 的四色全刷路径。

保持 BYOS 原有的 `grayscale_ready = utils.firmware_supports_grayscale(fw_version)`，然后确保插件产出的 **PNG 就是最终要显示的画面**：

- 400×300
- 模式 `P`（索引色），调色板顺序 `[(0,0,0), (255,255,255), (255,255,0), (255,0,0)]`
- 每像素索引即设备颜色码：黑 0 / 白 1 / 黄 2 / 红 3

**不要**让 BYOS 对图片再做灰阶化处理（`save_display_assets` 会被插件的 `save_assets` 覆盖，务必保持覆盖）。

---

## 调试小抄

```bash
# 服务是否活着 + 当前下发地址
curl -s http://127.0.0.1:4567/api/display -H "fw-version: 1.8.19" -H "id: <MAC>"

# 设备最近上报的电量/RSSI
curl -s http://127.0.0.1:4567/server/battery | head -c 300

# 设备上传的错误日志（含固件文件行号，排障神器）
curl -s http://127.0.0.1:4567/server/log | head -c 1000

# 强制改刷新周期
curl -X PATCH http://127.0.0.1:4567/devices/<MAC> \
     -H "Content-Type: application/json" -d '{"refresh_interval":900}'
```
