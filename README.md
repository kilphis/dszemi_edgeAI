# EdgeAI 駐輪場監視システム

Sony AITRIOS エッジAIカメラを使った自転車の放置・違法駐輪検出システム。熊本市の駐輪場への設置を想定したDSゼミプロジェクト。

## プロジェクト概要

AITRIOS カメラが出力する物体検出推論データ（FlatBuffers → JSON）を解析し、以下の2つの異常を検出する。

- **違法駐輪（ILLEGAL_PARK）**: 自転車が禁止ゾーンと重なっている
- **放置（ABANDONED）**: 自転車が閾値時間（デフォルト60分）以上同じ場所に留まっている

## ディレクトリ構成

```
SmartCamera/                   Sony提供のFlatBuffers推論デシリアライズライブラリ
background/                    駐輪場の参照写真（3枚 JPG）
data/handson_0602/
  images/                      ハンズオン用撮影画像（30枚 JPG、カラス検出データ）
  inferences/
    deserialized_inferences/   推論JSONファイル
    serialized_inferences/     FlatBuffers形式の生データ
notebooks/
  ds1ai_app.ipynb              Sony AITRIOSハンズオン用 Colab ノートブック（オリジナル）
  ds1ai_api2gdrive.ipynb       Google Drive連携ノートブック
presen/                        スライド・発表資料
sample_train/                  自転車検出モデルの学習用サンプル画像（24枚）
scripts/
  ds1ai_app.py                 ハンズオンノートブックをローカル実行用に移植
  bike_parking.py              本命：駐輪場監視パイプライン（自転車追跡・違法駐輪検出）
提出課題など/                  授業提出物・ノート
_mermaid/dif.md                システム全体のMermaid図（データフロー・クラス図）
_todo.md                       TODOリスト
```

git 管理外（`.gitignore` で除外）:

| パス | 内容 |
|------|------|
| `config/` | AITRIOS認証情報（clientID, secretID, token等） |
| `.env` | APIキー |
| `output/` | スクリプト生成画像 |
| `*.png` | 画像ファイル全般 |

## セットアップ＆実行

Python 環境は `uv` を使用する。依存パッケージは各スクリプト内のインポートから自動解決される。

```bash
# ハンズオンデータ（カラス検出）で動作確認
uv run --no-project scripts/ds1ai_app.py

# 駐輪場監視パイプライン（本命）
uv run --no-project scripts/bike_parking.py
```

出力画像は `output/` に保存される（git 管理外）。

### AITRIOS 認証情報の準備

`config/` ディレクトリは git 管理外のため、自分で用意する必要がある。AITRIOS ポータルから取得した認証情報を以下のように配置する。

```
config/
  client_id
  client_secret
  token_url
  （その他 AITRIOS が要求するファイル）
```

## 設定変更のポイント（STUB）

自転車の実データが届いたら `scripts/bike_parking.py` の以下の箇所を変更する。

| 変数 | 現在の値（仮） | 変更内容 |
|------|--------------|---------|
| `DATA_DIR` | `data/handson_0602/.../deserialized_inferences` | 自転車推論JSONのディレクトリに変更 |
| `class_map` | `{0: "bicycle", 1: "obstacle"}` | モデルのクラスIDに合わせて修正 |
| `NO_PARKING_ZONES` | 仮の左端・右端エリア（0〜320スケール） | `background/` の参照写真をもとに実座標を設定 |
| `STAY_TIME_THRESHOLD_MINUTES` | `60`（分） | 運用要件に合わせて調整 |

### 推論JSONのフォーマット

```json
{
  "T": "2026-06-02T02:27:45.222Z",
  "0": {"C": 0, "P": 0.85, "X": 50, "Y": 30, "x": 120, "y": 200}
}
```

座標（`X`, `Y`, `x`, `y`）は 0〜320 のスケール。`C` はクラスID、`P` は確信度。
