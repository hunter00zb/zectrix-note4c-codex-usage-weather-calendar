#!/usr/bin/env python3
"""NOTE4C Codex 监控独立推送脚本（Plan A 用；TRMNL 拉图模式下由 CodexPlugin 替代）.

用法:
  python3 render_codex.py                    # 渲染，输出预览 PNG + 2bpp bin
  python3 render_codex.py --device <DEVICE_IP> --push --meta "Codex用量监控"
"""

import argparse
import sys

import note4c_render as R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", help="NOTE4C 局域网 IP")
    ap.add_argument("--push", action="store_true", help="推送到设备")
    ap.add_argument("--meta", help="上传后设置的图片标题")
    args = ap.parse_args()

    img, ok = R.render_or_fallback()
    if not ok:
        print("监控服务不可用，已生成离线告警页")

    img.save("preview_color.png")
    q = R.quantize_bwry(img)
    q.save("preview_bwry.png")
    data = R.pack_2bpp(q)
    assert len(data) == 30000, f"2bpp 数据大小错误: {len(data)}"
    with open("codex_dashboard_400x300_2bpp.bin", "wb") as f:
        f.write(data)
    print("rendered · bin 30000 bytes · preview_color.png / preview_bwry.png")

    if args.push:
        if not args.device:
            sys.exit("需要 --device <设备IP>")
        import json
        import urllib.request

        device = args.device
        req = urllib.request.Request(
            f"http://{device}/upload?format=bwry2bpp", data=data, method="POST",
            headers={"Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        print(f"upload -> {result}")
        if not result.get("success"):
            sys.exit(f"上传失败: {result.get('error')}")
        photo_id = result.get("id", "")

        if args.meta:
            meta = json.dumps({"id": photo_id, "title": args.meta,
                               "location": "Mac", "body": "Codex 用量监控"}).encode()
            mreq = urllib.request.Request(
                f"http://{device}/photo/meta", data=meta, method="POST",
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(mreq, timeout=10) as resp:
                print(f"meta   -> {json.loads(resp.read())}")

        # 新固件支持 /photo/show；旧固件 404 则提示回相册查看
        try:
            sreq = urllib.request.Request(
                f"http://{device}/photo/show",
                data=json.dumps({"id": photo_id}).encode(), method="POST",
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(sreq, timeout=10) as resp:
                print(f"show   -> {json.loads(resp.read())}")
        except Exception:
            print("show   -> 设备不支持立即显示，请回相册页查看")


if __name__ == "__main__":
    main()
