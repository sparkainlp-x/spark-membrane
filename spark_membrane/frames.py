# SPDX-License-Identifier: AGPL-3.0-only
"""Frame bus: the native 32-channel JSONL contract of oes-telemetry-bench.

REFERENCE RE-IMPLEMENTATION of the frame checks in
sparkainlp-x/oes-telemetry-bench @ 48fc4d9b79e58557cc562b8dad0bc90b482d443f (``load_replay``):
exactly the seven fields timestamp / channel_ids / channel_timestamps / channels / regime /
event_label / event_id; 32 unique channel IDs in constant order; every channel timestamp equal
to the frame timestamp; finite JSON numbers only; strictly increasing timestamps with one exact
cadence; contiguous event episodes. No interpolation, resampling, padding or imputation.

512 channels are carried as 16 independent native-32 streams (blocks 0..15) that share the
same timestamps. Global channel index = 32 * block + channel. Nothing is resampled.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .canonical import MembraneError, canonical_json, sha256_bytes, strict_loads

CHANNEL_COUNT = 32
BLOCKS_512 = 16
FRAME_KEYS = {"timestamp", "channel_ids", "channel_timestamps", "channels", "regime", "event_label", "event_id"}
_FRACTION = re.compile(r"\.(\d+)")


@dataclass(frozen=True)
class Frame:
    timestamp: datetime
    timestamp_text: str
    channel_ids: tuple[str, ...]
    channels: tuple[float, ...]
    regime: str
    event_label: str
    event_id: str | None


@dataclass(frozen=True)
class Stream:
    frames: tuple[Frame, ...]
    channel_ids: tuple[str, ...]
    cadence_seconds: float
    sha256: str


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise MembraneError(f"{field} must be an ISO-8601 timestamp with UTC offset")
    frac = _FRACTION.search(value)
    if frac and len(frac.group(1)) > 6:
        raise MembraneError(f"{field} may not exceed microsecond precision")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError as exc:
        raise MembraneError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MembraneError(f"{field} must include an explicit UTC offset or Z")
    return parsed.astimezone(timezone.utc)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise MembraneError(f"{field} must be a non-empty string without outer whitespace")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MembraneError(f"{field} must be a JSON number, not a boolean or null")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise MembraneError(f"{field} must be finite") from exc
    if not math.isfinite(result):
        raise MembraneError(f"{field} must be finite")
    return result


def parse_frame(obj: Any, where: str = "frame") -> Frame:
    if not isinstance(obj, dict):
        raise MembraneError(f"{where}: every JSONL line must be an object")
    missing, unknown = FRAME_KEYS - set(obj), set(obj) - FRAME_KEYS
    if missing:
        raise MembraneError(f"{where}: missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise MembraneError(f"{where}: unknown fields: {', '.join(sorted(unknown))}")
    stamp = _timestamp(obj["timestamp"], f"{where}.timestamp")
    ids = obj["channel_ids"]
    if not isinstance(ids, list) or len(ids) != CHANNEL_COUNT:
        raise MembraneError(f"{where}.channel_ids must contain exactly {CHANNEL_COUNT} channel names")
    channel_ids = tuple(_text(v, f"{where}.channel_ids[{i}]") for i, v in enumerate(ids))
    if len(set(channel_ids)) != CHANNEL_COUNT:
        raise MembraneError(f"{where}.channel_ids must be unique")
    stamps = obj["channel_timestamps"]
    if not isinstance(stamps, list) or len(stamps) != CHANNEL_COUNT:
        raise MembraneError(f"{where}.channel_timestamps must contain exactly {CHANNEL_COUNT} timestamps")
    if any(_timestamp(v, f"{where}.channel_timestamps[{i}]") != stamp for i, v in enumerate(stamps)):
        raise MembraneError(f"{where}: all 32 channel timestamps must exactly equal the frame timestamp")
    values = obj["channels"]
    if not isinstance(values, list) or len(values) != CHANNEL_COUNT:
        raise MembraneError(f"{where}.channels must contain exactly {CHANNEL_COUNT} finite numbers")
    channels = tuple(_number(v, f"{where}.channels[{i}]") for i, v in enumerate(values))
    regime = _text(obj["regime"], f"{where}.regime")
    label = _text(obj["event_label"], f"{where}.event_label")
    if label == "none":
        if obj["event_id"] is not None:
            raise MembraneError(f"{where}.event_id must be null when event_label is 'none'")
        event_id = None
    else:
        event_id = _text(obj["event_id"], f"{where}.event_id")
    return Frame(stamp, obj["timestamp"], channel_ids, channels, regime, label, event_id)


def parse_stream_bytes(raw: bytes, source: str = "stream") -> Stream:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MembraneError(f"{source}: not UTF-8") from exc
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    frames: list[Frame] = []
    for n, line in enumerate(lines, start=1):
        if not line.strip():
            raise MembraneError(f"{source}:{n}: blank lines are not allowed")
        frames.append(parse_frame(strict_loads(line, f"{source}:{n}"), f"{source}:{n}"))
    if len(frames) < 2:
        raise MembraneError(f"{source}: at least two frames are required to establish a cadence")
    ids = frames[0].channel_ids
    for i, f in enumerate(frames):
        if f.channel_ids != ids:
            raise MembraneError(f"{source}: channel identity/order changes at frame {i + 1}")
        if i and f.timestamp <= frames[i - 1].timestamp:
            raise MembraneError(f"{source}: frame timestamps must be strictly increasing")
    steps = [(frames[i].timestamp - frames[i - 1].timestamp).total_seconds() for i in range(1, len(frames))]
    if any(s != steps[0] for s in steps[1:]) or steps[0] <= 0:
        raise MembraneError(f"{source}: timestamps must have one exact, positive sampling interval")
    active: str | None = None
    closed: set[str] = set()
    identity: dict[str, tuple[str, str]] = {}
    for i, f in enumerate(frames, start=1):
        if f.event_id is None:
            if active is not None:
                closed.add(active)
                active = None
            continue
        key = (f.regime, f.event_label)
        if identity.setdefault(f.event_id, key) != key:
            raise MembraneError(f"{source}: event_id {f.event_id!r} changes regime or label at frame {i}")
        if f.event_id != active:
            if f.event_id in closed:
                raise MembraneError(f"{source}: event_id {f.event_id!r} is not one contiguous episode")
            if active is not None:
                closed.add(active)
            active = f.event_id
    return Stream(tuple(frames), ids, steps[0], sha256_bytes(raw))


def load_stream(path: str | Path) -> Stream:
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise MembraneError(f"cannot read {p}: {exc}") from exc
    return parse_stream_bytes(raw, str(p))


def frame_record(timestamp: str, channel_ids: Sequence[str], channels: Sequence[float],
                 regime: str, event_label: str, event_id: str | None) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "channel_ids": list(channel_ids),
        "channel_timestamps": [timestamp] * len(channel_ids),
        "channels": list(channels),
        "regime": regime,
        "event_label": event_label,
        "event_id": event_id,
    }


def dump_stream(records: Sequence[dict[str, Any]]) -> bytes:
    return "".join(canonical_json(r) + "\n" for r in records).encode("utf-8")


def global_index(block: int, channel: int) -> int:
    if not 0 <= block < BLOCKS_512 or not 0 <= channel < CHANNEL_COUNT:
        raise MembraneError("block must be 0..15 and channel 0..31")
    return CHANNEL_COUNT * block + channel


__all__ = ["CHANNEL_COUNT", "BLOCKS_512", "Frame", "Stream", "parse_frame", "parse_stream_bytes",
           "load_stream", "frame_record", "dump_stream", "global_index"]
