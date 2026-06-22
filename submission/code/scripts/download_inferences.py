# /// script
# dependencies = ["requests", "pyyaml", "flatbuffers"]
# ///
"""
AITRIOS Console REST API から画像と推論結果をダウンロードして
data/<device_id>/<timestamp>/ に保存するスクリプト。

ds1ai_api2gdrive.ipynb の Google Drive 依存を除去したローカル版。

事前準備:
  config/clientID.txt  — クライアントアプリID
  config/secretID.txt  — クライアントシークレット
  config/deviceID.txt  — デバイスID (Aid-XXXXXXXX-...)

実行:
  uv run --no-project scripts/download_inferences.py
  uv run --no-project scripts/download_inferences.py --dir -1   # -1=最新, 0=最古
"""

import os
import sys
import base64
import json
import datetime
import argparse
import requests
import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR   = os.path.join(PROJECT_ROOT, "config")
DATA_DIR     = os.path.join(PROJECT_ROOT, "data")
SMART_CAMERA = os.path.join(PROJECT_ROOT, "SmartCamera")

sys.path.insert(0, PROJECT_ROOT)

PORTAL_ENDPOINT  = "https://auth.aitrios.sony-semicon.com/oauth2/default/v1/token"
CONSOLE_ENDPOINT = "https://console.aitrios.sony-semicon.com/api/v2"
TOKEN_FILE       = os.path.join(CONFIG_DIR, "token_info.yaml")

# ===== 認証情報の読み込み =====

def _read(filename: str) -> str:
    path = os.path.join(CONFIG_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return f.read().strip()

def get_credentials():
    try:
        return _read("clientID.txt"), _read("secretID.txt"), _read("deviceID.txt")
    except FileNotFoundError as e:
        print(f"ERROR: config/ に認証ファイルが見つかりません: {e}")
        sys.exit(1)

# ===== トークン管理 =====

def _fetch_token(client_id: str, client_secret: str) -> str:
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "accept": "application/json",
        "authorization": f"Basic {auth}",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
    }
    resp = requests.post(PORTAL_ENDPOINT, headers=headers, data="grant_type=client_credentials&scope=system")
    resp.raise_for_status()
    token = resp.json()["access_token"]
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        yaml.dump({"datetime": datetime.datetime.now(), "token": token}, f)
    print("トークン取得・保存完了")
    return token

def get_token(client_id: str, client_secret: str) -> str:
    if os.path.isfile(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8") as f:
            info = yaml.safe_load(f)
        age = (datetime.datetime.now() - info["datetime"]).total_seconds()
        if age < 3500:
            print(f"既存トークンを使用（残り約{int((3600-age)/60)}分）")
            return info["token"]
    return _fetch_token(client_id, client_secret)

# ===== 画像＆推論のダウンロード =====

def download(console_endpoint: str, token: str, device_id: str, dir_index: int):
    headers = {"Authorization": f"Bearer {token}"}

    # 画像ディレクトリ一覧
    resp = requests.get(
        f"{console_endpoint}/images/devices/directories?device_id={device_id}",
        headers=headers,
    )
    resp.raise_for_status()
    dir_list = resp.json()[0]["devices"][0]["Image"]
    sub_dir  = dir_list[dir_index]
    print(f"対象ディレクトリ: {sub_dir}  (全{len(dir_list)}件中 index={dir_index})")

    base_path = os.path.join(DATA_DIR, device_id, sub_dir)
    img_path  = os.path.join(base_path, "images")
    ser_path  = os.path.join(base_path, "inferences", "serialized_inferences")
    os.makedirs(img_path, exist_ok=True)
    os.makedirs(ser_path, exist_ok=True)

    # 画像取得
    resp = requests.get(
        f"{console_endpoint}/images/devices/{device_id}/directories/{sub_dir}",
        headers=headers,
    )
    resp.raise_for_status()
    images = resp.json()["data"]
    print(f"画像数: {len(images)}")
    for img in images:
        dest = os.path.join(img_path, img["name"])
        if os.path.exists(dest):
            print(f"  skip (already exists): {img['name']}")
            continue
        content = requests.get(img["sas_url"]).content
        with open(dest, "wb") as f:
            f.write(content)
        print(f"  saved: {img['name']}")

    # 推論取得
    resp = requests.get(
        f"{console_endpoint}/inferenceresults?devices={device_id}&limit={len(images)}&scope=full",
        headers=headers,
    )
    resp.raise_for_status()
    inferences = resp.json()["inferences"]
    print(f"推論数: {len(inferences)}")
    for item in inferences:
        for inf in item["inferences"]:
            ts  = inf["T"].strip().replace(" ", "")
            dt  = datetime.datetime.strptime(ts[:26], "%Y-%m-%dT%H:%M:%S.%f") if "." in ts else datetime.datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
            fname = dt.strftime("%Y%m%d%H%M%S%f")[:17] + ".json"
            dest  = os.path.join(ser_path, fname)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(inf, f, ensure_ascii=False, indent=4)
    print(f"シリアライズ済み推論を保存: {ser_path}")

    return base_path, ser_path

# ===== デシリアライズ =====

def deserialize(base_path: str, ser_path: str):
    from SmartCamera import ObjectDetectionTop, BoundingBox, BoundingBox2d

    out_path = os.path.join(base_path, "inferences", "deserialized_inferences")
    os.makedirs(out_path, exist_ok=True)

    files = [f for f in os.listdir(ser_path) if f.endswith(".json")]
    print(f"デシリアライズ: {len(files)} ファイル")
    for fname in files:
        with open(os.path.join(ser_path, fname), encoding="utf-8") as f:
            buf = json.load(f)

        if "O" not in buf:
            print(f"  skip (no 'O' field): {fname}")
            continue

        raw  = base64.b64decode(buf["O"])
        top  = ObjectDetectionTop.ObjectDetectionTop.GetRootAsObjectDetectionTop(raw, 0)
        perc = top.Perception()
        buf.pop("O")

        for i in range(perc.ObjectDetectionListLength()):
            obj = perc.ObjectDetectionList(i)
            if obj.BoundingBoxType() == BoundingBox.BoundingBox.BoundingBox2d:
                bb = BoundingBox2d.BoundingBox2d()
                bb.Init(obj.BoundingBox().Bytes, obj.BoundingBox().Pos)
                buf[str(i + 1)] = {
                    "C": obj.ClassId(),
                    "P": obj.Score(),
                    "X": bb.Left(),
                    "Y": bb.Top(),
                    "x": bb.Right(),
                    "y": bb.Bottom(),
                }

        with open(os.path.join(out_path, fname), "w", encoding="utf-8") as f:
            json.dump(buf, f, ensure_ascii=False, indent=4)

    print(f"デシリアライズ完了: {out_path}")
    return out_path

# ===== メイン =====

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AITRIOS から推論データをダウンロード")
    parser.add_argument("--dir", type=int, default=-1, help="ディレクトリ番号 (-1=最新, 0=最古)")
    args = parser.parse_args()

    client_id, client_secret, device_id = get_credentials()
    print(f"デバイスID: {device_id}")

    token = get_token(client_id, client_secret)
    base_path, ser_path = download(CONSOLE_ENDPOINT, token, device_id, args.dir)
    out_path = deserialize(base_path, ser_path)

    print()
    print("===== 完了 =====")
    print(f"画像:              {base_path}/images/")
    print(f"デシリアライズ済み: {out_path}/")
    print()
    print("bike_parking.py の DATA_DIR をこのパスに変更してください:")
    print(f'  DATA_DIR  = "{out_path}"')
    print(f'  IMAGE_DIR = "{base_path}/images"')
