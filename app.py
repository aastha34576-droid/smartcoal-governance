from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = "smartcoal-demo-secret-key"
DB = "smartcoal.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn
def fetch_caaqms_data():
    """
    Fetch latest environmental monitoring data from
    Coal India's official CAAQMS portal.

    Returns a list of clean monitoring records.
    """
    url = "https://apps.coalindia.in/ords/f?p=159:11"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        table = soup.find("table", class_="a-IRR-table")

        if table is None:
            return []

        headers = [
            h.get_text(" ", strip=True)
            for h in table.find_all("th")
        ]

        records = []

        for row in table.find_all("tr")[1:]:
            cells = [
                c.get_text(" ", strip=True)
                for c in row.find_all(["td", "th"])
            ]

            if len(cells) != len(headers):
                continue

            raw = dict(zip(headers, cells))

            def number(value):
                if value in ("", "-", "NA", "N/A", None):
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None

            records.append({
                "company": raw.get("Company Name"),
                "area": raw.get("Area Name"),
                "mine_name": raw.get("Mine Name"),
                "created_at": raw.get("Creation datetime"),
                "record_time": raw.get("Record time"),
                "pm25": number(raw.get("PM - 2.5 (µg/m3)")),
                "pm10": number(raw.get("PM - 10 (µg/m3)")),
                "so2": number(raw.get("SO2 (µg/m3)")),
                "no2": number(raw.get("NO2  (µg/m3)")),
                "co": number(raw.get("CO (mg/m3)")),
                "device_id": raw.get("Device ID"),
                "created_by": raw.get("Created by")
            })

        return records

    except requests.RequestException as e:
        print("CAAQMS REQUEST ERROR:", repr(e))
        return []

    except Exception as e:
        print("CAAQMS PARSING ERROR:", repr(e))
        return []

        

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS mines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subsidiary TEXT NOT NULL,
        state TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        compliance INTEGER NOT NULL,
        risk_score INTEGER NOT NULL,
        status TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mine_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        observation TEXT NOT NULL,
        severity TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        created_at TEXT NOT NULL,
        corrective_action TEXT,
        action_status TEXT DEFAULT 'Pending',
        FOREIGN KEY(mine_id) REFERENCES mines(id)
    );

    CREATE TABLE IF NOT EXISTS compliance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mine_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        requirement TEXT NOT NULL,
        due_date TEXT NOT NULL,
        status TEXT NOT NULL,
        FOREIGN KEY(mine_id) REFERENCES mines(id)
    );

    CREATE TABLE IF NOT EXISTS contractors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mine_id INTEGER NOT NULL,
        performance INTEGER NOT NULL,
        risk TEXT NOT NULL,
        FOREIGN KEY(mine_id) REFERENCES mines(id)
    );    CREATE TABLE IF NOT EXISTS environmental_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mine_id INTEGER NOT NULL,
        pm25 REAL,
        pm10 REAL,
        so2 REAL,
        no2 REAL,
        co REAL,
        recorded_at TEXT NOT NULL,
        source TEXT NOT NULL,
        FOREIGN KEY(mine_id) REFERENCES mines(id)
    );
    """)

    if cur.execute("SELECT COUNT(*) FROM mines").fetchone()[0] == 0:
        mines = [
            ("Dhanbad Central Mine","BCCL","Jharkhand",23.7957,86.4304,74,82,"HIGH"),
            ("Korba East Mine","SECL","Chhattisgarh",22.3595,82.7501,88,51,"MEDIUM"),
            ("Talcher North Mine","MCL","Odisha",20.9517,85.2167,93,27,"LOW"),
            ("Raniganj West Mine","ECL","West Bengal",23.6160,87.1300,68,89,"HIGH"),
            ("Singrauli Open Cast","NCL","Madhya Pradesh",24.1990,82.6750,81,63,"MEDIUM"),
        ]
        cur.executemany("""INSERT INTO mines
            (name, subsidiary, state, lat, lon, compliance, risk_score, status)
            VALUES (?,?,?,?,?,?,?,?)""", mines)

        inspections = [
            (1,"Safety","Damaged safety barrier near haul road","High",23.7957,86.4304,
             "2026-08-22 09:15","Repair barrier and verify","Open"),
            (1,"Environment","Dust level above internal threshold","Medium",23.7965,86.4310,
             "2026-08-21 14:20","Inspect water-sprinkling system","Pending"),
            (2,"Labour","Attendance mismatch in contractor records","Medium",22.3595,82.7501,
             "2026-08-20 11:05","Reconcile attendance data","Pending"),
            (4,"Safety","Repeated PPE non-compliance","High",23.6160,87.1300,
             "2026-08-22 10:30","Conduct contractor safety briefing","Escalated"),
        ]
        cur.executemany("""INSERT INTO inspections
            (mine_id,category,observation,severity,latitude,longitude,created_at,corrective_action,action_status)
            VALUES (?,?,?,?,?,?,?,?,?)""", inspections)

        compliance = [
            (1,"Safety","Annual mine safety inspection","2026-09-05","Due Soon"),
            (1,"Environment","Environmental monitoring submission","2026-08-28","Due Soon"),
            (2,"Labour","Contract labour compliance review","2026-09-15","Compliant"),
            (3,"Environment","Air quality monitoring report","2026-09-20","Compliant"),
            (4,"Safety","PPE compliance audit","2026-08-24","Overdue"),
            (5,"Production","Monthly production report","2026-08-31","Due Soon"),
        ]
        cur.executemany("""INSERT INTO compliance
            (mine_id,category,requirement,due_date,status)
            VALUES (?,?,?,?,?)""", compliance)

        contractors = [
            ("Alpha Mining Services",1,62,"HIGH"),
            ("Bharat Coal Logistics",2,84,"MEDIUM"),
            ("Eastern InfraWorks",4,48,"HIGH"),
            ("Odisha Mining Support",3,92,"LOW"),
        ]
        cur.executemany("""INSERT INTO contractors
            (name,mine_id,performance,risk)
            VALUES (?,?,?,?)""", contractors)
    # Seed environmental monitoring data for the prototype.
    # Values are stored separately from the mine master data.
    if cur.execute("SELECT COUNT(*) FROM environmental_data").fetchone()[0] == 0:
        environmental = [
            (1, 42.0, 118.0, 18.0, 31.0, 0.42,
             "2026-08-22 09:00",
             "Prototype demonstration data"),

            (2, 35.0, 92.0, 14.0, 24.0, 0.31,
             "2026-08-22 09:00",
             "Prototype demonstration data"),

            (3, 28.0, 71.0, 10.0, 19.0, 0.24,
             "2026-08-22 09:00",
             "Prototype demonstration data"),

            (4, 51.0, 136.0, 22.0, 38.0, 0.49,
             "2026-08-22 09:00",
             "Prototype demonstration data"),

            (5, 39.0, 104.0, 16.0, 27.0, 0.36,
             "2026-08-22 09:00",
             "Prototype demonstration data"),
        ]

        cur.executemany("""
            INSERT INTO environmental_data
            (mine_id, pm25, pm10, so2, no2, co, recorded_at, source)
            VALUES (?,?,?,?,?,?,?,?)
        """, environmental)
    conn.commit()
    conn.close()
def calculate_risk_score(mine_id, live_environment=None):
    conn = get_db()

    # Get mine compliance
    mine = conn.execute("""
        SELECT compliance, subsidiary, state
        FROM mines
        WHERE id=?
    """, (mine_id,)).fetchone()

    if not mine:
        conn.close()
        return 0

    compliance = mine["compliance"]

    # ---------------------------------
    # 1. COMPLIANCE RISK (0-30)
    # ---------------------------------
    compliance_risk = (100 - compliance) * 0.30

    # ---------------------------------
    # 2. INSPECTION RISK (0-25)
    # ---------------------------------
    inspections = conn.execute("""
        SELECT severity, action_status
        FROM inspections
        WHERE mine_id=?
    """, (mine_id,)).fetchall()

    inspection_risk = 0

    for inspection in inspections:

        if inspection["severity"] == "High":
            inspection_risk += 15

        elif inspection["severity"] == "Medium":
            inspection_risk += 8

        else:
            inspection_risk += 3

        if inspection["action_status"] == "Open":
            inspection_risk += 5

        elif inspection["action_status"] == "Escalated":
            inspection_risk += 8

    inspection_risk = min(inspection_risk, 25)

    # ---------------------------------
    # 3. CONTRACTOR RISK (0-20)
    # ---------------------------------
    contractors = conn.execute("""
        SELECT performance, risk
        FROM contractors
        WHERE mine_id=?
    """, (mine_id,)).fetchall()

    contractor_risk = 0

    for contractor in contractors:

        if contractor["risk"] == "HIGH":
            contractor_risk += 12

        elif contractor["risk"] == "MEDIUM":
            contractor_risk += 6

        if contractor["performance"] < 60:
            contractor_risk += 8

        elif contractor["performance"] < 75:
            contractor_risk += 4

    contractor_risk = min(contractor_risk, 20)

    # ---------------------------------
        # ---------------------------------
        # ---------------------------------
    # 4. ENVIRONMENTAL RISK (0-25)
    # ---------------------------------
    environment = None

    # Prefer LIVE CAAQMS data for SECL
    if live_environment and mine["subsidiary"] == "SECL":
        for record in live_environment:
            if "South Eastern Coalfields" in record.get("company", ""):
                environment = record
                break

    # Fallback to stored environmental data if live data is unavailable
    if environment is None:
        environment = conn.execute("""
            SELECT pm25, pm10, so2, no2
            FROM environmental_data
            WHERE mine_id=?
            ORDER BY recorded_at DESC
            LIMIT 1
        """, (mine_id,)).fetchone()

    environmental_risk = 0

    if environment:

        pm25 = environment.get("pm25") if isinstance(environment, dict) else environment["pm25"]
        pm10 = environment.get("pm10") if isinstance(environment, dict) else environment["pm10"]
        so2 = environment.get("so2") if isinstance(environment, dict) else environment["so2"]
        no2 = environment.get("no2") if isinstance(environment, dict) else environment["no2"]

        if pm25 is not None:
            if pm25 >= 50:
                environmental_risk += 10
            elif pm25 >= 35:
                environmental_risk += 5

        if pm10 is not None:
            if pm10 >= 100:
                environmental_risk += 10
            elif pm10 >= 80:
                environmental_risk += 5

        if so2 is not None and so2 >= 20:
            environmental_risk += 3

        if no2 is not None and no2 >= 35:
            environmental_risk += 3

    environmental_risk = min(environmental_risk, 25)

    # ---------------------------------
    # FINAL GOVERNANCE RISK
    # ---------------------------------
    score = (
        compliance_risk
        + inspection_risk
        + contractor_risk
        + environmental_risk
    )

    conn.close()

    return round(min(score, 100))
@app.route("/")
def dashboard():
    conn = get_db()

    mines = conn.execute(
        "SELECT * FROM mines ORDER BY risk_score DESC"
    ).fetchall()

    # Fetch live environmental data once
    live_environment = fetch_caaqms_data()

        # Match live CAAQMS records with mines in our database
    for record in live_environment:
        record["mine_id"] = None

        for mine in mines:
            if (
                mine["name"].lower() in record["mine_name"].lower()
                or record["mine_name"].lower() in mine["name"].lower()
            ):
                record["mine_id"] = mine["id"]
                break

    # Calculate current governance risk for every mine
    updated_mines = []

    for mine in mines:
        calculated_score = calculate_risk_score(
            mine["id"],
            live_environment
        )
        status = (
            "HIGH" if calculated_score >= 75
            else "MEDIUM" if calculated_score >= 50
            else "LOW"
        )

        updated_mines.append({
            **dict(mine),
            "risk_score": calculated_score,
            "status": status
        })

    mines = sorted(
        updated_mines,
        key=lambda x: x["risk_score"],
        reverse=True
    )

    inspections = conn.execute("""
        SELECT inspections.*, mines.name AS mine_name
        FROM inspections
        JOIN mines ON mines.id = inspections.mine_id
        ORDER BY inspections.id DESC
        LIMIT 8
    """).fetchall()

    contractors = conn.execute("""
        SELECT contractors.*, mines.name AS mine_name
        FROM contractors
        JOIN mines ON mines.id = contractors.mine_id
        ORDER BY contractors.id DESC
    """).fetchall()

    compliance = conn.execute("""
        SELECT compliance.*, mines.name AS mine_name
        FROM compliance
        JOIN mines ON mines.id = compliance.mine_id
        ORDER BY compliance.id DESC
        LIMIT 8
    """).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM mines"
    ).fetchone()[0]

    high = sum(
        1 for mine in mines
        if mine["status"] == "HIGH"
    )

    open_issues = conn.execute(
        "SELECT COUNT(*) FROM inspections WHERE action_status != 'Closed'"
    ).fetchone()[0]

    avg_compliance = round(
        conn.execute(
            "SELECT AVG(compliance) FROM mines"
        ).fetchone()[0]
    )
        # Fetch latest live environmental monitoring data
    live_environment = fetch_caaqms_data()

    conn.close()

    return render_template(
        "dashboard.html",
        mines=mines,
        inspections=inspections,
        compliance=compliance,
        contractors=contractors,
        total=total,
        high=high,
        open_issues=open_issues,
        avg_compliance=avg_compliance,
        live_environment=live_environment
    )
    
@app.route("/mine/<int:mine_id>")
def mine_detail(mine_id):
    conn = get_db()

    mine = conn.execute(
        "SELECT * FROM mines WHERE id=?",
        (mine_id,)
    ).fetchone()

    if not mine:
        conn.close()
        return "Mine not found", 404

    inspections = conn.execute("""
        SELECT * FROM inspections
        WHERE mine_id=?
        ORDER BY id DESC
    """, (mine_id,)).fetchall()

    compliance = conn.execute("""
        SELECT * FROM compliance
        WHERE mine_id=?
        ORDER BY due_date
    """, (mine_id,)).fetchall()

    contractors = conn.execute("""
        SELECT * FROM contractors
        WHERE mine_id=?
    """, (mine_id,)).fetchall()

    environment = conn.execute("""
        SELECT *
        FROM environmental_data
        WHERE mine_id=?
        ORDER BY recorded_at DESC
        LIMIT 1
    """, (mine_id,)).fetchone()

    # Fetch live CAAQMS data once
    live_environment = fetch_caaqms_data()

    # Prefer live CAAQMS data for SECL mines
    if live_environment and mine["subsidiary"] == "SECL":
        for record in live_environment:
            if "South Eastern Coalfields" in record.get("company", ""):
                environment = record
                break

    conn.close()
    # Calculate current risk using live environmental data
    risk_score = calculate_risk_score(
    mine_id,
    live_environment
)

    if risk_score >= 75:
        risk_status = "HIGH"
    elif risk_score >= 50:
        risk_status = "MEDIUM"
    else:
        risk_status = "LOW"

    # ---------------------------------
    # Generate explainable risk factors
    # ---------------------------------

    risk_factors = []

    if mine["compliance"] < 75:
        risk_factors.append(
            f"Low compliance score ({mine['compliance']}%)"
        )

    for inspection in inspections:
        if inspection["severity"] == "High":
            risk_factors.append(
                f"High-severity inspection: {inspection['observation']}"
            )

        if inspection["action_status"] == "Escalated":
            risk_factors.append(
                "Corrective action has been escalated"
            )

        elif inspection["action_status"] == "Open":
            risk_factors.append(
                "High-priority corrective action remains open"
            )

    for contractor in contractors:
        if contractor["risk"] == "HIGH":
            risk_factors.append(
                f"High-risk contractor: {contractor['name']}"
            )

        if contractor["performance"] < 60:
            risk_factors.append(
                f"Low contractor performance ({contractor['performance']}%)"
            )

    if environment:
        pm25 = environment.get("pm25") if isinstance(environment, dict) else environment["pm25"]
        pm10 = environment.get("pm10") if isinstance(environment, dict) else environment["pm10"]
        so2 = environment.get("so2") if isinstance(environment, dict) else environment["so2"]
        no2 = environment.get("no2") if isinstance(environment, dict) else environment["no2"]

        if pm25 is not None and pm25 >= 50:
            risk_factors.append(
                f"Elevated PM2.5 ({pm25} µg/m³)"
            )

        if pm10 is not None and pm10 >= 100:
            risk_factors.append(
                f"Elevated PM10 ({pm10} µg/m³)"
            )

        if so2 is not None and so2 >= 20:
            risk_factors.append(
                f"Elevated SO₂ ({so2} µg/m³)"
            )

        if no2 is not None and no2 >= 35:
            risk_factors.append(
                f"Elevated NO₂ ({no2} µg/m³)"
            )

    # ---------------------------------
    # Recommended action
    # ---------------------------------

    if risk_status == "HIGH":
        recommendation = (
            "Priority management review recommended. "
            "Conduct a targeted safety inspection and close "
            "all escalated corrective actions."
        )

    elif risk_status == "MEDIUM":
        recommendation = (
            "Enhanced monitoring recommended. "
            "Review outstanding compliance requirements "
            "and corrective actions."
        )

    else:
        recommendation = (
            "Continue routine monitoring and scheduled "
            "compliance inspections."
        )

    return render_template(
        "mine.html",
        mine=mine,
        inspections=inspections,
        compliance=compliance,
        contractors=contractors,
        environment=environment,
        risk_score=risk_score,
        risk_status=risk_status,
        risk_factors=risk_factors,
        recommendation=recommendation
    )
@app.route("/inspector")
def inspector():
    if not session.get("logged_in") or session.get("role") != "inspector":
        return redirect(url_for("login"))
    conn = get_db() 

    mines = conn.execute(
        "SELECT * FROM mines ORDER BY name"
    ).fetchall()

    conn.close()

    return render_template(
        "inspector.html",
        mines=mines
    )


@app.route("/inspection/new", methods=["GET", "POST"])
def new_inspection():
    conn = get_db()
    mines = conn.execute("SELECT * FROM mines ORDER BY name").fetchall()
    if request.method == "POST":
        mine_id = request.form["mine_id"]
        category = request.form["category"]
        observation = request.form["observation"]
        severity = request.form["severity"]
        corrective_action = request.form["corrective_action"]
        lat = request.form.get("latitude") or None
        lon = request.form.get("longitude") or None
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute("""INSERT INTO inspections
            (mine_id,category,observation,severity,latitude,longitude,created_at,corrective_action,action_status)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (mine_id,category,observation,severity,lat,lon,created_at,corrective_action,"Pending"))
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))
    conn.close()
    return render_template("inspection.html", mines=mines)
