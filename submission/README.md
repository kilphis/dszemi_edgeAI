# 放置自転車・違法駐輪検出システム - 提出資料

## フォルダ構成

```
submission/
├── slides/                      発表用スライド
│   └── AITRIOS_Urban_Dashboard.pdf
├── demo_videos/                 デモ動画（3本）
│   ├── 駐車検知.mov            違法駐輪検知デモ
│   ├── 放置比較.mov            改善前後の比較デモ
│   └── 放置自転車.mov          放置自転車検出デモ
├── diagrams/                    システム図解（Mermaid 図を PNG化）
│   ├── fig1_data_flow.png       データフロー図
│   ├── fig2_tracker_internal.png トラッキング内部処理
│   └── fig3_track_lifecycle.png トラック生存期間図
├── code/                        実装コード
│   ├── scripts/                 実行スクリプト
│   │   ├── tracker.py           トラッキング統一モジュール
│   │   ├── bike_parking.py      メインパイプライン（ヒートマップ生成）
│   │   ├── demo.py              違法駐輪リアルタイムデモ
│   │   ├── demo_abandoned.py    放置自転車タイマーデモ
│   │   ├── download_inferences.py AITRIOS API データ取得
│   │   ├── pick_zone.py         ポリゴンゾーン選択ツール
│   │   └── eval_tracker.py      トラッキング性能評価
│   └── presen_technical.md      技術解説（参考）
└── README.md                    このファイル
```

## 主要な改善点

### 1. トラッキング精度向上

**naive → greedy 戦略への切り替え**
- 誤マッチ由来の短命トラック：7個 → 4個
- 平均滞在時間の精度：56.8秒 → 67.9秒

### 2. システム構成

- **tracker.py**：追跡ロジックを単一モジュール化
- **複数戦略対応**：naive / greedy / ハンガリアン法（候補）
- **再利用性**：座標変更のみで別施設に展開可能

### 3. デモの透明性

- 1フレーム遅延で違法駐輪アラート表示（因果関係を可視化）
- YouTube 動画フレームをビジュアル素材として活用

## 実行方法

```bash
# 放置自転車検出（greedy 改善版）
uv run scripts/demo_abandoned.py --strategy greedy --fps 2

# 違法駐輪検知
uv run scripts/demo.py --fps 2

# トラッキング性能比較
uv run scripts/eval_tracker.py
```

## 技術サマリー

| 項目 | 内容 |
|---|---|
| カメラ | Sony AITRIOS（エッジコンピューティングカメラ） |
| モデル | YOLOv8 ベース（bike_program） |
| 座標システ | 0-320 正規化座標 |
| 違法駐輪判定 | Ray casting を用いた多角形内判定 |
| 放置判定 | 個体追跡 + 滞在時間カウント |
| 推論レート | 約 1fps |

---

**発表日**：2026年6月22日  
**プロジェクト**：DSゼミ EdgeAI（放置自転車・違法駐輪検出）
