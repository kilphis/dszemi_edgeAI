# スライド用画像一覧

`slide_assets/` フォルダに選定した画像のまとめ。
ファイル名の先頭 `s02_` = スライド2用、`s06_` = スライド6用。

---

## スライド2：社会課題・提案

### 冒頭で見せる「現場写真」（インパクト重視で2〜3枚使う）

| ファイル名 | 内容 | 推奨度 |
|---|---|---|
| `s02_problem_bikes_our_photo.jpg` | **自分たちで撮影**した現場写真：自転車が横倒しで乱雑に積み上がっている | ★★★ 冒頭で使うと「自分ごと感」が出る |
| `s02_problem_bikes_overflow_nishikumamoto.jpg` | 通路にあふれる大量の自転車（西熊本駅）| ★★★ 一番インパクト大 |
| `s02_problem_bikes_chaotic_heiseieki.jpg` | 乱雑に放置された状況（平成駅前）| ★★★ 混乱が伝わる |
| `s02_problem_bikes_fence_ginzabashi.jpg` | フェンス際まで自転車が溢れている（銀座橋際）| ★★ |
| `s02_problem_bikes_aisle_tomiaieki.jpg` | 通路・禁止エリアへの駐輪（富合駅）| ★★ 禁止区域侵入の例として良い |

### 「予算の80%が人件費」を説明するグラフ

| ファイル名 | 内容 | 推奨度 |
|---|---|---|
| `s02_budget_expenditure_pie.jpg` | 支出内訳：放置自転車対策費のうち79%が「整理指導」（人件費）| ★★★ 最重要・必ず使う |
| `s02_budget_income_pie.jpg` | 収入内訳：参考用 | ★ |

### 補足データ

| ファイル名 | 内容 | 推奨度 |
|---|---|---|
| `s02_satisfaction_survey.jpg` | 駐輪環境の満足度：45%が不満（熊本市アンケート）| ★★ 市民の不満を裏付ける |
| `s02_parking_lots_decrease_map.jpg` | まちなか駐輪場が11箇所→5箇所に減少した地図 | ★★ 悪循環の証拠 |

---

## スライド3：使用素材・要件定義

| ファイル名 | 内容 |
|---|---|
| `s03_camera_actual_view.jpg` | 実際のAITRIOSカメラの映像（今回使った駐輪場） |

---

## スライド6：アプリ開発

| ファイル名 | 内容 |
|---|---|
| `s06_heatmap_result.png` | 自転車の滞留ヒートマップ（オレンジ破線 = 禁止ゾーン）|
| `s06_heatmap_explanation.png` | ヒートマップの仕組み説明図（5フレーム→累積→ヒートマップ）|
| `s06_bbox_overlay_frame.png` | 実フレームへのバウンディングボックス重畳（緑=OK, 水色=ゾーン）|

---

## 使用を推奨するセット（最小構成）

1. 社会課題の冒頭: `s02_problem_bikes_our_photo.jpg`（自撮り）+ `s02_problem_bikes_overflow_nishikumamoto.jpg` または `s02_problem_bikes_chaotic_heiseieki.jpg`
2. 予算の話: `s02_budget_expenditure_pie.jpg`（放置自転車整理指導79%の円グラフ）
3. 満足度補足: `s02_satisfaction_survey.jpg`
4. 要件定義: `s03_camera_actual_view.jpg`
5. アプリ成果: `s06_heatmap_result.png` + `s06_heatmap_explanation.png`