@app.route("/api/caaqms")
def api_caaqms():
    records = fetch_caaqms_data()

    return jsonify({
        "source": "Coal India CAAQMS",
        "live": len(records) > 0,
        "count": len(records),
        "records": records
    })
@app.route("/api/mines")
def api_mines():
    conn = get_db()

    mines = conn.execute(
        "SELECT * FROM mines ORDER BY risk_score DESC"
    ).fetchall()

    conn.close()

    # Fetch live CAAQMS data once
    live_environment = fetch_caaqms_data()

    updated_mines = []

    for mine in mines:
        calculated_score = calculate_risk_score(
            mine["id"],
            live_environment
        )

        status = (
            "HIGH" if calculated_score >= 75
            else "MEDIUM" if calculated_score >= 50
            else "LOW"
        )

        updated_mines.append({
            **dict(mine),
            "risk_score": calculated_score,
            "status": status
        })

    return jsonify(updated_mines)
@app.route("/api/environment")
def api_environment():
    conn = get_db()

    data = conn.execute("""
        SELECT
            environmental_data.*,
            mines.name AS mine_name,
            mines.subsidiary,
            mines.state
        FROM environmental_data
        JOIN mines ON mines.id = environmental_data.mine_id
        ORDER BY environmental_data.recorded_at DESC
    """).fetchall()

    conn.close()

    return jsonify([dict(row) for row in data])
