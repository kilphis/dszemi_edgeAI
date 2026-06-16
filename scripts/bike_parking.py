# /// script
# dependencies = ["pandas", "matplotlib", "pillow", "numpy"]
# ///
"""
放置自転車監視パイプライン（熊本市駐輪場エッジAI）

【自転車推論データが届いたら変更すること】
  1. DATA_DIR  → 自転車モデルの推論JSONディレクトリに変更
  2. class_map → 自転車モデルのクラス番号に合わせる（0=bicycle など）
  3. NO_PARKING_ZONES → 駐輪禁止エリアを実際の座標で定義

【現在の動作】
  既存サンプルデータ（ハンズオン用カラスデータ）を bicycle として読み込み、
  パイプライン全体が通ることを確認できる。
"""

import os
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # ディスプレイなし環境でも動作
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
from dataclasses import dataclass, field
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR   = os.path.join(PROJECT_ROOT, "output")

# =====================================================================
# [STUB 1] 推論データのパス
# 自転車モデルの推論JSONが届いたらここを変更する
#   例: DATA_DIR = os.path.join(PROJECT_ROOT, "data", "bike_0620", "inferences", "deserialized_inferences")
# =====================================================================
DATA_DIR  = os.path.join(PROJECT_ROOT, "data", "Aid-80070001-0000-2000-9002-000000000cc9", "20260616013730349", "inferences", "deserialized_inferences")
IMAGE_DIR = os.path.join(PROJECT_ROOT, "data", "Aid-80070001-0000-2000-9002-000000000cc9", "20260616013730349", "images")
# =====================================================================

# =====================================================================
# [STUB 2] クラスマップ
# 自転車モデルのトレーニング時のクラス番号に合わせること
#   例: モデルが class0=bicycle, class1=background なら
#       class_map = {0: "bicycle"}
# =====================================================================
class_map = {
    0: "bicycle",
}
BICYCLE_CLASS_ID = 0
# =====================================================================

# =====================================================================
# [STUB 3] 駐輪禁止エリア（座標系: 0〜320）
# カメラが斜めのため、矩形ではなくポリゴン（多角形）で定義する。
# pick_zone.py でクリックして頂点を取得 → ここに貼る。
# 座標は 0〜320 スケール。頂点は時計回りで列挙。
# =====================================================================
NO_PARKING_ZONES: list[dict] = [
    {
        "name": "aisle",
        "polygon": [(0, 230), (320, 270), (320, 320), (0, 320)],  # 手前の通路（台形）
    },
    {
        "name": "left_open",
        "polygon": [(0, 0), (110, 0), (110, 230), (0, 230)],      # 左側スペース外
    },
]
# =====================================================================

# =====================================================================
# [STUB 4] 放置自転車の判定パラメータ
# =====================================================================
STAY_TIME_THRESHOLD_MINUTES = 60   # この時間（分）を超えたら放置とみなす
COORD_MATCH_RADIUS = 30            # 同一自転車と判定する座標ズレの許容値（px, 0〜320基準）
# =====================================================================


# -----------------------------------------------------------------
# データ構造
# -----------------------------------------------------------------
@dataclass
class Detection:
    frame_idx: int
    timestamp: datetime
    class_id: int
    prob: float
    x1: int   # 左上 X (0-320)
    y1: int   # 左上 Y
    x2: int   # 右下 X
    y2: int   # 右下 Y

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2


@dataclass
class TrackedBike:
    track_id: int
    first_seen: datetime
    last_seen: datetime
    last_cx: float
    last_cy: float
    alert_sent: bool = False
    illegal: bool = False


# -----------------------------------------------------------------
# ユーティリティ
# -----------------------------------------------------------------
def point_in_polygon(px: float, py: float, polygon: list[tuple]) -> bool:
    """レイキャスティング法：点(px,py)がポリゴン内部かどうかを判定する。"""
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


def is_illegal(det: Detection) -> bool:
    """検出の重心(cx,cy)がいずれかの禁止ゾーンポリゴン内にあれば違法。"""
    return any(point_in_polygon(det.cx, det.cy, z["polygon"]) for z in NO_PARKING_ZONES)


def match_track(det: Detection, tracks: list[TrackedBike]) -> TrackedBike | None:
    for t in tracks:
        dist = ((det.cx - t.last_cx) ** 2 + (det.cy - t.last_cy) ** 2) ** 0.5
        if dist <= COORD_MATCH_RADIUS:
            return t
    return None


# -----------------------------------------------------------------
# データ読み込み
# -----------------------------------------------------------------
def load_frames(directory: str) -> list[dict]:
    frames = []
    for fn in os.listdir(directory):
        if fn.endswith(".json"):
            with open(os.path.join(directory, fn), encoding="utf-8") as f:
                frames.append(json.load(f))
    frames.sort(key=lambda x: pd.to_datetime(x["T"]))
    return frames


