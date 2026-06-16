# edgeAI TODO

## 今すぐやること

- [ ] GitHub に private リポジトリ `dszemi_edgeai` を作成
- [ ] `git remote add` して初回 push
- [ ] チームメンバーを Collaborators に招待

## 推論データが揃ったらやること

- [ ] 自転車推論 JSON を `data/bike_XXXX/inferences/deserialized_inferences/` に配置
- [ ] `bike_parking.py` の `DATA_DIR` をそのパスに変更
- [ ] `class_map` をモデルのクラス番号に合わせる（AITRIOS でのクラス0/1確認）
- [ ] `STAY_TIME_THRESHOLD_MINUTES` を要件に合わせて調整（現在: 60分）
- [ ] `uv run --no-project scripts/bike_parking.py` で動作確認

## NO_PARKING_ZONES（後回し・AI で対応予定）

- [ ] `presen/background.jpg` をもとにカメラ映像との対応を確認
- [ ] AI（Claude）に座標を推定させて `bike_parking.py` に反映
- [ ] カメラ取り付け角度が決まったら再調整

## 授業内でやること

- [ ] 背景画像・オブジェクト画像のシナリオ確定
- [ ] スライド印刷

## スライド（残り）

- [ ] モデル開発
- [ ] アプリ開発
- [ ] システムの評価結果
