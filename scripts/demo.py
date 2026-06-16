# /// script
# dependencies = ["matplotlib", "pillow", "numpy", "pandas"]
# ///
"""
駐輪場監視システムのリアルタイムデモ。
- 禁止ゾーンに入ると ILLEGAL（赤）
- 同一個体が STAY_THRESHOLD 秒以上留まると ABANDONED（黄）

実行:
  uv run --no-project scripts/demo.py
  uv run --no-project scripts/demo.py --fps 4
  uv run --no-project scripts/demo.py --threshold 30   # 放置判定の秒数
"""

import os, sys, json, argparse
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.animation as animation
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

DATA_DIR  = os.path.join(PROJECT_ROOT, "data", "Aid-80070001-0000-2000-9002-000000000cc9",
                         "20260616013730349", "inferences", "deserialized_inferences")
IMAGE_DIR = os.path.join(PROJECT_ROOT, "data", "Aid-80070001-0000-2000-9002-000000000cc9",
                         "20260616013730349", "images")

NO_PARKING_ZONES = [
    {"name": "zone_1", "polygon": [(1, 251), (57, 319), (2, 318)]},
    {"name": "zone_2", "polygon": [(80, 319), (220, 212), (171, 190), (181, 186),
                                    (228, 204), (253, 194), (274, 203), (266, 319)]},
]
BICYCLE_CLASS_ID  = 0
COORD_MATCH_RADIUS = 30


# ===== ユーティリティ =====

def point_in_polygon(px, py, polygon):
    inside, n, j = False, len(polygon), len(polygon) - 1
    for i in range(n):
        xi, yi = polygon[i]; xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj-xi)*(py-yi)/(yj-yi)+xi):
            inside = not inside
        j = i
    return inside

def is_illegal(cx, cy):
    return any(point_in_polygon(cx, cy, z["polygon"]) for z in NO_PARKING_ZONES)


# ===== トラッキング（事前計算） =====

@dataclass
class Track:
    track_id: int
    first_seen: datetime
    last_seen: datetime
    last_cx: float
    last_cy: float
    stay_sec: float = 0.0
    abandoned: bool = False

def precompute_tracks(frames, threshold_sec):
    """全フレームを走査してトラックを計算し、フレームごとのスナップショットを返す。"""
    tracks: list[Track] = []
    next_id = 0
    snapshots = []   # フレームごとに [(track_id, cx, cy, stay_sec, abandoned, x1,y1,x2,y2), ...]

    for frame in frames:
        ts = pd.to_datetime(frame["T"]).to_pydatetime()
        frame_tracks = []

        for k, v in frame.items():
            if k == "T" or not isinstance(v, dict):
                continue
            if v.get("C") != BICYCLE_CLASS_ID:
                continue
            cx = (v["X"] + v["x"]) / 2
            cy = (v["Y"] + v["y"]) / 2

            # 既存トラックとマッチング
            matched = None
            for t in tracks:
                dist = ((cx - t.last_cx)**2 + (cy - t.last_cy)**2) ** 0.5
                if dist <= COORD_MATCH_RADIUS:
                    matched = t
                    break

            if matched:
                matched.last_seen = ts
                matched.last_cx = cx
                matched.last_cy = cy
                matched.stay_sec = (ts - matched.first_seen).total_seconds()
                matched.abandoned = matched.stay_sec >= threshold_sec
            else:
                matched = Track(next_id, ts, ts, cx, cy)
                next_id += 1
                tracks.append(matched)

            frame_tracks.append((matched.track_id, cx, cy, matched.stay_sec,
                                  matched.abandoned, v["X"], v["Y"], v["x"], v["y"]))

        snapshots.append(frame_tracks)

    return snapshots


# ===== データ読み込み =====

def load_data():
    json_files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".json"))
    img_files  = sorted(f for f in os.listdir(IMAGE_DIR) if f.endswith(".jpg"))
    frames = []
    for jf in json_files:
        with open(os.path.join(DATA_DIR, jf)) as f:
            frames.append(json.load(f))
    return frames, img_files

def find_image(frame_ts, img_files):
    best, best_diff = None, float("inf")
    for fn in img_files:
        stem = os.path.splitext(fn)[0]
        try:
            img_ts = pd.to_datetime(stem, format="%Y%m%d%H%M%S%f")
        except ValueError:
            continue
        diff = abs((img_ts - frame_ts).total_seconds())
        if diff < best_diff:
            best, best_diff = fn, diff
    return best