def parse_detections(frames: list[dict]) -> list[list[Detection]]:
    result = []
    for i, frame in enumerate(frames):
        ts = pd.to_datetime(frame["T"]).to_pydatetime()
        dets = []
        for key, val in frame.items():
            if key == "T" or not isinstance(val, dict):
                continue
            cls_id = val.get("C")
            if cls_id not in class_map:
                continue
            dets.append(Detection(
                frame_idx=i,
                timestamp=ts,
                class_id=cls_id,
                prob=val.get("P", 0.0),
                x1=val["X"], y1=val["Y"], x2=val["x"], y2=val["y"],
            ))
        result.append(dets)
    return result


# -----------------------------------------------------------------
# トラッキング
# -----------------------------------------------------------------
def run_tracking(all_dets: list[list[Detection]]) -> tuple[list[TrackedBike], list[dict]]:
    tracks: list[TrackedBike] = []
    events: list[dict] = []
    next_id = 0

    for frame_dets in all_dets:
        bike_dets = [d for d in frame_dets if d.class_id == BICYCLE_CLASS_ID]
        matched_track_ids = set()

        for det in bike_dets:
            track = match_track(det, [t for t in tracks if t.track_id not in matched_track_ids])
            if track is None:
                track = TrackedBike(
                    track_id=next_id,
                    first_seen=det.timestamp,
                    last_seen=det.timestamp,
                    last_cx=det.cx,
                    last_cy=det.cy,
                )
                tracks.append(track)
                next_id += 1
            else:
                track.last_seen = det.timestamp
                track.last_cx = det.cx
                track.last_cy = det.cy

            matched_track_ids.add(track.track_id)

            stay_min = (track.last_seen - track.first_seen).total_seconds() / 60
            illegal = is_illegal(det)

            if illegal and not track.illegal:
                track.illegal = True
                events.append({
                    "type": "ILLEGAL_PARK",
                    "track_id": track.track_id,
                    "timestamp": det.timestamp,
                    "cx": det.cx, "cy": det.cy,
                })

            if stay_min >= STAY_TIME_THRESHOLD_MINUTES and not track.alert_sent:
                track.alert_sent = True
                events.append({
                    "type": "ABANDONED",
                    "track_id": track.track_id,
                    "timestamp": det.timestamp,
                    "stay_minutes": stay_min,
                    "cx": det.cx, "cy": det.cy,
                })

    return tracks, events


# -----------------------------------------------------------------
# 可視化
# -----------------------------------------------------------------
def plot_count_timeline(frames: list[dict], all_dets: list[list[Detection]]) -> None:
    counts = [sum(1 for d in dets if d.class_id == BICYCLE_CLASS_ID) for dets in all_dets]
    timestamps = [pd.to_datetime(f["T"]) for f in frames]

    plt.figure(figsize=(10, 3))
    plt.plot(range(len(counts)), counts, marker="o", color="steelblue", label="bicycle count")
    plt.axhline(y=3, color="orange", linestyle="--", label="congestion line (example)")
    plt.title("Bicycle Detection Count per Frame")
    plt.xlabel("Frame Index")
    plt.ylabel("Count")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "bike_count.png")
    plt.savefig(out, dpi=100)
    plt.close()
    print(f"保存: {out}")


def plot_heatmap(all_dets: list[list[Detection]]) -> None:
    grid = np.zeros((320, 320), dtype=float)
    for dets in all_dets:
        for d in dets:
            if d.class_id == BICYCLE_CLASS_ID:
                grid[d.y1:d.y2, d.x1:d.x2] += 1

    plt.figure(figsize=(6, 6))
    plt.imshow(grid, cmap="hot", origin="upper")
    plt.colorbar(label="Cumulative detection count")
    for z in NO_PARKING_ZONES:
        rect = patches.Rectangle(
            (z["X"], z["Y"]), z["x"] - z["X"], z["y"] - z["Y"],
            linewidth=2, edgecolor="cyan", facecolor="none", linestyle="--",
        )
        plt.gca().add_patch(rect)
        plt.text(z["X"], z["Y"] - 5, z["name"], color="cyan", fontsize=8)
    plt.title("Bicycle Heatmap (cyan = no-parking zone)")
    plt.axis("off")
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "bike_heatmap.png")
    plt.savefig(out, dpi=100)
    plt.close()
    print(f"保存: {out}")


