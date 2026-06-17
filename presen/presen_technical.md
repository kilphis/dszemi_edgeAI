# 技術者向け補足スライド — エッジAI放置自転車検出システム

> 一般向け発表の後に追加するAppendix想定。
> GitHubリポジトリ: https://github.com/kilphis/dszemi_edgeAI

---

## Tech-1: システム全体のデータフロー

```
[Sony AITRIOSカメラ]
    │ エッジ推論（カメラ内部で処理）
    ▼
[AITRIOS Console REST API v2]
    │ GET /images          → JPEG画像
    │ GET /inferences      → Base64エンコードされたFlatBuffers
    ▼
[download_inferences.py]
    │ FlatBuffers → JSON にデシリアライズ
    │ 認証トークンをキャッシュ（3500秒でリフレッシュ）
    ▼
data/<device_id>/<timestamp>/
    ├── images/                         ← JPEG画像
    └── inferences/deserialized_inferences/  ← 推論JSON
    ▼
[bike_parking.py / demo.py / demo_abandoned.py]
    ▼
output/
    ├── bike_heatmap.png
    ├── bike_count.png
    └── bike_frame_NNN.png
```

### 推論JSONの構造

```json
{
  "T": "2026-06-16T01:37:30.349+09:00",
  "1": {"C": 0, "P": 0.609, "X": 7,  "Y": 232, "x": 88,  "y": 310},
  "2": {"C": 0, "P": 0.521, "X": 120, "Y": 180, "x": 200, "y": 260}
}
```

| キー | 意味 |
|---|---|
| `T` | タイムスタンプ（ISO 8601） |
| `C` | クラスID（0 = bicycle） |
| `P` | 確信度（0〜1） |
| `X, Y` | バウンディングボックス 左上 |
| `x, y` | バウンディングボックス 右下 |

**座標系**: 0〜320 の正規化座標。画像解像度によらず同じスケール。

---

## Tech-2: 禁止ゾーン判定の設計判断

### なぜ矩形（IoU）ではなくポリゴン + Point-in-Polygon か

カメラが斜め撮影のため、現実の長方形エリアが画像上では台形になる。
矩形ゾーンでは誤検知が増えるため、任意の多角形で定義できる設計にした。

```
現実（真上から）         カメラ画像（斜めから）
 ┌──────────────┐            ／￣￣￣￣￣＼
 │  禁止エリア  │   →       ／  禁止エリア ＼
 └──────────────┘           ＼_______________／
      長方形                      台形
```

ゾーン定義の変化:

```python
# 矩形（旧）
{"name": "zone", "X": 0, "Y": 240, "x": 320, "y": 320}

# ポリゴン（現在）
{"name": "zone_2", "polygon": [
    (80, 319), (220, 212), (171, 190),
    (181, 186), (228, 204), (253, 194),
    (274, 203), (266, 319)
]}
```

### レイキャスティング法による点判定

自転車の重心 `(cx, cy)` がポリゴン内かどうかを判定する。

**アルゴリズム:** 点から右向きにレイを飛ばし、辺との交差が奇数回なら内側。

```python
def point_in_polygon(px, py, polygon):
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and \
           (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside
```

17行、O(n)、外部ライブラリ不要。n はゾーンの頂点数（今回は最大8頂点）。

### ゾーン座標のキャリブレーション手順

`pick_zone.py` を実行 → 実際のカメラ画像をクリックして頂点を選択 → コードに貼り付け

```bash
uv run --no-project scripts/pick_zone.py
```

---

## Tech-3: 個体追跡の設計と課題

### 座標近傍マッチング（Coordinate Proximity Matching）

AITRIOSの推論出力にはフレーム間の個体IDが存在しない。
そこで「前フレームから30px以内に検出されたら同一個体」とみなすロジックを自作した。

```
フレームN:   cx=120, cy=200  → track_id=0 として登録
フレームN+1: cx=118, cy=203  → 距離 ≈ 2.8px < 30px → track_id=0 の滞在時間を更新
フレームN+2: cx=122, cy=201  → 距離 ≈ 2.2px < 30px → track_id=0 の滞在時間を更新
```

閾値 `COORD_MATCH_RADIUS = 30px`（0〜320スケール）は実データから経験的に設定。

---

### 現在の実装の課題

#### 課題1: 最近傍が保証されない

現在: リストを先頭から走査し、30px以内の**最初の**トラックにマッチ

```
トラックA: cx=100  (距離12px)  ← リストが先頭 → こちらにマッチ（誤り）
トラックB: cx=108  (距離 4px)  ← 本来こちらが正解
```

改善案: **ハンガリアン法** で全検出×全トラックの距離行列を最小コストで割り当て

#### 課題2: 消えたトラックが残り続ける

現在: 一度登録されたトラックは永続する

```
09:00  自転車Aが来る   → track_id=0 登録
09:30  自転車Aが去る   → track_id=0 はリストに残ったまま
10:00  自転車Bが来る   → track_id=0 近くなら「A継続」と誤認識（本当はBが新規）
```

改善案: `last_seen` から N フレーム未検出でトラックを **Dead** 状態に遷移

#### 課題3: 密集時の誤マッチ

30px の半径が隣接自転車と重なると、どちらのトラックにマッチするか不定になる。

改善案: IoUベースのマッチング、またはBBサイズに応じた動的半径

---

### 課題の整理

| # | 課題 | 現在の影響 | 改善の方向 |
|---|---|---|---|
| 1 | 最近傍が保証されない | 誤トラック割り当て | ハンガリアン法 |
| 2 | トラックが消えない | 別個体を同一と誤認識 | N フレーム未検出で消滅 |
| 3 | 密集時の誤マッチ | 滞在時間の誤算 | IoUベースのマッチング |

今回のデータ（50フレーム、駐輪密度は中程度）では課題1・2が影響しやすく、**滞在時間の計算精度に直結**するため優先度が高い。

---

## Tech-4: 拡張性・再利用性

### 場所の変更 → 座標だけ更新すれば再利用できる

```python
# bike_parking.py の設定部分を変えるだけ
NO_PARKING_ZONES = [
    {"name": "zone_A", "polygon": [(x1,y1), (x2,y2), ...]},
    {"name": "zone_B", "polygon": [(x1,y1), (x2,y2), ...]},
]
```

モデルの再学習・デプロイは不要。`pick_zone.py` で新しい座標を取得して貼り替えるだけ。

### 閾値の調整

```python
STAY_TIME_THRESHOLD_MINUTES = 60   # 放置判定の閾値（分）
COORD_MATCH_RADIUS = 30            # 同一個体と判定する距離（px, 0〜320スケール）
```

これらは設定値として分離されており、場所・用途に応じて変更しやすい。

### 複数カメラへの拡張（将来）

現在: 1台のカメラ = 1つの `device_id` ディレクトリ

拡張案:
```
data/
  <device_id_A>/   ← カメラA（入口付近）
  <device_id_B>/   ← カメラB（奥のエリア）
```

`download_inferences.py` にデバイスIDのリストを渡すだけで、複数カメラの推論データを並列取得できる設計にしてある。

### GitHub

コード全体: https://github.com/kilphis/dszemi_edgeAI

```
scripts/
  download_inferences.py   # AITRIOS API からデータ取得
  bike_parking.py          # メインパイプライン・ヒートマップ生成
  demo.py                  # 違法駐輪リアルタイムデモ
  demo_abandoned.py        # 放置自転車タイマーデモ
  pick_zone.py             # ゾーン座標インタラクティブ選択ツール
```
