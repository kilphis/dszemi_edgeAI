# /// script
# dependencies = ["pandas", "matplotlib", "pillow"]
# ///
"""
ds1ai_app.ipynb のローカル実行版。
Google Drive マウント部分を除去し、ローカルパスで動作する。
"""

import os
import json
import re
import matplotlib
matplotlib.use("Agg")
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image

# ===== パス設定 =====
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
inference_data_dir = os.path.join(PROJECT_ROOT, "data", "handson_0602", "inferences", "deserialized_inferences")
image_dir          = os.path.join(PROJECT_ROOT, "data", "handson_0602", "images")
OUTPUT_DIR         = os.path.join(PROJECT_ROOT, "output")

print(f"推論データ: {inference_data_dir}")
print(f"画像データ:  {image_dir}")

# ===== クラス設定 =====
class_map = {
    0: "class0",
    1: "class1",
    2: "class2",
}
target_class_id = 0
colors = {0: "green", 1: "gray", 2: "blue"}
threshold = 3

# ===== データ読み込み =====
def load_inference_data(directory: str) -> list[dict]:
    data = []
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            with open(os.path.join(directory, filename), encoding="utf-8") as f:
                data.append(json.load(f))
    data.sort(key=lambda x: pd.to_datetime(x["T"]))
    return data

def convert_to_df(data: list[dict]) -> pd.DataFrame:
    records = []
    for i, frame in enumerate(data):
        timestamp = pd.to_datetime(frame["T"])
        counts = {f"count_{label}": 0 for label in class_map.values()}
        for key, val in frame.items():
            if key == "T" or not isinstance(val, dict):
                continue
            cls_id = val.get("C")
            if cls_id in class_map:
                counts[f"count_{class_map[cls_id]}"] += 1
        records.append({"frame_index": i, "timestamp": timestamp, **counts})
    return pd.DataFrame(records)

raw_data = load_inference_data(inference_data_dir)
df = convert_to_df(raw_data)
image_files = sorted(f for f in os.listdir(image_dir) if f.endswith((".jpg", ".jpeg", ".png")))

print(f"読み込んだフレーム数: {len(raw_data)}")

# ===== 時系列グラフ =====
plt.figure(figsize=(10, 4))
for cls_id, label in class_map.items():
    plt.plot(df["frame_index"], df[f"count_{label}"], label=label, marker="o")

for _, row in df.iterrows():
    if row[f"count_{class_map[target_class_id]}"] >= threshold:
        plt.axvspan(row["frame_index"] - 0.5, row["frame_index"] + 0.5, color="red", alpha=0.1)
        print(f"ALERT: {class_map[target_class_id]} が {threshold} 個以上 (frame {row['frame_index']})")

plt.title("Detection Count Over Frame Index")
plt.xlabel("Frame Index")
plt.ylabel("Count")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "output_count.png"), dpi=100)
plt.close()

# ===== 画像への BB 重畳 =====
def find_matching_image(frame_ts: pd.Timestamp, files: list[str]) -> str | None:
    best, best_diff = None, float("inf")
    for f in files:
        stem = os.path.splitext(f)[0]
        try:
            img_ts = pd.to_datetime(stem, format="%Y%m%d%H%M%S%f")
        except ValueError:
            try:
                img_ts = pd.to_datetime(stem)
            except ValueError:
                continue
        diff = abs((img_ts - frame_ts).total_seconds())
        if diff < best_diff:
            best, best_diff = f, diff
    return best

for i, frame in enumerate(raw_data):
    frame_ts = pd.to_datetime(frame["T"])
    img_file = find_matching_image(frame_ts, image_files)
    if img_file is None:
        print(f"Frame {i}: 対応画像なし")
        continue

    img = Image.open(os.path.join(image_dir, img_file))
    W, H = img.size
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(img)
    ax.set_title(f"Frame {i}  {frame_ts.strftime('%H:%M:%S')}")
    ax.axis("off")

    target_count = 0
    for key, val in frame.items():
        if key == "T" or not isinstance(val, dict):
            continue
        cls_id = val.get("C")
        if cls_id not in class_map:
            continue
        label = class_map[cls_id]
        color = colors.get(cls_id, "black")
        if cls_id == target_class_id:
            target_count += 1
        x1, y1 = val["X"] * W / 320, val["Y"] * H / 320
        x2, y2 = val["x"] * W / 320, val["y"] * H / 320
        rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, linewidth=2, edgecolor=color, facecolor="none")
        ax.add_patch(rect)
        ax.text(x1, y1 - 10, label, color=color, fontsize=10, weight="bold",
                bbox=dict(facecolor="white", alpha=0.5, pad=2))

    if target_count >= threshold:
        fig.patch.set_edgecolor(colors[target_class_id])
        fig.patch.set_linewidth(5)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"output_frame_{i:03d}.png"), dpi=80)
    plt.close(fig)

print(f"完了。{OUTPUT_DIR}/ の output_*.png を確認してください。")
