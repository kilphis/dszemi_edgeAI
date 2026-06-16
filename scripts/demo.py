# /// script
# dependencies = ["matplotlib", "pillow", "numpy", "pandas"]
# ///
"""
【デモ1】禁止ゾーンへの侵入検出
フレームを順番に再生し、禁止ゾーンに自転車が入ると ILLEGAL アラートを表示する。

実行:
  uv run --no-project scripts/demo.py
  uv run --no-project scripts/demo.py --fps 4
"""

import os, sys, json, argparse
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
BICYCLE_CLASS_ID = 0


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
    parser.add_argument("--fps", type=float, default=3)
    args = parser.parse_args()

    frames, img_files = load_data()

    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor("#111")
    plt.subplots_adjust(top=0.88, bottom=0.04, left=0.02, right=0.98)

    alert_text = fig.text(0.5, 0.95, "", ha="center", va="top",
                          fontsize=16, fontweight="bold", color="red",
                          transform=fig.transFigure)
    count_text = fig.text(0.02, 0.96, "", ha="left", va="top",
                          fontsize=10, color="white", transform=fig.transFigure)
    alert_count = [0]

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

        for z in NO_PARKING_ZONES:
            pts = [(x*W/320, y*H/320) for x, y in z["polygon"]]
            ax.add_patch(patches.Polygon(pts, closed=True,
                edgecolor="#e05c00", facecolor="#e05c00", alpha=0.18,
                linewidth=2, linestyle="--"))
            ax.text(pts[0][0], pts[0][1]-8, z["name"],
                    color="#e05c00", fontsize=8, fontweight="bold")

        frame_illegal = False
        for k, v in frame.items():
            if k == "T" or not isinstance(v, dict):
                continue
            if v.get("C") != BICYCLE_CLASS_ID:
                continue
            cx = (v["X"] + v["x"]) / 2
            cy = (v["Y"] + v["y"]) / 2
            illegal = is_illegal(cx, cy)
            x1, y1 = v["X"]*W/320, v["Y"]*H/320
            x2, y2 = v["x"]*W/320, v["y"]*H/320

            if illegal:
                frame_illegal = True
                color = "#ff3333"
                label = "ILLEGAL"
            else:
                color = "#44cc66"
                label = "OK"

            ax.add_patch(patches.Rectangle((x1, y1), x2-x1, y2-y1,
                linewidth=2.5 if illegal else 1.5,
                edgecolor=color, facecolor=color, alpha=0.15))
            ax.text(x1, y1-10, label, color=color, fontsize=9, fontweight="bold",
                    bbox=dict(facecolor="#111", edgecolor="none", alpha=0.6, pad=1))

        if frame_illegal:
            alert_count[0] += 1
            alert_text.set_text("!  ILLEGAL PARKING DETECTED  !")
            fig.patch.set_facecolor("#2a0000")
        else:
            alert_text.set_text("")
            fig.patch.set_facecolor("#111")

        count_text.set_text(f"Alerts: {alert_count[0]}")

    ani = animation.FuncAnimation(fig, draw_frame, frames=len(frames),
                                  interval=int(1000/args.fps), repeat=True)
    plt.show()

if __name__ == "__main__":
    main()
