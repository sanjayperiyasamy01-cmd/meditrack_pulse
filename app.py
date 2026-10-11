from flask import Flask, render_template, request, jsonify
import sqlite3
from pathlib import Path
from datetime import date, datetime
import math

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "meditrack.db"
app = Flask(__name__)

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with connect_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS centres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            distance_km REAL DEFAULT 0,
            contact TEXT DEFAULT '',
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            centre_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'General',
            stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
            daily_usage REAL NOT NULL DEFAULT 0 CHECK(daily_usage >= 0),
            minimum_stock INTEGER NOT NULL DEFAULT 10 CHECK(minimum_stock >= 0),
            unit TEXT NOT NULL DEFAULT 'units',
            expiry_date TEXT DEFAULT '',
            next_delivery_date TEXT DEFAULT '',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(centre_id) REFERENCES centres(id)
        );
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_name TEXT NOT NULL,
            from_centre_id INTEGER NOT NULL,
            to_centre_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            status TEXT NOT NULL DEFAULT 'Pending',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(from_centre_id) REFERENCES centres(id),
            FOREIGN KEY(to_centre_id) REFERENCES centres(id)
        );
        """)
        count = db.execute("SELECT COUNT(*) FROM centres").fetchone()[0]
        if count == 0:
            db.executemany(
                "INSERT INTO centres(name,location,distance_km,contact) VALUES(?,?,?,?)",
                [
                    ("Central Primary Health Centre", "Central Block", 0, "pharmacist@demo.local"),
                    ("Kaveri Primary Health Centre", "East Block Road", 2.4, "kaveri@demo.local"),
                    ("Greenfield Health Centre", "Greenfield", 3.1, "greenfield@demo.local"),
                    ("North Block PHC", "North Block", 4.8, "north@demo.local"),
                ],
            )
            centres = {r["name"]: r["id"] for r in db.execute("SELECT id,name FROM centres")}
            now = datetime.now().isoformat(timespec="seconds")
            sample = [
                (centres["Central Primary Health Centre"], "Paracetamol Syrup 125 mg/5 ml", "Essential medicine", 100, 20, 80, "bottles", "2027-04-30", "2026-10-22", now),
                (centres["Central Primary Health Centre"], "Paracetamol Tablets 500 mg", "Pain relief", 420, 35, 100, "tablets", "2027-08-15", "2026-10-20", now),
                (centres["Central Primary Health Centre"], "ORS Sachets", "Rehydration", 36, 18, 50, "sachets", "2027-02-20", "2026-10-25", now),
                (centres["Central Primary Health Centre"], "Amoxicillin 250 mg", "Antibiotic", 240, 20, 60, "capsules", "2027-06-10", "2026-10-20", now),
                (centres["Central Primary Health Centre"], "Cetirizine 10 mg", "Antihistamine", 180, 10, 40, "tablets", "2027-10-05", "2026-10-20", now),
                (centres["Central Primary Health Centre"], "Zinc Tablets 20 mg", "Supplement", 25, 8, 30, "tablets", "2027-01-18", "2026-10-24", now),
                (centres["Kaveri Primary Health Centre"], "Paracetamol Syrup 125 mg/5 ml", "Essential medicine", 180, 8, 40, "bottles", "2027-04-30", "2026-10-22", now),
                (centres["Greenfield Health Centre"], "Paracetamol Syrup 125 mg/5 ml", "Essential medicine", 145, 7, 35, "bottles", "2027-06-30", "2026-10-24", now),
                (centres["North Block PHC"], "ORS Sachets", "Rehydration", 120, 5, 25, "sachets", "2027-02-20", "2026-10-25", now),
            ]
            db.executemany("""INSERT INTO medicines
                (centre_id,name,category,stock,daily_usage,minimum_stock,unit,expiry_date,next_delivery_date,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", sample)

def medicine_dict(row):
    m = dict(row)
    usage = float(m["daily_usage"] or 0)
    m["days_remaining"] = math.floor(m["stock"] / usage) if usage > 0 else None
    delivery = m.get("next_delivery_date") or ""
    try:
        m["days_to_delivery"] = (date.fromisoformat(delivery) - date.today()).days
    except ValueError:
        m["days_to_delivery"] = None
    days = m["days_remaining"]
    if days is None:
        m["status"] = "Check usage"
    elif days <= 3 or (m["days_to_delivery"] is not None and days < m["days_to_delivery"] and m["stock"] <= m["minimum_stock"]):
        m["status"] = "Critical"
    elif m["stock"] <= m["minimum_stock"] or days <= 7 or (
        m["days_to_delivery"] is not None and days < m["days_to_delivery"]
    ):
        m["status"] = "Low stock"
    else:
        m["status"] = "Healthy"
    m["shortage_before_delivery"] = bool(
        days is not None and m["days_to_delivery"] is not None and days < m["days_to_delivery"]
    )
    return m

@app.route("/")
def dashboard():
    return render_template("index.html")

@app.get("/api/centres")
def get_centres():
    with connect_db() as db:
        rows = db.execute("SELECT * FROM centres WHERE active=1 ORDER BY distance_km").fetchall()
    return jsonify([dict(r) for r in rows])

@app.get("/api/medicines")
def get_medicines():
    centre_id = request.args.get("centre_id", type=int)
    with connect_db() as db:
        if centre_id:
            rows = db.execute("""SELECT m.*,c.name AS centre_name FROM medicines m
                JOIN centres c ON c.id=m.centre_id WHERE m.centre_id=? ORDER BY m.name""", (centre_id,)).fetchall()
        else:
            rows = db.execute("""SELECT m.*,c.name AS centre_name FROM medicines m
                JOIN centres c ON c.id=m.centre_id ORDER BY c.name,m.name""").fetchall()
    items = [medicine_dict(r) for r in rows]
    return jsonify(items)

@app.post("/api/medicines")
def add_medicine():
    data = request.get_json(silent=True) or {}
    required = ["centre_id", "name", "stock", "daily_usage", "unit"]
    if any(data.get(k) in (None, "") for k in required):
        return jsonify(error="centre_id, name, stock, daily_usage and unit are required"), 400
    try:
        stock = int(data["stock"]); usage = float(data["daily_usage"])
        minimum = int(data.get("minimum_stock", 10)); centre_id = int(data["centre_id"])
        if stock < 0 or usage < 0 or minimum < 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify(error="Stock, usage and minimum stock must be non-negative numbers"), 400
    with connect_db() as db:
        if not db.execute("SELECT 1 FROM centres WHERE id=? AND active=1", (centre_id,)).fetchone():
            return jsonify(error="Health centre not found"), 404
        cur = db.execute("""INSERT INTO medicines
            (centre_id,name,category,stock,daily_usage,minimum_stock,unit,expiry_date,next_delivery_date,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (centre_id, data["name"].strip(), data.get("category","General").strip(), stock, usage,
             minimum, data["unit"].strip(), data.get("expiry_date",""), data.get("next_delivery_date",""),
             datetime.now().isoformat(timespec="seconds")))
        new_id = cur.lastrowid
    return jsonify(id=new_id, message="Medicine added"), 201

@app.patch("/api/medicines/<int:medicine_id>")
def update_medicine(medicine_id):
    data = request.get_json(silent=True) or {}
    allowed = {"stock", "daily_usage", "minimum_stock", "expiry_date", "next_delivery_date", "category", "name"}
    fields = {k:v for k,v in data.items() if k in allowed}
    if not fields:
        return jsonify(error="No editable fields provided"), 400
    for k in ("stock", "daily_usage", "minimum_stock"):
        if k in fields:
            try:
                fields[k] = float(fields[k]) if k == "daily_usage" else int(fields[k])
                if fields[k] < 0: raise ValueError()
            except (TypeError, ValueError):
                return jsonify(error=f"{k} must be non-negative"), 400
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    sql = ", ".join(f"{key}=?" for key in fields)
    with connect_db() as db:
        cur = db.execute(f"UPDATE medicines SET {sql} WHERE id=?", (*fields.values(), medicine_id))
        if cur.rowcount == 0:
            return jsonify(error="Medicine not found"), 404
    return jsonify(message="Medicine updated")

@app.get("/api/summary")
def summary():
    with connect_db() as db:
        rows = db.execute("""SELECT m.*,c.name AS centre_name FROM medicines m
            JOIN centres c ON c.id=m.centre_id""").fetchall()
        transfers = db.execute("SELECT COUNT(*) FROM transfers WHERE status='Pending'").fetchone()[0]
    items = [medicine_dict(r) for r in rows]
    return jsonify({
        "total_medicines": len(items),
        "low_stock": sum(m["status"] == "Low stock" for m in items),
        "critical": sum(m["status"] == "Critical" for m in items),
        "pending_transfers": transfers,
        "shortage_alerts": [m for m in items if m["shortage_before_delivery"] or m["status"] == "Critical"]
    })

@app.get("/api/matches/<int:medicine_id>")
def matches(medicine_id):
    with connect_db() as db:
        requested = db.execute("""SELECT m.*,c.name AS centre_name FROM medicines m
            JOIN centres c ON c.id=m.centre_id WHERE m.id=?""", (medicine_id,)).fetchone()
        if not requested:
            return jsonify(error="Medicine not found"), 404
        rows = db.execute("""SELECT m.*,c.name AS centre_name,c.distance_km FROM medicines m
            JOIN centres c ON c.id=m.centre_id
            WHERE lower(m.name)=lower(?) AND m.centre_id<>? AND c.active=1
            ORDER BY c.distance_km ASC""", (requested["name"], requested["centre_id"])).fetchall()
    # A conservative demo reserve: never propose stock below the source centre's minimum stock.
    results = []
    for row in rows:
        item = medicine_dict(row)
        transferable = max(0, item["stock"] - item["minimum_stock"])
        if transferable > 0:
            results.append({
                "centre_id": item["centre_id"], "centre_name": item["centre_name"],
                "distance_km": item["distance_km"], "stock": item["stock"],
                "unit": item["unit"], "expiry_date": item["expiry_date"],
                "transferable_estimate": transferable
            })
    return jsonify({"requested_medicine": requested["name"], "matches": results})

@app.post("/api/transfers")
def create_transfer():
    data = request.get_json(silent=True) or {}
    try:
        medicine_id = int(data["medicine_id"]); from_id = int(data["from_centre_id"])
        to_id = int(data["to_centre_id"]); quantity = int(data["quantity"])
        if quantity <= 0 or from_id == to_id: raise ValueError()
    except (KeyError, TypeError, ValueError):
        return jsonify(error="Provide valid medicine_id, from_centre_id, to_centre_id and positive quantity"), 400
    with connect_db() as db:
        medicine = db.execute("SELECT * FROM medicines WHERE id=?", (medicine_id,)).fetchone()
        if not medicine:
            return jsonify(error="Medicine not found"), 404
        if medicine["centre_id"] != from_id:
            return jsonify(error="Selected medicine record does not belong to the source centre"), 400
        source = db.execute("SELECT * FROM medicines WHERE centre_id=? AND lower(name)=lower(?)", (from_id, medicine["name"])).fetchone()
        target = db.execute("SELECT * FROM centres WHERE id=? AND active=1", (to_id,)).fetchone()
        if not target:
            return jsonify(error="Destination centre not found"), 404
        transferable = max(0, source["stock"] - source["minimum_stock"])
        if quantity > transferable:
            return jsonify(error=f"Quantity exceeds estimated transferable stock ({transferable} {source['unit']})."), 400
        cur = db.execute("""INSERT INTO transfers(medicine_name,from_centre_id,to_centre_id,quantity,status,notes,created_at)
            VALUES(?,?,?,?,?,?,?)""", (source["name"], from_id, to_id, quantity, "Pending",
            "Requires authorized staff approval and expiry/storage verification.", datetime.now().isoformat(timespec="seconds")))
        transfer_id = cur.lastrowid
    return jsonify(id=transfer_id, status="Pending", message="Transfer proposal created; no stock has moved."), 201

@app.get("/api/transfers")
def get_transfers():
    with connect_db() as db:
        rows = db.execute("""SELECT t.*,s.name AS from_name,d.name AS to_name FROM transfers t
            JOIN centres s ON s.id=t.from_centre_id JOIN centres d ON d.id=t.to_centre_id
            ORDER BY t.id DESC""").fetchall()
    return jsonify([dict(r) for r in rows])

@app.post("/api/transfers/<int:transfer_id>/approve")
def approve_transfer(transfer_id):
    # Demo endpoint only: production must enforce logged-in role permissions and audited approval.
    with connect_db() as db:
        transfer = db.execute("SELECT * FROM transfers WHERE id=?", (transfer_id,)).fetchone()
        if not transfer: return jsonify(error="Transfer not found"), 404
        if transfer["status"] != "Pending": return jsonify(error="Transfer is not pending"), 409
        source = db.execute("SELECT * FROM medicines WHERE centre_id=? AND lower(name)=lower(?)",
                            (transfer["from_centre_id"], transfer["medicine_name"])).fetchone()
        if not source: return jsonify(error="Source medicine record not found"), 404
        available = max(0, source["stock"] - source["minimum_stock"])
        if transfer["quantity"] > available:
            return jsonify(error="Stock has changed; there is not enough transferable stock"), 409
        target = db.execute("SELECT id FROM medicines WHERE centre_id=? AND lower(name)=lower(?)",
                            (transfer["to_centre_id"], transfer["medicine_name"])).fetchone()
        db.execute("UPDATE medicines SET stock=stock-?,updated_at=? WHERE id=?",
                   (transfer["quantity"], datetime.now().isoformat(timespec="seconds"), source["id"]))
        if target:
            db.execute("UPDATE medicines SET stock=stock+?,updated_at=? WHERE id=?",
                       (transfer["quantity"], datetime.now().isoformat(timespec="seconds"), target["id"]))
        else:
            db.execute("""INSERT INTO medicines(centre_id,name,category,stock,daily_usage,minimum_stock,unit,expiry_date,next_delivery_date,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (transfer["to_centre_id"], source["name"], source["category"], transfer["quantity"], 0,
                 0, source["unit"], source["expiry_date"], "", datetime.now().isoformat(timespec="seconds")))
        db.execute("UPDATE transfers SET status='Approved (demo)' WHERE id=?", (transfer_id,))
    return jsonify(message="Demo transfer recorded. In a real deployment, approval identity and dispatch/receipt verification are required.")

@app.get("/api/health")
def health():
    return jsonify(status="ok", database=str(DB_PATH.name), note="Local demo API; protect before any real deployment.")

init_db()
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