# ===== メイン =====

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fps",       type=float, default=3,  help="再生fps")
    parser.add_argument("--threshold", type=float, default=60, help="放置判定の秒数（デフォルト60秒）")
    args = parser.parse_args()

    frames, img_files = load_data()
    snapshots = precompute_tracks(frames, args.threshold)
    print(f"フレーム数: {len(frames)}  放置閾値: {args.threshold}秒")

    fig, (ax_main, ax_info) = plt.subplots(
        1, 2, figsize=(11, 6),
        gridspec_kw={"width_ratios": [3, 1]}
    )
    fig.patch.set_facecolor("#111")
    ax_info.set_facecolor("#1a1a1a")
    ax_info.axis("off")
    plt.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.04, wspace=0.04)

    alert_text = fig.text(0.38, 0.95, "", ha="center", va="top",
                          fontsize=14, fontweight="bold", color="red",
                          transform=fig.transFigure)

    def draw_frame(fi):
        ax_main.cla()
        ax_main.axis("off")
        ax_info.cla()
        ax_info.set_facecolor("#1a1a1a")
        ax_info.axis("off")

        frame = frames[fi]
        snap  = snapshots[fi]
        frame_ts = pd.to_datetime(frame["T"])
        img_fn   = find_image(frame_ts, img_files)

        if img_fn:
            img = Image.open(os.path.join(IMAGE_DIR, img_fn))
            W, H = img.size
            ax_main.imshow(img)
        else:
            W, H = 320, 320

        ax_main.set_title(f"Frame {fi+1}/{len(frames)}   {frame_ts.strftime('%H:%M:%S')}",
                          fontsize=10, color="white", pad=5,
                          bbox=dict(facecolor="#222", edgecolor="none", pad=3))

        # 禁止ゾーン
        for z in NO_PARKING_ZONES:
            pts = [(x*W/320, y*H/320) for x, y in z["polygon"]]
            ax_main.add_patch(patches.Polygon(
                pts, closed=True,
                edgecolor="#e05c00", facecolor="#e05c00", alpha=0.18,
                linewidth=2, linestyle="--"
            ))
            ax_main.text(pts[0][0], pts[0][1]-8, z["name"],
                         color="#e05c00", fontsize=8, fontweight="bold")

        # 検出 + トラック情報
        has_illegal = has_abandoned = False
        info_lines = [("Track", "Time", "Status")]

        for (tid, cx, cy, stay, abandoned, x1, y1, x2, y2) in snap:
            illegal = is_illegal(cx, cy)
            px1, py1 = x1*W/320, y1*H/320
            px2, py2 = x2*W/320, y2*H/320

            if abandoned:
                has_abandoned = True
                color = "#ffcc00"
                label = f"ABANDONED\n{stay:.0f}s"
                edge_w = 3.0
            elif illegal:
                has_illegal = True
                color = "#ff3333"
                label = "ILLEGAL"
                edge_w = 2.5
            else:
                color = "#44cc66"
                label = f"OK  {stay:.0f}s"
                edge_w = 1.5

            ax_main.add_patch(patches.Rectangle(
                (px1, py1), px2-px1, py2-py1,
                linewidth=edge_w, edgecolor=color,
                facecolor=color, alpha=0.15
            ))
            ax_main.text(px1, py1-10, label, color=color, fontsize=8,
                         fontweight="bold",
                         bbox=dict(facecolor="#111", edgecolor="none", alpha=0.6, pad=1))

            # 滞在タイムバー（BB の下に描画）
            bar_w = (px2 - px1)
            ratio = min(stay / args.threshold, 1.0)
            ax_main.add_patch(patches.Rectangle(
                (px1, py2+2), bar_w * ratio, 4,
                linewidth=0, facecolor=color, alpha=0.7
            ))

            status = "ABANDONED" if abandoned else ("ILLEGAL" if illegal else "OK")
            info_lines.append((f"#{tid}", f"{stay:.0f}s", status))

        # 右パネル: トラック一覧
        ax_info.set_title("Track list", fontsize=9, color="white", pad=4)
        y_pos = 0.95
        for i, (tid, t, st) in enumerate(info_lines):
            color = "white" if i == 0 else (
                "#ffcc00" if st == "ABANDONED" else
                "#ff3333" if st == "ILLEGAL" else "#44cc66"
            )
            ax_info.text(0.05, y_pos, f"{tid:>5}  {t:>6}  {st}", color=color,
                         fontsize=8, transform=ax_info.transAxes,
                         fontfamily="monospace")
            y_pos -= 0.055
            if y_pos < 0.05:
                break

        # アラートバナー
        if has_abandoned:
            alert_text.set_text("!! ABANDONED BIKE DETECTED !!")
            alert_text.set_color("#ffcc00")
            fig.patch.set_facecolor("#1a1400")
        elif has_illegal:
            alert_text.set_text("!  ILLEGAL PARKING DETECTED  !")
            alert_text.set_color("#ff3333")
            fig.patch.set_facecolor("#2a0000")
        else:
            alert_text.set_text("")
            fig.patch.set_facecolor("#111")

    ani = animation.FuncAnimation(
        fig, draw_frame,
        frames=len(frames),
        interval=int(1000 / args.fps),
        repeat=True,
    )
    plt.show()


if __name__ == "__main__":
    main()
