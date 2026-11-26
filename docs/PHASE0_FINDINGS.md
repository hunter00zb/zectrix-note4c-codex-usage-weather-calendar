Phase 0 预研结论 (2026-11-25 14:00)
1. 固件: atchoum31/trmnl-firmware-note4c v1.8.19-note4c (2026-11-14)
   - merged-firmware.bin 刷 0x0（会清 Wi-Fi/服务器设置，需重新配网）
   - SHA256SUMS 校验; 回退=刷回 demo v6.5.9 bin 或 16MB 原厂备份
   - 按钮: 下侧键=唤醒+播放列表下一屏; 上侧键睡眠中不可唤醒(硬件限制)
   - OTA: 老版本刷机一次 USB 后才有
2. 服务器选型: usetrmnl/byos_fastapi (FastAPI, Python, Mac 原生跑, 默认端口 4567)
   - 实现完整设备 API: /api/display (image_url+filename token), /api/setup (配网), /api/log, /api/battery
   - 插件管线 (Pillow) 生成 BMP/PNG; SQLite 设备/播放列表; Web 预览 UI
   - 选它而非自研小服务: 设备固件依赖完整生命周期端点, 自研易漏
3. 渲染对接: 我们的 render_codex.py 产出精确四色 PNG → 接入 BYOS 插件管线
   - 设备端做 BWRY 转换; 精确调色板输入 → 无损映射 (Phase 2 联调验证)
4. 设备指向: 配网时填 http://<Mac_IP>:4567