def overlay_frame(frame: dict, dets: list[Detection], frame_idx: int, events: list[dict]) -> None:
    image_files = sorted(f for f in os.listdir(IMAGE_DIR) if f.endswith((".jpg", ".jpeg", ".png")))
    frame_ts = pd.to_datetime(frame["T"])
    best, best_diff = None, float("inf")
    for fn in image_files:
        stem = os.path.splitext(fn)[0]
        try:
            img_ts = pd.to_datetime(stem, format="%Y%m%d%H%M%S%f")
        except ValueError:
            continue
        diff = abs((img_ts - frame_ts).total_seconds())
        if diff < best_diff:
            best, best_diff = fn, diff

    if best is None:
        return
    img = Image.open(os.path.join(IMAGE_DIR, best))
    W, H = img.size
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(img)
    ax.set_title(f"Frame {frame_idx}  {frame_ts.strftime('%H:%M:%S')}")
    ax.axis("off")

    for z in NO_PARKING_ZONES:
        pts = [(px * W / 320, py * H / 320) for px, py in z["polygon"]]
        poly = patches.Polygon(pts, closed=True,
                               linewidth=2, edgecolor="cyan", facecolor="cyan", alpha=0.15)
        ax.add_patch(poly)
        ax.text(pts[0][0], pts[0][1], z["name"], color="cyan", fontsize=8)

    frame_events = {e["track_id"] for e in events if e.get("timestamp") == frame_ts.to_pydatetime()}

    for d in dets:
        if d.class_id != BICYCLE_CLASS_ID:
            continue
        color = "red" if is_illegal(d) else "lime"
        x1, y1 = d.x1 * W / 320, d.y1 * H / 320
        x2, y2 = d.x2 * W / 320, d.y2 * H / 320
        rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1,
                                  linewidth=2, edgecolor=color, facecolor="none")
        ax.add_patch(rect)
        label_text = "ILLEGAL" if is_illegal(d) else "OK"
        ax.text(x1, y1 - 10, label_text, color=color,
                fontsize=9, weight="bold", bbox=dict(facecolor="white", alpha=0.5, pad=1))

    plt.tight_layout()
    ts_str = frame_ts.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(OUTPUT_DIR, f"bike_frame_{frame_idx:03d}_{ts_str}.png")
    plt.savefig(out, dpi=80)
    plt.close(fig)


# -----------------------------------------------------------------
# メイン
# -----------------------------------------------------------------
def print_todo_checklist() -> None:
    print("=" * 60)
    print("【TODO: 自転車推論データが届いたら対応すること】")
    print("=" * 60)
    print("[1] DATA_DIR を自転車モデルの推論JSONディレクトリに変更")
    print("    現在:", DATA_DIR)
    print("[2] class_map を自転車モデルのクラス番号に合わせる")
    print("    現在:", class_map)
    print("[3] NO_PARKING_ZONES を実際の駐輪場画像の座標で定義")
    print("    ヒント: backImage06-05/ の画像を開き、禁止エリアの")
    print("            左上(X,Y)・右下(x,y)を 0〜320 で計測する")
    print("[4] STAY_TIME_THRESHOLD_MINUTES を要件に合わせる")
    print("    現在:", STAY_TIME_THRESHOLD_MINUTES, "分")
    print("=" * 60)
    print()


def main() -> None:
    print_todo_checklist()

    if not os.path.isdir(DATA_DIR):
        print(f"ERROR: データディレクトリが見つかりません: {DATA_DIR}")
        sys.exit(1)

    print("推論データを読み込んでいます...")
    frames = load_frames(DATA_DIR)
    all_dets = parse_detections(frames)
    print(f"フレーム数: {len(frames)}")

    total_bikes = sum(sum(1 for d in dets if d.class_id == BICYCLE_CLASS_ID) for dets in all_dets)
    print(f"自転車検出総数: {total_bikes}")

    print("\nトラッキング実行中...")
    tracks, events = run_tracking(all_dets)
    print(f"追跡した自転車ユニーク数: {len(tracks)}")

    if events:
        print(f"\n発生したアラート ({len(events)}件):")
        for e in events:
            ts_str = e["timestamp"].strftime("%H:%M:%S")
            if e["type"] == "ILLEGAL_PARK":
                print(f"  [違法駐輪]  {ts_str}  track_id={e['track_id']}  cx={e['cx']:.0f} cy={e['cy']:.0f}")
            elif e["type"] == "ABANDONED":
                print(f"  [放置自転車] {ts_str}  track_id={e['track_id']}  滞在={e['stay_minutes']:.0f}分")
    else:
        print("\nアラートなし（データが少ないか、STUBゾーン設定が実態と合っていない）")

    print("\n可視化を生成しています...")
    plot_count_timeline(frames, all_dets)
    plot_heatmap(all_dets)

    # 最初の3フレームだけ画像重畳（多いと時間がかかる）
    for i in range(min(3, len(frames))):
        overlay_frame(frames[i], all_dets[i], i, events)

    print("\n完了。生成ファイル:")
    print("  bike_count.png   - 検出数の時系列グラフ")
    print("  bike_heatmap.png - 自転車の滞留ヒートマップ")
    print("  bike_frame_*.png - バウンディングボックス重畳画像（最初3枚）")


if __name__ == "__main__":
    main()
