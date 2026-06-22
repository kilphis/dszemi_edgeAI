# /// script
# dependencies = ["matplotlib", "pillow"]
# ///
"""
駐輪禁止ゾーンの頂点をクリックで取得するツール。

操作:
  クリック    → 頂点を追加
  Enter       → 現在のゾーンを確定して次のゾーンへ
  Backspace   → 直前の頂点を取り消し
  q / 閉じる  → 終了して NO_PARKING_ZONES の定義を出力

実行:
  uv run --no-project scripts/pick_zone.py
  uv run --no-project scripts/pick_zone.py --image path/to/image.jpg
"""

import os
import sys
import argparse
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_DIR = os.path.join(
    PROJECT_ROOT, "data",
    "Aid-80070001-0000-2000-9002-000000000cc9",
    "20260616013730349", "images"
)

# ===== 状態 =====
zones: list[dict] = []          # 確定済みゾーン
current_pts: list[tuple] = []   # 編集中の頂点
zone_index = 1                  # 次のゾーン番号

IMG_W = IMG_H = 1               # 実際の画像サイズ（後で設定）

COLORS = ["cyan", "yellow", "magenta", "orange", "lime"]


def to_320(px, py):
    """画像ピクセル座標 → 0-320 スケールに変換。"""
    return round(px * 320 / IMG_W), round(py * 320 / IMG_H)


def redraw(ax, img):
    ax.cla()
    ax.imshow(img)
    ax.set_title(
        f"Zone {zone_index} を定義中  [{len(current_pts)}頂点]\n"
        "クリック: 頂点追加  Enter: ゾーン確定  Backspace: 戻す  q: 終了",
        fontsize=9
    )
    ax.axis("off")

    # グリッド（64刻み ≒ 0,64,128,192,256,320）
    for v in [64, 128, 192, 256]:
        ax.axvline(v * IMG_W / 320, color="white", alpha=0.2, linewidth=0.5)
        ax.axhline(v * IMG_H / 320, color="white", alpha=0.2, linewidth=0.5)
        ax.text(v * IMG_W / 320, 4, str(v), color="white", fontsize=6, alpha=0.5)
        ax.text(2, v * IMG_H / 320, str(v), color="white", fontsize=6, alpha=0.5)

    # 確定済みゾーン
    for i, z in enumerate(zones):
        pts_px = [(x * IMG_W / 320, y * IMG_H / 320) for x, y in z["polygon"]]
        color = COLORS[i % len(COLORS)]
        poly = patches.Polygon(pts_px, closed=True,
                               edgecolor=color, facecolor=color, alpha=0.2, linewidth=2)
        ax.add_patch(poly)
        ax.text(pts_px[0][0], pts_px[0][1] - 8, z["name"],
                color=color, fontsize=9, weight="bold")

    # 編集中のゾーン
    color = COLORS[len(zones) % len(COLORS)]
    if current_pts:
        xs = [p[0] * IMG_W / 320 for p in current_pts]
        ys = [p[1] * IMG_H / 320 for p in current_pts]
        ax.plot(xs + [xs[0]], ys + [ys[0]], color=color, linewidth=1.5, linestyle="--")
        ax.scatter(xs, ys, color=color, s=40, zorder=5)
        for j, (x, y) in enumerate(current_pts):
            ax.text(x * IMG_W / 320 + 4, y * IMG_H / 320 - 4,
                    f"({x},{y})", color=color, fontsize=7)

    plt.draw()


def print_result():
    all_zones = zones[:]
    if current_pts and len(current_pts) >= 3:
        all_zones.append({"name": f"zone_{zone_index}", "polygon": current_pts[:]})

    print("\n" + "=" * 60)
    print("bike_parking.py の NO_PARKING_ZONES にコピペしてください")
    print("=" * 60)
    print("NO_PARKING_ZONES: list[dict] = [")
    for z in all_zones:
        pts_str = ", ".join(f"({x}, {y})" for x, y in z["polygon"])
        print(f'    {{"name": "{z["name"]}", "polygon": [{pts_str}]}},')
    print("]")
    print("=" * 60)


def main():
    global IMG_W, IMG_H, zone_index, current_pts

    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=None, help="使用する画像のパス")
    args = parser.parse_args()

    if args.image:
        img_path = args.image
    else:
        files = sorted(f for f in os.listdir(IMAGE_DIR) if f.endswith(".jpg"))
        if not files:
            print(f"ERROR: 画像が見つかりません: {IMAGE_DIR}")
            sys.exit(1)
        img_path = os.path.join(IMAGE_DIR, files[len(files) // 2])  # 中間フレーム

    print(f"使用画像: {img_path}")
    img = Image.open(img_path)
    IMG_W, IMG_H = img.size

    fig, ax = plt.subplots(figsize=(7, 7))
    plt.subplots_adjust(top=0.88)
    redraw(ax, img)

    def on_click(event):
        if event.inaxes != ax or event.button != 1:
            return
        x320, y320 = to_320(event.xdata, event.ydata)
        current_pts.append((x320, y320))
        redraw(ax, img)

    def on_key(event):
        global zone_index, current_pts

        if event.key == "enter":
            if len(current_pts) < 3:
                print(f"  ※ 頂点が{len(current_pts)}個しかありません（3個以上必要）")
                return
            name = f"zone_{zone_index}"
            zones.append({"name": name, "polygon": current_pts[:]})
            print(f"  ✓ {name} 確定: {current_pts}")
            zone_index += 1
            current_pts = []
            redraw(ax, img)

        elif event.key == "backspace":
            if current_pts:
                removed = current_pts.pop()
                print(f"  ← 取り消し: {removed}")
                redraw(ax, img)

        elif event.key == "q":
            print_result()
            plt.close()

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    fig.canvas.mpl_connect("close_event", lambda e: print_result())

    plt.show()


if __name__ == "__main__":
    main()
