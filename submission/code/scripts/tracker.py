"""
tracker.py — 自転車追跡ロジックの唯一の実装

bike_parking.py / demo_abandoned.py から import して使う。
直接実行不可（eval_tracker.py で比較テストができる）。

改良の窓口:
  strategy="naive"  → 現在の実装（リスト先頭から走査）
  strategy="greedy" → 改良版（全ペア距離を計算し近い順に割り当て）
  dead_after=N      → N フレーム未検出でトラック消滅（0=消滅なし）
"""

from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd


# ────────────────────────────────────────────────
# パラメータ（変更するときはここだけ触る）
# ────────────────────────────────────────────────
COORD_MATCH_RADIUS = 30   # 同一個体と判定する距離（px, 0-320スケール）
DEAD_AFTER_FRAMES  = 5    # この連続フレーム数だけ未検出ならトラック消滅（0=消滅なし）


# ────────────────────────────────────────────────
# データ構造
# ────────────────────────────────────────────────
@dataclass
class Track:
    track_id:       int
    first_seen:     datetime
    last_seen:      datetime
    last_cx:        float
    last_cy:        float
    frames_missing: int   = 0      # 連続未検出フレーム数
    stay_sec:       float = 0.0
    alive:          bool  = True   # False になったトラックはマッチング対象外
    alert_sent:     bool  = False  # ABANDONED イベントを発火済みか
    illegal:        bool  = False  # ILLEGAL_PARK イベントを発火済みか


# ────────────────────────────────────────────────
# マッチング戦略
# ────────────────────────────────────────────────
def _match_naive(dets, live_tracks):
    """
    【現在の実装・課題あり】
    各検出をリストの先頭から走査し、COORD_MATCH_RADIUS 以内の
    「最初の」トラックに割り当てる。
    → 距離が近い方が後にあっても無視される。
    """
    used = set()
    result = []
    for det in dets:
        matched = None
        for t in live_tracks:
            if t.track_id in used:
                continue
            dist = ((det["cx"] - t.last_cx) ** 2 + (det["cy"] - t.last_cy) ** 2) ** 0.5
            if dist <= COORD_MATCH_RADIUS:
                matched = t
                break
        if matched:
            used.add(matched.track_id)
        result.append((det, matched))
    return result


def _match_greedy(dets, live_tracks):
    """
    【改良版】
    全検出 × 全トラックの距離を計算し、近い順にグリーディー割り当て。
    リスト順バイアスが消え、常に「最も近いペア」が優先される。
    計算量: O(n*m * log(n*m))。n,m が 10 以下なら実質無視できる。
    """
    if not dets or not live_tracks:
        return [(d, None) for d in dets]

    pairs = []
    for di, det in enumerate(dets):
        for ti, trk in enumerate(live_tracks):
            dist = ((det["cx"] - trk.last_cx) ** 2 + (det["cy"] - trk.last_cy) ** 2) ** 0.5
            if dist <= COORD_MATCH_RADIUS:
                pairs.append((dist, di, ti))
    pairs.sort()

    used_dets, used_trks = set(), set()
    assignments = {}
    for _, di, ti in pairs:
        if di not in used_dets and ti not in used_trks:
            assignments[di] = ti
            used_dets.add(di)
            used_trks.add(ti)

    return [
        (dets[di], live_tracks[assignments[di]] if di in assignments else None)
        for di in range(len(dets))
    ]


_MATCHERS = {
    "naive":  _match_naive,
    "greedy": _match_greedy,
}


# ────────────────────────────────────────────────
# メイン関数
# ────────────────────────────────────────────────
def run_tracking(
    frames,
    *,
    bicycle_class_id: int = 0,
    strategy: str = "naive",
    dead_after: int = DEAD_AFTER_FRAMES,
    threshold_sec: float | None = None,
    is_illegal_fn=None,
):
    """
    全フレームを順番に処理して追跡結果を返す。

    Parameters
    ----------
    frames           : list[dict]      推論JSON（T + 検出辞書）
    bicycle_class_id : int             自転車のクラスID
    strategy         : "naive"|"greedy"  マッチング戦略
    dead_after       : int             N フレーム連続未検出でトラック消滅（0=消滅なし）
    threshold_sec    : float|None      放置判定秒数
    is_illegal_fn    : (cx,cy)->bool|None  禁止ゾーン判定関数

    Returns
    -------
    tracks    : list[Track]
        全トラック（dead 含む）。alive=False のものはマッチング中に消滅したもの。
    snapshots : list[list[tuple]]
        フレームごとのスナップショット。demo_abandoned.py のアニメーション用。
        各 tuple: (track_id, stay_sec, abandoned, x1, y1, x2, y2)
    events    : list[dict]
        ILLEGAL_PARK / ABANDONED イベントのリスト。bike_parking.py の報告用。
    """
    matcher = _MATCHERS.get(strategy)
    if matcher is None:
        raise ValueError(f"strategy は {list(_MATCHERS)} のどれかにしてください: {strategy!r}")

    tracks: list[Track] = []
    events: list[dict]  = []
    snapshots: list     = []
    next_id = 0

    for frame in frames:
        ts = pd.to_datetime(frame["T"]).to_pydatetime()

        # 検出データを辞書リストに変換
        dets = []
        for k, v in frame.items():
            if k == "T" or not isinstance(v, dict):
                continue
            if v.get("C") != bicycle_class_id:
                continue
            dets.append({
                "cx": (v["X"] + v["x"]) / 2,
                "cy": (v["Y"] + v["y"]) / 2,
                "x1": v["X"], "y1": v["Y"],
                "x2": v["x"], "y2": v["y"],
            })

        # 生存トラックだけをマッチング対象にする
        live = [t for t in tracks if t.alive]

        pairs = matcher(dets, live)
        matched_ids = set()
        snap = []

        for det, track in pairs:
            if track is None:
                track = Track(
                    track_id=next_id,
                    first_seen=ts, last_seen=ts,
                    last_cx=det["cx"], last_cy=det["cy"],
                )
                tracks.append(track)
                next_id += 1
            else:
                track.last_seen = ts
                track.last_cx   = det["cx"]
                track.last_cy   = det["cy"]
                track.frames_missing = 0

            matched_ids.add(track.track_id)
            track.stay_sec = (track.last_seen - track.first_seen).total_seconds()
            abandoned = threshold_sec is not None and track.stay_sec >= threshold_sec

            if is_illegal_fn and is_illegal_fn(det["cx"], det["cy"]) and not track.illegal:
                track.illegal = True
                events.append({
                    "type": "ILLEGAL_PARK",
                    "track_id": track.track_id,
                    "timestamp": ts,
                    "cx": det["cx"], "cy": det["cy"],
                })

            if abandoned and not track.alert_sent:
                track.alert_sent = True
                events.append({
                    "type": "ABANDONED",
                    "track_id": track.track_id,
                    "timestamp": ts,
                    "stay_sec": track.stay_sec,
                    "cx": det["cx"], "cy": det["cy"],
                })

            snap.append((
                track.track_id, track.stay_sec, abandoned,
                det["x1"], det["y1"], det["x2"], det["y2"],
            ))

        # 未マッチのトラック: 連続未検出カウントを増やし、閾値超えで消滅
        if dead_after > 0:
            for t in live:
                if t.track_id not in matched_ids:
                    t.frames_missing += 1
                    if t.frames_missing >= dead_after:
                        t.alive = False

        snapshots.append(snap)

    return tracks, snapshots, events
