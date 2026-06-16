# /// script
# dependencies = ["matplotlib", "numpy", "pillow", "pandas"]
# ///
"""
ヒートマップの仕組みを説明する図を生成する。
output/explain_heatmap.png に保存。
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR  = os.path.join(PROJECT_ROOT, "data", "Aid-80070001-0000-2000-9002-000000000cc9",
                         "20260616013730349", "inferences", "deserialized_inferences")
IMG_DIR   = os.path.join(PROJECT_ROOT, "data", "Aid-80070001-0000-2000-9002-000000000cc9",
                         "20260616013730349", "images")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

# フレームデータ読み込み
json_files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".json"))
img_files  = sorted(f for f in os.listdir(IMG_DIR)  if f.endswith(".jpg"))

SHOW_FRAMES = [0, 12, 24, 36, 49]  # 表示するフレームのインデックス

# 全フレームのグリッド累積
grid = np.zeros((320, 320), dtype=float)
for jf in json_files:
    with open(os.path.join(DATA_DIR, jf)) as f:
        d = json.load(f)
    for k, v in d.items():
        if k == "T":
            continue
        x1, y1, x2, y2 = v["X"], v["Y"], v["x"], v["y"]
        grid[y1:y2, x1:x2] += 1

# ===== レイアウト =====
# 上段: 選択フレーム × 5  下段左: 累積イメージ  下段右: 最終ヒートマップ
fig = plt.figure(figsize=(14, 8))
fig.patch.set_facecolor("#f8f8f8")

COLS = len(SHOW_FRAMES)
gs = fig.add_gridspec(2, COLS + 2, hspace=0.45, wspace=0.3,
                      left=0.04, right=0.97, top=0.88, bottom=0.05)

# ----- 上段: 選択フレーム -----
for col, fi in enumerate(SHOW_FRAMES):
    ax = fig.add_subplot(gs[0, col])
    jf = json_files[fi]
    imf = img_files[fi]
    img = Image.open(os.path.join(IMG_DIR, imf))
    W, H = img.size
    ax.imshow(img)
    ax.axis("off")

    with open(os.path.join(DATA_DIR, jf)) as f:
        d = json.load(f)
    ts = pd.to_datetime(d["T"]).strftime("%H:%M:%S")
    ax.set_title(f"Frame {fi}  {ts}", fontsize=8, pad=3)

    for k, v in d.items():
        if k == "T":
            continue
        x1 = v["X"] * W / 320
        y1 = v["Y"] * H / 320
        x2 = v["x"] * W / 320
        y2 = v["y"] * H / 320
        rect = patches.Rectangle((x1, y1), x2-x1, y2-y1,
                                  linewidth=1.2, edgecolor="#2196F3", facecolor="#2196F3", alpha=0.25)
        ax.add_patch(rect)

# 上段の矢印（最後のフレームの右）
ax_arrow = fig.add_subplot(gs[0, COLS])
ax_arrow.axis("off")
ax_arrow.text(0.5, 0.55, "all\nframes\n+", ha="center", va="center",
              fontsize=10, color="#555", transform=ax_arrow.transAxes)

# ----- 下段左: 累積イメージ（グリッドそのまま） -----
ax_acc = fig.add_subplot(gs[1, :COLS])
im = ax_acc.imshow(grid, cmap="Blues", origin="upper", aspect="auto")
ax_acc.set_title("Add +1 to every pixel inside each bounding box\n(50 frames x detections per frame)",
                 fontsize=8, pad=4)
ax_acc.set_xlabel("x  (0 - 320)", fontsize=7)
ax_acc.set_ylabel("y  (0 - 320)", fontsize=7)
ax_acc.tick_params(labelsize=6)
plt.colorbar(im, ax=ax_acc, label="count", shrink=0.8)

# 累積→ヒートマップの矢印
ax_arrow2 = fig.add_subplot(gs[1, COLS])
ax_arrow2.axis("off")
ax_arrow2.text(0.5, 0.5, "->", ha="center", va="center",
               fontsize=14, color="#555", transform=ax_arrow2.transAxes)

# ----- 下段右: 最終ヒートマップ -----
ax_heat = fig.add_subplot(gs[1, COLS+1])
im2 = ax_heat.imshow(grid, cmap="Blues", origin="upper")
ax_heat.set_title("Heatmap\n(darker = bike appeared more often)", fontsize=8, pad=4)
ax_heat.axis("off")
plt.colorbar(im2, ax=ax_heat, label="count", shrink=0.8)

# 全体タイトル
fig.suptitle("How the heatmap works: accumulate bounding boxes from each frame into a 320x320 grid",
             fontsize=11, fontweight="bold", y=0.97)

out = os.path.join(OUTPUT_DIR, "explain_heatmap.png")
plt.savefig(out, dpi=120, facecolor=fig.get_facecolor())
plt.close()
print(f"保存: {out}")
