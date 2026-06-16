# /// script
# dependencies = ["matplotlib", "pillow", "numpy", "pandas"]
# ///
"""
駐輪場監視システムのリアルタイムデモ。
フレームを順番に再生し、禁止ゾーンに自転車が入ると ILLEGAL アラートを表示する。

実行:
  uv run --no-project scripts/demo.py
  uv run --no-project scripts/demo.py --fps 4   # 再生速度変更
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib
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
BICYCLE_CLASS_ID = 0


def point_in_polygon(px, py, polygon):
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def is_illegal(cx, cy):
    return any(point_in_polygon(cx, cy, z["polygon"]) for z in NO_PARKING_ZONES)


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fps", type=float, default=3, help="再生フレームレート")
    args = parser.parse_args()

    frames, img_files = load_data()
    print(f"フレーム数: {len(frames)}")

    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor("#111")
    plt.subplots_adjust(top=0.88, bottom=0.04, left=0.02, right=0.98)

    alert_text = fig.text(0.5, 0.95, "", ha="center", va="top",
                          fontsize=16, fontweight="bold", color="red",
                          transform=fig.transFigure)
    illegal_count_text = fig.text(0.02, 0.96, "", ha="left", va="top",
                                  fontsize=10, color="white",
                                  transform=fig.transFigure)

    illegal_total = [0]

    def draw_frame(fi):
        ax.cla()
        ax.axis("off")

        frame = frames[fi]
        frame_ts = pd.to_datetime(frame["T"])
        img_fn = find_image(frame_ts, img_files)

        if img_fn:
            img = Image.open(os.path.join(IMAGE_DIR, img_fn))
            W, H = img.size
            ax.imshow(img)
        else:
            W, H = 320, 320

        ax.set_title(f"Frame {fi+1}/{len(frames)}   {frame_ts.strftime('%H:%M:%S')}",
                     fontsize=10, color="white", pad=6,
                     bbox=dict(facecolor="#222", edgecolor="none", pad=4))
        fig.patch.set_facecolor("#111")

        # 禁止ゾーン描画
        for z in NO_PARKING_ZONES:
            pts = [(x * W / 320, y * H / 320) for x, y in z["polygon"]]
            poly = patches.Polygon(pts, closed=True,
                                   edgecolor="#e05c00", facecolor="#e05c00", alpha=0.18,
                                   linewidth=2, linestyle="--")
            ax.add_patch(poly)
            ax.text(pts[0][0], pts[0][1] - 8, z["name"],
                    color="#e05c00", fontsize=8, fontweight="bold")

        # 検出結果描画
        frame_illegal = False
        for k, v in frame.items():
            if k == "T" or not isinstance(v, dict):
                continue
            if v.get("C") != BICYCLE_CLASS_ID:
                continue
            cx = (v["X"] + v["x"]) / 2
            cy = (v["Y"] + v["y"]) / 2
            illegal = is_illegal(cx, cy)

            x1 = v["X"] * W / 320
            y1 = v["Y"] * H / 320
            x2 = v["x"] * W / 320
            y2 = v["y"] * H / 320

            if illegal:
                color = "#ff3333"
                frame_illegal = True
                rect = patches.Rectangle((x1, y1), x2-x1, y2-y1,
                                         linewidth=2.5, edgecolor=color, facecolor=color, alpha=0.2)
                ax.add_patch(rect)
                ax.text(x1, y1 - 10, "ILLEGAL", color=color, fontsize=10,
                        fontweight="bold",
                        bbox=dict(facecolor="#111", edgecolor=color, pad=2))
            else:
                color = "#44cc66"
                rect = patches.Rectangle((x1, y1), x2-x1, y2-y1,
                                         linewidth=1.5, edgecolor=color, facecolor="none")
                ax.add_patch(rect)
                ax.text(x1, y1 - 8, "OK", color=color, fontsize=8,
                        bbox=dict(facecolor="#111", edgecolor="none", alpha=0.5, pad=1))

        # アラート表示
        if frame_illegal:
            illegal_total[0] += 1
            alert_text.set_text("!  ILLEGAL PARKING DETECTED  !")
            fig.patch.set_facecolor("#2a0000")
        else:
            alert_text.set_text("")
            fig.patch.set_facecolor("#111")

        illegal_count_text.set_text(f"Alerts: {illegal_total[0]}")

    ani = animation.FuncAnimation(
        fig, draw_frame,
        frames=len(frames),
        interval=int(1000 / args.fps),
        repeat=True,
    )

    plt.show()


if __name__ == "__main__":
    main()
