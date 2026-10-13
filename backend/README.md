# Smart Parking API: first milestone

## Dashboard

Open **http://127.0.0.1:8000/** while the API server is running. Upload a vehicle photo, click **Read plate**, review the recognized text, choose Entry or Exit, and confirm. Active visits and history are searchable below. **Check out** selects a parked vehicle for exit; the receipt supports browser printing or Save as PDF. No additional packages or frontend server are required.

For isolated browser testing, run `.\.venv\Scripts\python.exe tests\preview_dashboard.py` and open port 8001. This uses the real model with a temporary parking database, separate from your saved visits. Stop the test server with Ctrl+C afterward.

This local API loads the project's `best.pt` weights, detects license-plate boxes, and can optionally read plate characters with EasyOCR. It runs inference on the CPU, so no local GPU is needed. OCR results are uncertain and must be reviewed before being used to open or close a parking session.

## Run on Windows

Open the project folder in VS Code, then open **Terminal → New Terminal**. In PowerShell, run:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

If dependency installation reports that a package has no compatible Python build, install Python 3.12 and replace `py -3.14` with `py -3.12` when creating `.venv`.

When the server starts, open <http://127.0.0.1:8000/docs>, expand **POST /predict**, choose an image of a car, and set `include_ocr` to `true` to read plate text. Select **Execute**. The first OCR request may download EasyOCR's English model files and take longer; later requests reuse the loaded model. The response includes the plate bounding box, detection confidence, recognized text, OCR confidence, and a manual-review flag. `/health` reports whether the weights loaded.

The model file is expected at the project root as `best.pt`. Keep a backup of it. Do not move it into the `backend` directory.

## Try a complete parking visit

Refresh `/docs` after the server reloads to see the **Parking** endpoints.

1. Use `/predict` with OCR enabled and check the plate text against the image.
2. Open `POST /parking/entry`, choose **Try it out**, and send:

   ```json
   {"plate": "TN99F2378", "confirmed": true}
   ```

3. Copy the returned `id`. `GET /parking/active` shows the vehicle and its arrival time.
4. At exit, check the plate again. In `POST /parking/sessions/{session_id}/exit`, paste the saved `id` into `session_id` and send the same confirmed plate body.
5. The response includes departure time, duration, billed hours, amount, and a receipt URL. `GET /parking/history` retains the completed visit; `/parking/active` no longer includes it.

The initial demo tariff is **PKR 100 per started hour**, minimum one hour and no grace period. An immediate exit therefore costs PKR 100; exactly one hour costs PKR 100, and one hour plus any fraction costs PKR 200. This is an illustrative tariff, not an agreed real parking rate. Money is stored as integer minor units (100 minor units = PKR 1); the response also includes a formatted `amount`. The rate is saved at entry so later changes cannot alter existing visits.

Entry and exit timestamps come from the server in UTC. SQLite data is saved in `storage/parking.sqlite3`, persists across server restarts, and is ignored by Git. Duplicate active entries return HTTP 409. Repeating an exit for the same session returns its existing receipt without closing a later visit. Only exactly matching confirmed plates can close a session. The receipt API returns JSON; the dashboard displays a printable receipt that can be saved as PDF using the browser.

Run the parking checks with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
