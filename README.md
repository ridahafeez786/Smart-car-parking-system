# Smart Car Parking System

A computer-vision capstone prototype for managing parking entry and exit. A local dashboard connects a custom-trained YOLO11n plate detector and RapidOCR with automatic parking records, fee calculation, and receipts.

> **Project status:** Automatic image uploads and browser-camera scanning, plate detection and OCR, entry/exit, searchable records, minute billing, and printable receipts are implemented. Broader OCR and live-camera accuracy evaluation remain outstanding.

## What it does

```text
Image upload or camera frame → YOLO plate detection → RapidOCR → automatic entry/exit → receipt
```

A recognized plate starts a visit if it is not parked. Its next accepted appearance closes the visit. A different plate starts a separate visit. Completed visits stay in history.

Camera mode requires three consistent readings spanning at least two seconds. A recorded plate cannot trigger again until the camera observes no plates for three readings spanning at least three seconds. Unreadable background plates are ignored when exactly one distinct plate passes the acceptance rules. Observations with no readable plate or multiple distinct readable plates are skipped. These rules reduce accidental repeated events; they cannot guarantee correct OCR.

The detector locates plates and RapidOCR reads characters. Training labels contain bounding boxes, not plate text.

## Model and evaluation

YOLO11n was fine-tuned for 30 epochs using a Tesla T4 in Google Colab. The report keeps validation and held-out test results separate:

| Split | Images | Plate instances | Precision | Recall | mAP@50 | mAP@50-95 |
|---|---:|---:|---:|---:|---:|---:|
| Validation | 141 | 157 | 0.922 | 0.866 | 0.914 | 0.634 |
| Held-out test | 199 | 274 | 0.938 | 0.763 | 0.824 | 0.575 |

The test set is held out from training. The lower test recall indicates that some plates are missed on unseen examples; this is an area for improvement. Training evidence and the dataset audit are saved in [`evidence/`](evidence/).

## Tech stack

- **Object detection:** Ultralytics YOLO11n
- **API:** FastAPI and Uvicorn
- **Image handling:** Pillow
- **Training:** Google Colab with a Tesla T4 GPU
- **Inference:** CPU supported; a local GPU is not required
- **OCR:** RapidOCR (PP-OCRv6 via ONNX Runtime on CPU); EasyOCR retained as a comparison option
- **Parking records:** SQLite sessions, fee calculation, and JSON receipts
- **Interface:** responsive HTML/CSS/JavaScript dashboard served by FastAPI; no frontend build or separate server
- **Receipts:** view saved visits and print or save as PDF through the browser

## Run the plate detection API

The API expects a trained checkpoint named `best.pt` in the repository root. The checkpoint and dataset are kept out of Git; this repository cannot run plate detection until you supply the checkpoint. Train one using the included Colab notebook and your labeled dataset, then download `best.pt` to the project root. The project author's existing local checkpoint also works.

Clone the repository first:

```powershell
git clone https://github.com/ridahafeez786/Smart-car-parking-system.git
cd Smart-car-parking-system
```

From a PowerShell terminal opened at the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

If Python 3.12 is not installed, use a Python version supported by your installed dependencies. Open **<http://127.0.0.1:8000/>** while the server remains running.

### Image demo

Select **Upload image** and choose a clear vehicle image. The application reads and records it automatically. Select the same image again to close the visit; select another plate to add another vehicle. No plate typing or confirmation is required. If a request fails, **Retry scan** reuses its event ID to prevent duplicate changes.

### Live camera demo

Select **Live camera → Start camera**, allow the browser's camera permission, and hold your phone's plate image steady in front of the laptop camera. Wait for the entry message. Remove the phone until **Ready** appears, then show the same plate again to exit. Holding it continuously does not repeatedly toggle entry and exit. Use one browser tab as the station; separate tabs or devices are not coordinated as one camera.

The webcam preview is continuous; CPU analysis samples frames sequentially, with a one-second pause between completed requests. Initial OCR loading can take longer. Use localhost or HTTPS for browser camera access. A remote phone browser accessing an ordinary HTTP LAN address may not have camera access.

**Tariff: Rs 10 per started minute**, minimum one minute, no grace period. An immediate exit costs Rs 10; exactly 60 seconds costs Rs 10; 61 seconds costs Rs 20. Existing visits retain the tariff saved at their entry, including older hourly visits. Receipts are available in history with **Print / Save PDF**.

