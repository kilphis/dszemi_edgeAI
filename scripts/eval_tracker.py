# /// script
# dependencies = ["pandas"]
# ///
"""
追跡ロジックの性能比較スクリプト

同じデータに対して strategy / dead_after の組み合わせを全部走らせ、
結果を表で比較する。

実行:
  uv run --no-project scripts/eval_tracker.py
  uv run --no-project scripts/eval_tracker.py --threshold 30
"""

import os, sys, json, argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import pandas as pd
from tracker import run_tracking, DEAD_AFTER_FRAMES

DATA_DIR = os.path.join(
    PROJECT_ROOT, "data",
    "Aid-80070001-0000-2000-9002-000000000cc9",
    "20260616013730349",
    "inferences", "deserialized_inferences",
)


def load_frames():
    files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".json"))
    frames = [json.load(open(os.path.join(DATA_DIR, f))) for f in files]
    frames.sort(key=lambda x: pd.to_datetime(x["T"]))
    return frames


def evaluate(frames, strategy, dead_after, threshold_sec):
    tracks, snapshots, events = run_tracking(
        frames,
        strategy=strategy,
        dead_after=dead_after,
        threshold_sec=threshold_sec,
    )

    total          = len(tracks)
    alive_at_end   = sum(1 for t in tracks if t.alive)
    dead           = total - alive_at_end
    short_lived    = sum(1 for t in tracks if t.stay_sec < 5)   # 5秒未満 = 誤検出の疑い
    abandoned_evts = sum(1 for e in events if e["type"] == "ABANDONED")
    avg_stay       = (sum(t.stay_sec for t in tracks) / total) if total else 0

    return {
        "strategy":      strategy,
        "dead_after":    dead_after,
        "total_tracks":  total,
        "alive_at_end":  alive_at_end,
        "dead(消滅)":    dead,
        "short(<5s)":    short_lived,
        "abandoned":     abandoned_evts,
        "avg_stay_sec":  round(avg_stay, 1),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=60,
                        help="放置判定の秒数（デフォルト60秒）")
    args = parser.parse_args()

    print(f"データ読み込み中: {DATA_DIR}")
    frames = load_frames()
    print(f"フレーム数: {len(frames)}  放置閾値: {args.threshold}秒\n")

    # ── 比較する設定の組み合わせ ──────────────────────────────
    configs = [
        ("naive",  0),                  # 現在の実装（消滅なし）
        ("naive",  DEAD_AFTER_FRAMES),  # 現在の実装 + 消滅あり
        ("greedy", 0),                  # 改良マッチング（消滅なし）
        ("greedy", DEAD_AFTER_FRAMES),  # 改良マッチング + 消滅あり ← 推奨
    ]

    rows = []
    for strategy, dead_after in configs:
        rows.append(evaluate(frames, strategy, dead_after, args.threshold))

    # ── 表示 ─────────────────────────────────────────────────
    headers = list(rows[0].keys())
    col_w   = [max(len(h), max(len(str(r[h])) for r in rows)) + 2 for h in headers]

    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_w))
    sep_line    = "  ".join("-" * w for w in col_w)
    print(header_line)
    print(sep_line)
    for row in rows:
        print("  ".join(str(row[h]).ljust(w) for h, w in zip(headers, col_w)))

    print()
    print("【読み方】")
    print("  total_tracks : 全フレームで新規登録されたトラック数（多すぎると誤マッチ疑い）")
    print("  short(<5s)   : 5秒未満で消えたトラック数（少ないほど良い）")
    print("  dead(消滅)   : dead_after フレームで消滅したトラック数")
    print("  abandoned    : 放置アラートの発火回数")
    print("  avg_stay_sec : 全トラックの平均滞在時間（秒）")
    print()
    print("★ 推奨: strategy=greedy / dead_after=5 の行を基準にする")


if __name__ == "__main__":
    main()
