"""Automatic observation rules. No database writes or ML dependencies here."""
import re

MIN_DETECTION = 0.50
MIN_OCR = 0.80
STABLE_READINGS = 3
STABLE_SECONDS = 2.0
CLEAR_READINGS = 3
CLEAR_SECONDS = 3.0


def classify(detections):
    if not detections:
        return "empty", None
    readable = set()
    for det in detections:
        ocr = det.get("ocr") or {}
        plate = ocr.get("normalized_text") or ""
        if (det.get("confidence", 0) >= MIN_DETECTION and ocr.get("confidence", 0) >= MIN_OCR
                and re.fullmatch(r"[A-Z0-9]{4,15}", plate) and any(c.isdigit() for c in plate)):
            readable.add(plate)
    if not readable:
        return "uncertain", None
    if len(readable) > 1:
        return "multiple", None
    return "readable", next(iter(readable))


def observe(gate, detections, timestamp):
    """Return state and optional plate to toggle. Blank means no detected plate at all."""
    kind, plate = classify(detections)
    gate.setdefault("seen", [])
    status = {"status": kind, "plate": plate, "stable_readings": 0}
    if kind == "empty":
        gate["candidate"] = None
        gate["hits"] = 0
        if not gate.get("blank_count"):
            gate["blank_since"] = timestamp
        gate["blank_count"] = gate.get("blank_count", 0) + 1
        if gate["blank_count"] >= CLEAR_READINGS and timestamp - gate["blank_since"] >= CLEAR_SECONDS:
            gate["seen"] = []
        status["status"] = "rearming" if gate["seen"] else "ready"
        return status, None
    gate["blank_count"] = 0
    if kind != "readable":
        gate["candidate"] = None
        gate["hits"] = 0
        return status, None
    if plate in gate["seen"]:
        gate["candidate"] = None
        gate["hits"] = 0
        status["status"] = "already_seen"
        return status, None
    if gate.get("candidate") != plate:
        gate.update(candidate=plate, hits=1, candidate_since=timestamp)
    else:
        gate["hits"] += 1
    status.update(status="stabilizing", stable_readings=gate["hits"])
    if gate["hits"] >= STABLE_READINGS and timestamp - gate["candidate_since"] >= STABLE_SECONDS:
        gate["seen"].append(plate)
        gate["candidate"] = None
        gate["hits"] = 0
        status["status"] = "processed"
        return status, plate
    return status, None
