# EdgeAI 駐輪場監視システム

Sony AITRIOS エッジAIカメラを使った自転車の放置・違法駐輪検出システム。  
熊本市の駐輪場への設置を想定した DSゼミプロジェクト（16班）。

## 概要

AITRIOS カメラがエッジ推論した結果（FlatBuffers → JSON）を解析し、2種類の異常を検出する。

| 機能 | 説明 |
|---|---|
| **違法駐輪検出** | 自転車が禁止ゾーン（ポリゴン定義）に入ったらアラート |
| **放置自転車検出** | 同一個体が閾値時間以上同じ場所に留まったらアラート |
| **ヒートマップ** | 自転車の滞留密度を320×320グリッドで可視化 |

## ディレクトリ構成

```
.
├── scripts/
│   ├── tracker.py              ★ 追跡ロジック（モジュール）naive / greedy
│   ├── bike_parking.py         メインパイプライン（ヒートマップ・BB重畳・カウント）
│   ├── demo.py                 違法ゾーン侵入のリアルタイムデモ
│   ├── demo_abandoned.py       放置タイマーバーのリアルタイムデモ
│   ├── eval_tracker.py         追跡アルゴリズム比較（naive vs greedy）
│   ├── download_inferences.py  AITRIOS API からデータ取得・保存
│   ├── pick_zone.py            禁止ゾーン座標をクリックで取得するツール
│   ├── explain_heatmap.py      ヒートマップの仕組み説明図を生成
│   └── ds1ai_app.py            ⚠ レガシー（ハンズオン用ノートブックの移植版）
│
├── notebooks/
│   └── ds1ai_api2gdrive.ipynb  ⚠ レガシー（AITRIOS → Google Drive 連携 Colab ノートブック）
│
├── SmartCamera/                Sony 提供 FlatBuffers デシリアライズライブラリ
├── presen/                     スライド・発表資料
│   ├── appendix/               技術者向け補足資料
│   └── mermaid/                システム図（PNG）
│
├── _mermaid/dif.md             Mermaid 図のソース
├── _todo.md                    TODO リスト
│
│   ── git 管理外 ──────────────────────────────────────────
├── config/                     AITRIOS 認証情報（clientID / secretID / deviceID）
├── data/                       カメラ画像 & 推論 JSON
└── output/                     スクリプト生成画像
```

## 実行方法

Python 環境は `uv` を使用する（`python` 直接実行不可）。

```bash
# データ取得（AITRIOS API）
uv run --no-project scripts/download_inferences.py

# メインパイプライン（ヒートマップ・BB重畳画像を output/ に保存）
uv run --no-project scripts/bike_parking.py

# デモ（インタラクティブ表示）
uv run --no-project scripts/demo.py
uv run --no-project scripts/demo_abandoned.py --threshold 30

# デモ画像を output/ に保存（スライド用）
uv run --no-project scripts/demo_abandoned.py --threshold 30 --strategy greedy --save-frames 6

# 追跡アルゴリズムの比較
uv run --no-project scripts/eval_tracker.py --threshold 30

# 禁止ゾーン座標の取得（実際のカメラ画像をクリック）
uv run --no-project scripts/pick_zone.py
```

## 追跡アルゴリズム

AITRIOS の推論出力はフレームをまたぐ個体 ID を持たないため、座標近傍マッチングで自前実装している。

| strategy | 方式 | 特徴 |
|---|---|---|
| `naive` | リスト先頭から走査 | 旧実装。リスト順に依存した誤マッチが起きる |
| `greedy` | 全ペア距離→近い順に割り当て | 最も近いペアが優先される（推奨） |

`--strategy` オプションで切り替え可能。詳細は `presen/appendix/tracking_algorithms.md` を参照。

## 認証情報のセットアップ

`config/` は git 管理外のため各自で用意する。

```
config/
  clientID.txt    AITRIOS クライアント ID
  secretID.txt    AITRIOS クライアントシークレット
  deviceID.txt    カメラのデバイス ID
```

## 禁止ゾーンの設定

カメラが斜め撮影のため、ゾーンはポリゴン（多角形）で定義する。

```bash
uv run --no-project scripts/pick_zone.py  # 実画像をクリックして頂点を取得
```

取得した座標を `scripts/bike_parking.py` と `scripts/demo.py` の `NO_PARKING_ZONES` に貼り付ける。
