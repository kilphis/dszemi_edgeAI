# /// script
# dependencies = ["matplotlib", "pillow", "numpy", "pandas"]
# ///
"""
【デモ2】放置自転車の検出
同一個体が THRESHOLD 秒以上同じ場所に留まると ABANDONED アラートを表示する。
各自転車に滞在タイマーバーを表示してカウントアップを可視化する。

実行:
  uv run --no-project scripts/demo_abandoned.py
  uv run --no-project scripts/demo_abandoned.py --threshold 30  # 30秒で発火
  uv run --no-project scripts/demo_abandoned.py --fps 2
"""

import os, sys, json, argparse
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.animation as animation
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tracker.py を import するため

from tracker import run_tracking

DATA_DIR  = os.path.join(PROJECT_ROOT, "data", "Aid-80070001-0000-2000-9002-000000000cc9",
                         "20260616013730349", "inferences", "deserialized_inferences")
IMAGE_DIR = os.path.join(PROJECT_ROOT, "data", "Aid-80070001-0000-2000-9002-000000000cc9",
                         "20260616013730349", "images")
DEMO_VIDEO_FRAMES_DIR = os.path.join(PROJECT_ROOT, "data", "demo_video", "frames")

BICYCLE_CLASS_ID = 0


def load_data():
    json_files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".json"))
    img_files  = sorted(f for f in os.listdir(IMAGE_DIR) if f.endswith(".jpg"))
    frames = [json.load(open(os.path.join(DATA_DIR, jf))) for jf in json_files]
    return frames, img_files

def find_image(frame_ts, img_files):
    best, best_diff = None, float("inf")
    for fn in img_files:
        try:
            img_ts = pd.to_datetime(os.path.splitext(fn)[0], format="%Y%m%d%H%M%S%f")
        except ValueError:
            continue
        diff = abs((img_ts - frame_ts).total_seconds())
        if diff < best_diff:
            best, best_diff = fn, diff
    return best

def get_demo_video_frame(frame_index, num_frames):
    """推論フレーム番号をデモ動画フレーム番号にスケーリング"""
    demo_frame_idx = int(frame_index * 1799 / num_frames) + 1  # frame_000001.jpg から開始
    frame_file = f"frame_{demo_frame_idx:06d}.jpg"
    frame_path = os.path.join(DEMO_VIDEO_FRAMES_DIR, frame_file)
    return frame_path if os.path.exists(frame_path) else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fps",         type=float, default=1)
    parser.add_argument("--threshold",   type=float, default=60,
                        help="放置判定の秒数（デフォルト60秒）")
    parser.add_argument("--strategy",    default="naive", choices=["naive", "greedy"],
                        help="追跡アルゴリズム（naive=旧実装 / greedy=改良版）")
    parser.add_argument("--save-frames", type=int, default=0, metavar="N",
                        help="アニメーションを表示せず最初の N フレームを output/ に保存する")
    args = parser.parse_args()

    frames, img_files = load_data()
    _, snapshots, _ = run_tracking(frames, threshold_sec=args.threshold, strategy=args.strategy)
    print(f"フレーム数: {len(frames)}  放置閾値: {args.threshold}秒  strategy: {args.strategy}")

    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor("#111")
    plt.subplots_adjust(top=0.88, bottom=0.04, left=0.02, right=0.98)

    alert_text = fig.text(0.5, 0.95, "", ha="center", va="top",
                          fontsize=15, fontweight="bold",
                          transform=fig.transFigure)
    threshold_text = fig.text(0.98, 0.96, f"Threshold: {args.threshold:.0f}s",
                              ha="right", va="top", fontsize=9,
                              color="#aaa", transform=fig.transFigure)

    def draw_frame(fi):
        ax.cla()
        ax.axis("off")
        frame = frames[fi]
        snap  = snapshots[fi]
        frame_ts = pd.to_datetime(frame["T"])

        # デモ動画フレームを優先的に使う
        demo_frame_path = get_demo_video_frame(fi, len(frames))
        if demo_frame_path:
            img = Image.open(demo_frame_path)
            W, H = img.size
            ax.imshow(img)
        else:
            # フォールバック：元のカメラ画像を使う
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

        has_abandoned = False

        for (tid, stay, abandoned, x1, y1, x2, y2) in snap:
            px1, py1 = x1*W/320, y1*H/320
            px2, py2 = x2*W/320, y2*H/320
            bw = px2 - px1

            if abandoned:
                has_abandoned = True
                color = "#ffcc00"
                edge_w = 3.0
                label = f"ABANDONED  {stay:.0f}s"
            else:
                ratio = min(stay / args.threshold, 1.0)
                # 時間が経つほど緑→黄→橙へ
                r = min(1.0, ratio * 2)
                g = min(1.0, 2 - ratio * 2) if ratio > 0.5 else 1.0
                color = (r, g, 0.1)
                edge_w = 1.5
                label = f"#{tid}  {stay:.0f}s"

            # バウンディングボックス
            ax.add_patch(patches.Rectangle(
                (px1, py1), bw, py2-py1,
                linewidth=edge_w, edgecolor=color, facecolor=color, alpha=0.15
            ))
            # ラベル
            ax.text(px1, py1-10, label, color=color, fontsize=8, fontweight="bold",
                    bbox=dict(facecolor="#111", edgecolor="none", alpha=0.6, pad=1))

            # タイマーバー（BB下部）
            ratio = min(stay / args.threshold, 1.0)
            ax.add_patch(patches.Rectangle(
                (px1, py2+2), bw, 5,
                facecolor="#333", linewidth=0
            ))
            ax.add_patch(patches.Rectangle(
                (px1, py2+2), bw * ratio, 5,
                facecolor=color, linewidth=0, alpha=0.9
            ))

        if has_abandoned:
            alert_text.set_text("!!  ABANDONED BIKE DETECTED  !!")
            alert_text.set_color("#ffcc00")
            fig.patch.set_facecolor("#1a1400")
        else:
            alert_text.set_text("")
            fig.patch.set_facecolor("#111")

    if args.save_frames > 0:
        import matplotlib
        matplotlib.use("Agg")
        out_dir = os.path.join(PROJECT_ROOT, "output")
        os.makedirs(out_dir, exist_ok=True)
        n = min(args.save_frames, len(frames))
        for fi in range(n):
            draw_frame(fi)
            ts_str = pd.to_datetime(frames[fi]["T"]).strftime("%H%M%S")
            path = os.path.join(out_dir, f"demo_abandoned_{args.strategy}_f{fi+1:02d}_{ts_str}.png")
            fig.savefig(path, dpi=120, facecolor=fig.get_facecolor())
            print(f"保存: {path}")
        plt.close(fig)
    else:
        ani = animation.FuncAnimation(fig, draw_frame, frames=len(frames),
                                      interval=int(1000/args.fps), repeat=True)
        plt.show()

if __name__ == "__main__":
    main()
