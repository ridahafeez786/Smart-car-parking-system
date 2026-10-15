# SmartPark — Smart Car Parking System

A computer-vision capstone by **Rida Hafeez** that reads vehicle number plates and manages parking visits automatically. It combines a fine-tuned YOLO11n detector, RapidOCR, a FastAPI backend, and a browser dashboard.

**[Open the live demo](https://smartpark.up.railway.app/)** · **[API documentation](https://smartpark.up.railway.app/docs)** · **[Project report](reports/Smart_Parking_Report.pdf)**

Hosted on **Railway**. No installation is needed to try the dashboard.

> This is a shared academic demo without authentication. Visitors can view parking records and trigger entry/exit events. Use demonstration images. Live-camera accuracy and performance are still being evaluated.

## What the app does

- Accepts an uploaded image or frames from your browser's camera.
- Detects the plate, reads its characters, and checks the reading before recording it.
- Creates an entry when an accepted plate has no active parking session.
- Closes the active session when the same plate appears again as a new event.
- Calculates **Rs 10 per started minute**, with a minimum charge of Rs 10.
- Shows active vehicles, searchable history, and receipts with browser **Print / Save PDF**.

Completed sessions remain in history; they are not deleted.

## Try the demo

### Upload an image

1. Open the [dashboard](https://smartpark.up.railway.app/) and select **Upload image**.
2. Choose a clear JPG, PNG, or WebP vehicle image, up to 12 MB.
3. Wait for the entry message and check **Active parking**.
4. Select the same image again to record an exit and create a receipt.
5. Select a different plate to start another visit.

A failed request can be retried without duplicating its recorded event.

### Use the live camera

1. Select **Live camera → Start camera** and allow camera access.
2. Hold one plate steady until the entry message appears.
3. Remove it completely until the scanner says **Ready**.
4. Show it again to record the exit.

For a phone-screen demonstration, open the image full-screen, enlarge the plate, reduce glare, and hold the phone straight. The preview is live, but recognition samples frames sequentially; it does not analyze every video frame. Use one browser tab as the camera station.

**A green box does not mean the plate has been read.** Automatic recording requires:

| Check | Requirement |
|---|---|
| Plate detection score | At least 50% |
| OCR score | At least 80%, with a valid normalized plate string |
| Plate selection | Exactly one distinct readable plate; unreadable background plates are ignored |
| Camera stability | Three matching readings spanning at least two seconds |
| Same-plate reappearance | Three plate-free readings spanning at least three seconds before it can trigger again |

If the app shows **Text unreadable**, no vehicle is saved. Improve focus, plate size, lighting, or viewing angle. Two different readable plates in one frame are treated as ambiguous. Confidence scores are not guarantees of correctness.

## How it works

```text
Image upload / browser camera
              ↓
       YOLO11n plate detection
              ↓
     Plate crop → RapidOCR text
              ↓
     Validation + repeat protection
              ↓
       Active parking session?
        ├─ No  → Record entry
        └─ Yes → Record exit → Calculate fee → Receipt
              ↓
         SQLite + dashboard
```

Entry and exit use server timestamps. Times are stored in UTC and displayed in Pakistan time. The rate is saved when a visit starts: 60 seconds costs Rs 10; 61 seconds costs Rs 20. Existing visits retain their saved tariff. Payment collection is not implemented.

## Technical stack

| Layer | Technology |
|---|---|
| Plate detector | Ultralytics YOLO11n, fine-tuned on annotated vehicle images |
| Text recognition | RapidOCR 3.10.0, PP-OCRv6, ONNX Runtime 1.31.0 |
| Backend | Python, FastAPI, Uvicorn, Pillow |
| Interface | HTML, CSS, JavaScript; served by FastAPI |
| Database | SQLite |
| Training | Google Colab, Tesla T4 GPU |
| Deployment | Docker on Railway; CPU inference |

A local GPU is not required. Camera frames and uploaded images are processed by the backend: on your computer for local use, or on Railway for the hosted demo.

## Run locally on Windows

Install Python 3.12 and Git, then run these commands in PowerShell:

```powershell
git clone https://github.com/ridahafeez786/Smart-car-parking-system.git
cd Smart-car-parking-system
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Open **http://127.0.0.1:8000/**. Keep the terminal running while using the app; press **Ctrl+C** to stop it. API documentation is at **http://127.0.0.1:8000/docs**.

The trained **`best.pt` is included in the repository**. No retraining or dataset download is required to run the demo. OCR may download its models on first local use. Local records are stored in `storage/parking.sqlite3` by default.

## Deploy your copy on Railway

1. Connect your GitHub repository as a Railway service.
2. Keep the service root at `/`. The included `Dockerfile` and `railway.json` define the build and health check; clear conflicting custom build/start commands.
3. Attach a persistent volume at `/data`.
4. Add the following service variables:

   | Variable | Value |
   |---|---|
   | `PORT` | `8080` |
   | `SMARTPARK_DB_PATH` | `/data/parking.sqlite3` |
   | `SMARTPARK_OCR` | `rapidocr` (the container default) |

5. Deploy and wait for a successful health check.
6. Under **Settings → Networking**, select **Generate Domain** and use target port **8080**.
7. Open the HTTPS address, allow camera access, and test entry, exit, receipts, and persistence after a restart.

The Docker build installs CPU dependencies, includes `best.pt`, and exercises OCR to download its models before deployment. It runs one Uvicorn worker. Local datasets, databases, and private settings are excluded from the build context.

**Persistent storage matters:** setting the database path alone is not enough; the volume must also be mounted there. A new deployment starts with its own database, not your laptop's records. Railway resource usage is billed under your account's plan; the included domain does not make hosting free.

## Dataset and detector results

Images were collected from Kaggle and photographs of parked cars, then annotated in Roboflow and exported as YOLO bounding-box labels. The cleaned training split contains **821 images and 844 plate boxes**. Labels identify plate locations, not their text.

YOLO11n was fine-tuned for **30 epochs**, at image size **640** and batch size **8**, on a Colab Tesla T4. Training took approximately **10.4 minutes**.

| Split | Images | Plate boxes | Precision | Recall | mAP@50 | mAP@50-95 |
|---|---:|---:|---:|---:|---:|---:|
| Validation | 141 | 157 | 0.922 | 0.866 | 0.914 | 0.634 |
| Held-out test | 199 | 274 | 0.938 | 0.763 | 0.824 | 0.575 |

These are **plate-detection metrics**, not OCR or complete parking-system accuracy. Some plates are missed, particularly on challenging images. Exact duplicates were reconciled during cleanup; near-duplicate checking remains a limitation.

The dataset is not distributed here. Check source permissions before redistributing images. To train your own detector, use the [Colab notebook](notebooks/train_plate_detector_colab.ipynb) with your labeled dataset.

## OCR experimentation

We started with **EasyOCR**, improved crop preprocessing and text ordering, and then selected **RapidOCR** after testing difficult stacked and green plates.

| Pipeline | Exact matches on four development examples |
|---|---:|
| Improved EasyOCR | 3 / 4 |
| RapidOCR with fallback | 4 / 4 |

These examples were used during development, so this is **not a held-out benchmark or a claim of 100% accuracy**.

The current pipeline tries a 256-pixel minimum-side resize, retries uncertain text at 736 pixels, and can compare original and inverted whole-crop readings for wide plates. The four examples remained correct after the resize update. Difficult readings may require more processing; Railway latency has not been systematically benchmarked.

See the [original comparison](evidence/ocr_comparison.json) and [resize regression check](evidence/ocr_resize_regression.json). Reproduce with `python scripts/compare_ocr.py` after supplying the original dataset. To compare EasyOCR locally, set `$env:SMARTPARK_OCR="easyocr"` before starting the server.

## Testing and troubleshooting

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The last verified run passed **24 automated tests**, covering parking rules, billing boundaries, persistence, repeat protection, OCR ordering, and fallback agreement. These tests do not measure recognition accuracy. GitHub Actions also runs the test suite.

| Symptom | What to check |
|---|---|
| Plate boxed but no entry | Read the OCR score and scanner status; detection alone is insufficient. |
| Camera takes time to record | It needs three stable readings. Initial model loading, retries, CPU load, and upload speed add delay. |
| Same plate does not exit | Remove it until **Ready**, then present it again. |
| Camera will not start | Use HTTPS or localhost, allow permission, and close other apps using the camera. |
| Records disappear after deployment | Verify the volume mount and `SMARTPARK_DB_PATH`. |
| Railway cannot build | Verify repository root `/` and that the latest Docker configuration is deployed. |

Scan responses include `processing_seconds`; server logs report scan status, action, and processing time. Use them to distinguish an uncertain reading from a saved entry or a server error.

## Repository guide

```text
backend/          Detection, OCR, parking rules, API, and browser dashboard
best.pt           Trained YOLO11n checkpoint
notebooks/        Colab training notebook
scripts/          Dataset audit, OCR comparison, and report tools
tests/            Automated tests
evidence/         Dataset audit and experiment results
reports/          Project report
Dockerfile        CPU deployment image
railway.json      Railway build and health-check configuration
```

## Current limitations

This prototype does not infer physical travel direction: a new accepted appearance toggles the visit's state. Separate camera stations are not coordinated as a real entry/exit gate system. Blur, glare, tiny text, and OCR mistakes can prevent or misidentify a visit. A separate transcribed OCR test set, physical camera evaluation, access controls, and multi-user testing are needed before unattended real-world billing.
