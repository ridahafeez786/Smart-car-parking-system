# Smart Parking backend

Run from the project root with the existing environment:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000/ for the automatic dashboard. See the root README for installation and camera-demo steps. Keep `best.pt` in the project root. Inference uses CPU; the first OCR request initializes RapidOCR and its local ONNX models.

## Automatic endpoint

`POST /parking/scan?event_id=<UUID>&source=upload` accepts an image in multipart field `file`. Camera calls use `source=camera&station_id=<persistent UUID>` as well. The backend performs detection and OCR itself, then returns detections and an `event` object. It never trusts caller-supplied plate text in this endpoint.

- Upload: exactly one distinct sufficiently confident, valid plate immediately toggles its active session, even when other detections are unreadable. Duplicate readings of that same identifier count once. More than one distinct readable identifier remains ambiguous.
- Camera: three matching frames spanning two seconds are required. The same plate is suppressed until three blank frames spanning three seconds. Uncertain or multiple detections do not rearm it.
- OCR accepts hyphens during recognition, orders spatial text blocks before normalization, and uses the least confident block as its score so a weak prefix cannot be hidden by a strong suffix.
- Detection score must be at least 0.50 and OCR score at least 0.80, with 4–15 ASCII letters/digits including a digit. These are initial heuristics, not calibrated accuracy guarantees.
- Reuse the event UUID when retrying a failed request. A recorded event returns the same response without another mutation. The dashboard submits only one request at a time.
- Camera gates are saved in SQLite and survive server/browser refresh. The browser keeps its station ID in local storage. Use one station tab for the demo.

`event.status` can be `processed`, `stabilizing`, `already_seen`, `ready`, `rearming`, `empty`, `uncertain`, or `multiple`. Accepted events also contain `action` (`entry` or `exit`) and `session`.

## Billing and records

New visits use **PKR 10 per started minute**, minimum one minute. Money is integer minor units; 1000 minor units equals PKR 10. Server timestamps use UTC. The rate and unit are saved at entry. Legacy visits keep their original hourly rates. Closed visits remain in history and their receipts are immutable.

`GET /parking/active`, `/parking/history`, `/parking/summary`, `/parking/pricing`, and `/parking/sessions/{id}/receipt` support the dashboard. Receipt JSON is displayed and printed/saved as PDF in the browser.

`POST /predict` remains a read-only detection/OCR endpoint. Earlier confirmed manual entry and exit endpoints remain available for compatibility, but the automatic dashboard does not call them.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

For isolated UI testing, run `tests/preview_dashboard.py` with the same Python environment and open http://127.0.0.1:8001/. It loads the real model but uses a temporary database, separate from saved visits. Stop the test server afterward.

Model accuracy must be measured separately. Passing workflow tests does not establish OCR accuracy or real-camera performance.

## OCR engine

RapidOCR is now the default CPU engine. Install the updated requirements and restart the server after dependency changes. `SMARTPARK_OCR=easyocr` keeps the older recognizer available for comparison; `rapidocr` is the default. Responses include `ocr.engine` and `ocr.method`. Wide low-confidence crops may use `whole_crop_agreement`: original and inverted grayscale recognition must agree before acceptance. Confidence thresholds remain unchanged. See the root README and `scripts/compare_ocr.py` for the four-example development comparison and its limitations.