Server timestamps are stored in UTC and displayed in Pakistan time. Records persist in `storage/parking.sqlite3`. API documentation remains at <http://127.0.0.1:8000/docs>.

## Automated checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

GitHub Actions runs the parking tests on pushes and pull requests. These check automatic toggling, event retries, camera stability and rearming, persistence, legacy tariff migration, billing boundaries, receipt access, and summary totals. The checks do not need a GPU, dataset, or model weights; they do not measure model accuracy.

## Train the detector

The Colab training notebook is [`notebooks/train_plate_detector_colab.ipynb`](notebooks/train_plate_detector_colab.ipynb). It uses the cleaned YOLO dataset and saves `best.pt`. Keep the test split for final evaluation; use the validation split when comparing training settings or confidence thresholds.

The dataset is not included in this repository. It contains third-party vehicle images; check its license and permissions before redistributing it. The cleaned local copy, archive files, and training outputs are ignored by Git. The project-trained root `best.pt` is included for deployment; other model files remain ignored.

## Railway deployment

Deploy the repository root using the included `Dockerfile` and `railway.json`.
Keep the service Root Directory at `/`, and clear any custom build/start command
overrides so the Docker configuration is used. The container installs CPU PyTorch,
loads the trained weights and RapidOCR during its build, and runs one Uvicorn worker
on Railway's `PORT`. The `/health` endpoint checks startup.

Attach a persistent volume at `/data` and set the service variable
`SMARTPARK_DB_PATH=/data/parking.sqlite3` before recording visits. Without a volume,
records in the container filesystem can disappear on redeployment. This starts a
fresh cloud database; local parking history is not uploaded.

After deployment succeeds, use Settings > Networking > Generate Domain and open
the HTTPS address. Allow camera access in the browser. Test image upload, entry,
exit, receipt, camera rearming, and persistence after a restart. Monitor memory and
usage while OCR runs; hosting does not guarantee recognition accuracy or latency.

This deployment is a shared demo parking lot, without authentication: public
visitors can see its records and trigger events. Use demo plates only. The supplied
Docker context excludes datasets, local databases, reports, and private settings.

## Repository layout

```text
backend/                 FastAPI detection and parking services
backend/static/          Dashboard HTML, CSS, and JavaScript
evidence/                Training evidence and dataset audit summary
scripts/                 Dataset preparation and audit utilities
notebooks/               Training notebook
```

## Limitations and next work

- Evaluate OCR against manually transcribed plates and review uncertain readings.
- Evaluate the phone-screen camera demo under blur, glare, motion and varying distances; add a tariff settings interface if needed.
- Add direct PDF downloads if needed; current PDF saving uses the browser print dialog.
- Evaluate OCR and the complete entry-to-exit workflow on separately labeled examples.
- Improve missed detections using validation-set analysis, then report final results once on the held-out test set.

This is an academic prototype, not a production access-control system. Automatic OCR can misidentify a vehicle even with a high score; the prototype is not suitable for unattended real billing without further evaluation and safeguards.

## OCR engine comparison

The default recognizer is RapidOCR 3.10.0 using bundled PP-OCRv6 models and ONNX Runtime 1.31.0 on CPU. Plate images are processed locally. Text blocks are spatially ordered. For wide crops with a weak or missing text detection, recognition of the entire crop is retried with original and inverted grayscale inputs; both must agree and pass the score threshold. Scores from different engines are not calibrated probabilities or directly comparable accuracy measures.

Four previously inspected development images were compared: Cars281, Cars320, Cars307 and Cars323. EasyOCR read 3/4 correctly; the RapidOCR pipeline read 4/4, including MH01DB0001 on the green plate. This small, targeted comparison helped select an engine and fallback; it is **not a held-out OCR accuracy benchmark**. In this run EasyOCR took about 0.18–0.27 s per crop and RapidOCR about 0.93–1.60 s, excluding shared YOLO detection and including lazy initialization where applicable. Measure live latency separately.

Reproduce with `python scripts/compare_ocr.py` after installing requirements and supplying the original local dataset and weights. Results are saved in `evidence/ocr_comparison.json`. To compare with the previous engine, set `$env:SMARTPARK_OCR="easyocr"` before starting Uvicorn. Default is `rapidocr`; switching requires a server restart.
