# MediTrack Pulse — Real-World Prototype

A local multi-centre medicine inventory prototype using Flask + SQLite + HTML/CSS/JavaScript.

## Requirements
- Python 3.10 or newer
- Visual Studio Code
- Internet connection only to load optional Google Fonts; the app itself runs locally

## Run in VS Code (Windows)
1. Extract this folder.
2. Open the folder in VS Code.
3. Open Terminal > New Terminal.
4. Create a virtual environment (recommended):
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```
   If `py` is unavailable, try `python`.
5. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
6. Start the server:
   ```powershell
   python app.py
   ```
7. Open `http://127.0.0.1:5000` in your browser.
8. Stop the server with Ctrl+C in the terminal.

## Features
- SQLite persistence across refreshes and server restarts
- Multiple sample health centres and medicine stock records
- Low-stock and estimated stock-out alerts
- Delivery-date comparison
- Update stock and daily usage
- Add medicines
- Match same-name medicine at nearby centres and estimate transferable quantity after minimum reserve
- Create transfer proposals, view requests, and demo-approve proposals
- Export inventory as CSV

## API endpoints
- `GET /api/health`
- `GET /api/centres`
- `GET /api/medicines?centre_id=1`
- `POST /api/medicines`
- `PATCH /api/medicines/<id>`
- `GET /api/summary`
- `GET /api/matches/<medicine_id>`
- `GET /api/transfers`
- `POST /api/transfers`
- `POST /api/transfers/<id>/approve`

## Important limitations
This is a learning/hackathon prototype, NOT a production healthcare system. It has no login, role-based authorization, audit-grade identity, encryption, deployment hardening, automated notification service, verified geolocation, or validated clinical forecasting. The demo approval endpoint changes sample inventory and is not secure for real-world use. Do not enter real patient data or use it to authorize real medicine movement. A production deployment requires security review, authenticated staff roles, audited approval, backups, monitoring, validated transfer procedures, medicine batch/lot tracking, expiry checks and regulatory approval.