@app.route("/mine-portal")
def mine_portal():
    if not session.get("logged_in") or session.get("role") != "mine":
        return redirect(url_for("login"))
    conn = get_db()

    mines = conn.execute(
        "SELECT * FROM mines ORDER BY risk_score DESC"
    ).fetchall()

    live_environment = fetch_caaqms_data()

    updated_mines = []

    for mine in mines:

        calculated_score = calculate_risk_score(
            mine["id"],
            live_environment
        )

        status = (
            "HIGH"
            if calculated_score >= 75
            else "MEDIUM"
            if calculated_score >= 50
            else "LOW"
        )

        updated_mines.append({
            **dict(mine),
            "risk_score": calculated_score,
            "status": status
        })

    conn.close()

    updated_mines.sort(
        key=lambda x: x["risk_score"],
        reverse=True
    )

    return render_template(
        "mine_portal.html",
        mines=updated_mines
    )
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        users = {
            "admin": {
                "password": "admin123",
                "role": "admin"
            },
            "inspector": {
                "password": "inspect123",
                "role": "inspector"
            },
            "mine": {
                "password": "mine123",
                "role": "mine"
            }
        }

        user = users.get(username)

        if user and user["password"] == password:

            session["logged_in"] = True
            session["username"] = username
            session["role"] = user["role"]

            if user["role"] == "inspector":
                return redirect(url_for("inspector"))

            if user["role"] == "mine":
                return redirect(url_for("mine_portal"))

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid username or password."
        )

    return render_template("login.html")
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("dashboard"))
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
