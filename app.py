from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re
import json
import math

# ============================================================
# MACHINE LEARNING
# ============================================================

try:
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


app = Flask(__name__)
app.secret_key = "smartcoal-demo-secret-key"

DB = "smartcoal.db"

CAAQMS_URL = "https://apps.coalindia.in/ords/f?p=159:11"
CAAQMS_SOURCE = "Coal India CAAQMS"

# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(
        DB,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def add_column_if_missing(conn, table, column, definition):
    columns = {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }

    if column not in columns:
        try:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )
        except Exception as error:
            print(
                f"Migration warning for {table}.{column}:",
                repr(error)
            )


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
        compliance INTEGER NOT NULL DEFAULT 0,
        risk_score INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'LOW'
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
    );

    CREATE TABLE IF NOT EXISTS environmental_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mine_id INTEGER,
        pm25 REAL,
        pm10 REAL,
        so2 REAL,
        no2 REAL,
        co REAL,
        recorded_at TEXT NOT NULL,
        source TEXT NOT NULL,
        company TEXT,
        area TEXT,
        mine_name TEXT,
        device_id TEXT,
        created_by TEXT,
        raw_record TEXT,
        FOREIGN KEY(mine_id) REFERENCES mines(id)
    );

    CREATE TABLE IF NOT EXISTS environmental_anomalies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        environmental_id INTEGER,
        mine_id INTEGER,
        anomaly_score REAL,
        anomaly_level TEXT,
        explanation TEXT,
        detected_at TEXT NOT NULL,
        FOREIGN KEY(environmental_id)
            REFERENCES environmental_data(id),
        FOREIGN KEY(mine_id)
            REFERENCES mines(id)
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mine_id INTEGER,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN',
        created_at TEXT NOT NULL,
        FOREIGN KEY(mine_id) REFERENCES mines(id)
    );

    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mine_id INTEGER NOT NULL,
        incident_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        description TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        occurred_at TEXT NOT NULL,
        reported_at TEXT NOT NULL,
        workers_affected INTEGER DEFAULT 0,
        injured_count INTEGER DEFAULT 0,
        missing_count INTEGER DEFAULT 0,
        fatality_count INTEGER DEFAULT 0,
        emergency_status TEXT NOT NULL DEFAULT 'ACTIVE',
        evacuation_status TEXT NOT NULL DEFAULT 'NOT_STARTED',
        rescue_status TEXT NOT NULL DEFAULT 'NOT_REQUIRED',
        investigation_status TEXT NOT NULL DEFAULT 'PENDING',
        root_cause TEXT,
        corrective_action TEXT,
        closure_status TEXT NOT NULL DEFAULT 'OPEN',
        closed_at TEXT,
        reported_by TEXT,
        FOREIGN KEY(mine_id) REFERENCES mines(id)
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        action TEXT NOT NULL,
        entity_type TEXT,
        entity_id INTEGER,
        details TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS system_status (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        environment_status TEXT,
        environment_source TEXT,
        last_successful_refresh TEXT,
        last_refresh_attempt TEXT,
        records_received INTEGER DEFAULT 0,
        message TEXT
    );
    """)

    # ========================================================
    # SAFE MIGRATIONS
    # ========================================================

    migrations = {

        "mines": {
            "risk_score": "INTEGER DEFAULT 0",
            "status": "TEXT DEFAULT 'LOW'"
        },

        "environmental_data": {
            "company": "TEXT",
            "area": "TEXT",
            "mine_name": "TEXT",
            "device_id": "TEXT",
            "created_by": "TEXT",
            "raw_record": "TEXT",
            "mine_id": "INTEGER"
        },

        "inspections": {
            "corrective_action": "TEXT",
            "action_status": "TEXT DEFAULT 'Pending'",
            "latitude": "REAL",
            "longitude": "REAL"
        },

        "incidents": {
            "root_cause": "TEXT",
            "corrective_action": "TEXT",
            "closed_at": "TEXT",
            "reported_by": "TEXT"
        }
    }

    for table, columns in migrations.items():

        for column, definition in columns.items():

            add_column_if_missing(
                conn,
                table,
                column,
                definition
            )

    # ========================================================
    # SEED DATA
    # ========================================================

    if cur.execute(
        "SELECT COUNT(*) FROM mines"
    ).fetchone()[0] == 0:

        mines = [

            (
                "Dhanbad Central Mine",
                "BCCL",
                "Jharkhand",
                23.7957,
                86.4304,
                74,
                0,
                "LOW"
            ),

            (
                "Korba East Mine",
                "SECL",
                "Chhattisgarh",
                22.3595,
                82.7501,
                88,
                0,
                "LOW"
            ),

            (
                "Talcher North Mine",
                "MCL",
                "Odisha",
                20.9517,
                85.2167,
                93,
                0,
                "LOW"
            ),

            (
                "Raniganj West Mine",
                "ECL",
                "West Bengal",
                23.6160,
                87.1300,
                68,
                0,
                "LOW"
            ),

            (
                "Singrauli Open Cast",
                "NCL",
                "Madhya Pradesh",
                24.1990,
                82.6750,
                81,
                0,
                "LOW"
            )
        ]

        cur.executemany("""
            INSERT INTO mines
            (
                name,
                subsidiary,
                state,
                lat,
                lon,
                compliance,
                risk_score,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, mines)

        inspections = [

            (
                1,
                "Safety",
                "Damaged safety barrier near haul road",
                "High",
                23.7957,
                86.4304,
                "2026-08-22 09:15",
                "Repair barrier and verify",
                "Open"
            ),

            (
                1,
                "Environment",
                "Dust level above internal threshold",
                "Medium",
                23.7965,
                86.4310,
                "2026-08-21 14:20",
                "Inspect water-sprinkling system",
                "Pending"
            ),

            (
                2,
                "Labour",
                "Attendance mismatch in contractor records",
                "Medium",
                22.3595,
                82.7501,
                "2026-08-20 11:05",
                "Reconcile attendance data",
                "Pending"
            ),

            (
                4,
                "Safety",
                "Repeated PPE non-compliance",
                "High",
                23.6160,
                87.1300,
                "2026-08-22 10:30",
                "Conduct contractor safety briefing",
                "Escalated"
            )
        ]

        cur.executemany("""
            INSERT INTO inspections
            (
                mine_id,
                category,
                observation,
                severity,
                latitude,
                longitude,
                created_at,
                corrective_action,
                action_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, inspections)

        compliance = [

            (
                1,
                "Safety",
                "Annual mine safety inspection",
                "2026-09-05",
                "Due Soon"
            ),

            (
                1,
                "Environment",
                "Environmental monitoring submission",
                "2026-08-28",
                "Overdue"
            ),

            (
                2,
                "Labour",
                "Contract labour compliance review",
                "2026-09-15",
                "Compliant"
            ),

            (
                3,
                "Environment",
                "Air quality monitoring report",
                "2026-09-20",
                "Compliant"
            ),

            (
                4,
                "Safety",
                "PPE compliance audit",
                "2026-08-24",
                "Overdue"
            ),

            (
                5,
                "Production",
                "Monthly production report",
                "2026-08-31",
                "Due Soon"
            )
        ]

        cur.executemany("""
            INSERT INTO compliance
            (
                mine_id,
                category,
                requirement,
                due_date,
                status
            )
            VALUES (?, ?, ?, ?, ?)
        """, compliance)

        contractors = [

            (
                "Alpha Mining Services",
                1,
                62,
                "HIGH"
            ),

            (
                "Bharat Coal Logistics",
                2,
                84,
                "MEDIUM"
            ),

            (
                "Eastern InfraWorks",
                4,
                48,
                "HIGH"
            ),

            (
                "Odisha Mining Support",
                3,
                92,
                "LOW"
            )
        ]

        cur.executemany("""
            INSERT INTO contractors
            (
                name,
                mine_id,
                performance,
                risk
            )
            VALUES (?, ?, ?, ?)
        """, contractors)

        # ----------------------------------------------------
        # Demonstration environmental records.
        # These are clearly labelled as prototype/cache data
        # until official CAAQMS readings are successfully
        # matched.
        # ----------------------------------------------------

        demo_environment = [

            (
                1,
                32,
                82,
                24,
                38,
                1.8,
                "2026-08-30 10:00:00",
                "Prototype demonstration data"
            ),

            (
                2,
                28,
                74,
                18,
                32,
                1.5,
                "2026-08-30 10:15:00",
                "Prototype demonstration data"
            ),

            (
                3,
                22,
                61,
                14,
                26,
                1.1,
                "2026-08-30 10:30:00",
                "Prototype demonstration data"
            ),

            (
                4,
                51,
                136,
                32,
                58,
                3.4,
                "2026-08-30 10:45:00",
                "Prototype demonstration data"
            ),

            (
                5,
                30,
                91,
                20,
                41,
                2.0,
                "2026-08-30 11:00:00",
                "Prototype demonstration data"
            )
        ]

        cur.executemany("""
            INSERT INTO environmental_data
            (
                mine_id,
                pm25,
                pm10,
                so2,
                no2,
                co,
                recorded_at,
                source,
                company,
                area,
                mine_name,
                device_id,
                created_by,
                raw_record
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [

            (
                mine_id,
                pm25,
                pm10,
                so2,
                no2,
                co,
                recorded_at,
                source,
                "",
                "",
                "",
                "",
                "SmartCoal",
                json.dumps({
                    "type": "demo"
                })
            )

            for (
                mine_id,
                pm25,
                pm10,
                so2,
                no2,
                co,
                recorded_at,
                source
            )
            in demo_environment
        ])

    conn.execute("""
        INSERT OR IGNORE INTO system_status
        (
            id,
            environment_status,
            environment_source,
            last_successful_refresh,
            last_refresh_attempt,
            records_received,
            message
        )
        VALUES
        (
            1,
            'INITIAL',
            'Prototype fallback',
            NULL,
            NULL,
            0,
            'System initialized'
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def number(value):

    if value is None:
        return None

    value = clean_text(value)

    if value.upper() in (
        "",
        "-",
        "NA",
        "N/A",
        "NULL",
        "--"
    ):
        return None

    try:
        return float(
            value.replace(",", "")
        )

    except (
        ValueError,
        TypeError
    ):
        return None


def parse_caaqms_date(value):

    if not value:
        return None

    value = clean_text(value)

    formats = [

        "%d-%b-%Y %H:%M",

        "%d-%b-%Y %H:%M:%S",

        "%d-%m-%Y %H:%M",

        "%d-%m-%Y %H:%M:%S",

        "%d/%m/%Y %H:%M",

        "%d/%m/%Y %H:%M:%S",

        "%Y-%m-%d %H:%M",

        "%Y-%m-%d %H:%M:%S"
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                value.upper(),
                fmt
            ).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        except ValueError:
            continue

    return value


def normalize_name(value):

    if not value:
        return ""

    value = value.lower()

    replacements = [

        "limited",
        "ltd",
        "m/s",
        "mine",
        "coalfields",
        "coal fields",
        "opencast",
        "open cast",
        "project"
    ]

    for word in replacements:

        value = value.replace(
            word,
            " "
        )

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )

    return " ".join(
        value.split()
    )


def safe_int(value, default=0):

    try:
        return int(value)
    except (
        ValueError,
        TypeError
    ):
        return default


def safe_float(value):

    try:
        return float(value)
    except (
        ValueError,
        TypeError
    ):
        return None


# ============================================================
# AUDIT
# ============================================================

def audit(
    action,
    entity_type=None,
    entity_id=None,
    details=None
):

    conn = get_db()

    conn.execute("""
        INSERT INTO audit_log
        (
            username,
            action,
            entity_type,
            entity_id,
            details,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (

        session.get(
            "username",
            "system"
        ),

        action,

        entity_type,

        entity_id,

        details,

        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()


# ============================================================
# SYSTEM STATUS
# ============================================================

def update_system_status(
    status,
    source,
    successful_time=None,
    records_received=0,
    message=""
):

    conn = get_db()

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    if successful_time is None:

        row = conn.execute("""
            SELECT last_successful_refresh
            FROM system_status
            WHERE id=1
        """).fetchone()

        successful_time = (
            row["last_successful_refresh"]
            if row
            else None
        )

    conn.execute("""
        UPDATE system_status
        SET
            environment_status=?,
            environment_source=?,
            last_successful_refresh=?,
            last_refresh_attempt=?,
            records_received=?,
            message=?
        WHERE id=1
    """, (

        status,
        source,
        successful_time,
        now,
        records_received,
        message
    ))

    conn.commit()
    conn.close()


def get_system_status():

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM system_status
        WHERE id=1
    """).fetchone()

    conn.close()

    return dict(row) if row else {}


# ============================================================
# CAAQMS LIVE DATA
# ============================================================

# ============================================================
# CAAQMS LIVE DATA
# ============================================================
def fetch_caaqms_data():
    """
    Fetch environmental data from Coal India's official CAAQMS page.

    The CAAQMS page can change its HTML structure, so this parser:
    1. Reads the official APEX table when available.
    2. Searches the complete page text for environmental values.
    3. Keeps records even when some pollutant fields are unavailable.
    4. Uses robust mine/company matching.
    """

    try:
        response = requests.get(
            CAAQMS_URL,
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/153.0 Safari/537.36"
                )
            },
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        records = []
        seen = set()

        # ============================================================
        # HELPERS
        # ============================================================

        def clean(value):
            if value is None:
                return ""

            return " ".join(
                str(value)
                .replace("\xa0", " ")
                .replace("\r", " ")
                .replace("\t", " ")
                .split()
            ).strip()

        def to_float(value):
            value = clean(value)

            if not value:
                return None

            value = value.replace(",", "")

            if value in (
                "-",
                "—",
                "–",
                "#####",
                "null",
                "None",
                "N/A",
                "NA",
            ):
                return None

            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def normalize_datetime(value):
            value = clean(value)

            if not value:
                return None

            formats = [
                "%d-%b-%Y %H:%M:%S",
                "%d-%b-%Y %H:%M",
                "%d-%b-%y %H:%M:%S",
                "%d-%b-%y %H:%M",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(
                        value,
                        fmt
                    ).strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

            return value

        def add_record(record, source="Coal India CAAQMS"):

            mine_name = clean(
                record.get("mine_name")
            )

            company = clean(
                record.get("company")
            )

            if not mine_name:
                return False

            pm25 = record.get("pm25")
            pm10 = record.get("pm10")
            so2 = record.get("so2")
            no2 = record.get("no2")
            co = record.get("co")

            # At least one environmental reading is required.
            if not any(
                value is not None
                for value in [
                    pm25,
                    pm10,
                    so2,
                    no2,
                    co,
                ]
            ):
                return False

            recorded_at = normalize_datetime(
                record.get("recorded_at")
            )

            if not recorded_at:
                recorded_at = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

            final_record = {
                "company": company,
                "area": clean(
                    record.get("area")
                ),
                "mine_name": mine_name,
                "recorded_at": recorded_at,
                "pm25": pm25,
                "pm10": pm10,
                "so2": so2,
                "no2": no2,
                "co": co,
                "device_id": clean(
                    record.get("device_id")
                ),
                "created_by": clean(
                    record.get("created_by")
                ),
                "source": source,
            }

            key = (
                final_record["company"],
                final_record["area"],
                final_record["mine_name"],
                final_record["recorded_at"],
                final_record["device_id"],
                final_record["pm25"],
                final_record["pm10"],
                final_record["so2"],
                final_record["no2"],
                final_record["co"],
            )

            if key in seen:
                return False

            seen.add(key)

            final_record["raw_record"] = str(
                final_record
            )

            records.append(final_record)

            return True

        # ============================================================
        # COMPANY NAMES
        # ============================================================

        company_names = [
            "Northern Coalfields Limited",
            "Western Coalfields Limited",
            "Mahanadi Coalfields Limited",
            "South Eastern Coalfields Limited",
            "South Eastern Coalfields",
            "Eastern Coalfields Limited",
            "Central Coalfields Limited",
            "Bharat Coking Coal Limited",
            "Central Mine Planning and Design Institute Limited",
        ]

        # ============================================================
        # PART 1 — NORMAL APEX TABLE
        # ============================================================

        table = soup.find(
            "table",
            class_="a-IRR-table"
        )

        if table is None:

            for candidate in soup.find_all("table"):

                text = candidate.get_text(
                    " ",
                    strip=True
                )

                text_lower = text.lower()

                if (
                    "company name" in text_lower
                    and "pm - 2.5" in text_lower
                    and "pm - 10" in text_lower
                ):
                    table = candidate
                    break

        table_records = 0

        if table is not None:

            header_row = None
            headers = []

            for row in table.find_all("tr"):

                cells = row.find_all(
                    ["th", "td"]
                )

                candidate = [
                    clean(
                        cell.get_text(
                            " ",
                            strip=True
                        )
                    )
                    for cell in cells
                ]

                joined = " ".join(
                    candidate
                ).lower()

                if (
                    "company name" in joined
                    and (
                        "pm - 2.5" in joined
                        or "pm - 10" in joined
                    )
                ):
                    header_row = row
                    headers = candidate
                    break

            if header_row is not None:

                started = False

                for row in table.find_all("tr"):

                    if row == header_row:
                        started = True
                        continue

                    if not started:
                        continue

                    cells = row.find_all(
                        ["td", "th"]
                    )

                    if len(cells) != len(headers):
                        continue

                    values = [
                        clean(
                            cell.get_text(
                                " ",
                                strip=True
                            )
                        )
                        for cell in cells
                    ]

                    raw = dict(
                        zip(headers, values)
                    )

                    def get_column(*names):

                        # Exact match first.
                        for name in names:
                            if name in raw:
                                return raw[name]

                        # Normalized match.
                        normalized_raw = {
                            clean(k).lower(): v
                            for k, v in raw.items()
                        }

                        for name in names:
                            normalized_name = clean(
                                name
                            ).lower()

                            if (
                                normalized_name
                                in normalized_raw
                            ):
                                return normalized_raw[
                                    normalized_name
                                ]

                        # Partial header match.
                        for key, value in raw.items():

                            key_lower = clean(
                                key
                            ).lower()

                            for name in names:

                                name_lower = clean(
                                    name
                                ).lower()

                                if (
                                    name_lower
                                    in key_lower
                                ):
                                    return value

                        return ""

                    success = add_record(
                        {
                            "company": get_column(
                                "Company Name"
                            ),

                            "area": get_column(
                                "Area Name"
                            ),

                            "mine_name": get_column(
                                "Mine Name"
                            ),

                            "recorded_at": (
                                get_column(
                                    "Record time"
                                )
                                or get_column(
                                    "Creation datetime"
                                )
                            ),

                            "pm25": to_float(
                                get_column(
                                    "PM - 2.5 (µg/m3)",
                                    "PM - 2.5",
                                    "PM 2.5",
                                    "PM2.5"
                                )
                            ),

                            "pm10": to_float(
                                get_column(
                                    "PM - 10 (µg/m3)",
                                    "PM - 10",
                                    "PM 10",
                                    "PM10"
                                )
                            ),

                            "so2": to_float(
                                get_column(
                                    "SO2 (µg/m3)",
                                    "SO2"
                                )
                            ),

                            "no2": to_float(
                                get_column(
                                    "NO2 (µg/m3)",
                                    "NO2"
                                )
                            ),

                            "co": to_float(
                                get_column(
                                    "CO (mg/m3)",
                                    "CO"
                                )
                            ),

                            "device_id": get_column(
                                "Device ID"
                            ),

                            "created_by": get_column(
                                "Created by"
                            ),
                        }
                    )

                    if success:
                        table_records += 1

        print(
            f"CAAQMS: Table records accepted: "
            f"{table_records}"
        )

        # ============================================================
        # PART 2 — GENERIC TEXT-BASED FALLBACK
        # ============================================================

        page_lines = [
            clean(text)
            for text in soup.stripped_strings
        ]

        page_lines = [
            line
            for line in page_lines
            if line
        ]

        # ------------------------------------------------------------
        # Build a mine-name list from lines containing known
        # subsidiary/mine identifiers.
        # ------------------------------------------------------------

        mine_keywords = [
            "BHATADI",
            "PENGANGA",
            "SAONER",
            "KUSMUNDA",
            "GEVRA",
            "DIPKA",
            "AMADAND",
            "NCL_CETI",
            "SECL_",
            "MINE",
            "PROJECT",
            "AQMS",
        ]

        possible_mines = []

        for line in page_lines:

            upper = line.upper()

            if any(
                keyword in upper
                for keyword in mine_keywords
            ):

                if len(line) <= 180:
                    possible_mines.append(line)

        # ------------------------------------------------------------
        # Search lines for environmental labels followed by numbers.
        # ------------------------------------------------------------

        def extract_value_near(
            lines,
            index,
            labels,
            look_ahead=4
        ):

            for offset in range(
                1,
                look_ahead + 1
            ):

                position = index + offset

                if position >= len(lines):
                    break

                candidate = lines[position]

                # Avoid grabbing a timestamp or unrelated text.
                if re.search(
                    r"\d{2}[-/][A-Za-z0-9]{2,3}"
                    r"[-/]\d{2,4}",
                    candidate
                ):
                    continue

                match = re.search(
                    r"(-?\d+(?:\.\d+)?)",
                    candidate.replace(",", "")
                )

                if match:
                    return to_float(
                        match.group(1)
                    )

            return None

        environmental_blocks = []

        for index, line in enumerate(page_lines):

            upper = line.upper()

            if (
                "PM - 2.5" in upper
                or "PM2.5" in upper
                or "PM 2.5" in upper
            ):

                pm25 = extract_value_near(
                    page_lines,
                    index,
                    ["PM"],
                    5
                )

                pm10 = None
                so2 = None
                no2 = None
                co = None

                for k in range(
                    index + 1,
                    min(
                        index + 15,
                        len(page_lines)
                    )
                ):

                    text_upper = page_lines[k].upper()

                    if (
                        "PM - 10" in text_upper
                        or "PM10" in text_upper
                        or "PM 10" in text_upper
                    ):
                        pm10 = extract_value_near(
                            page_lines,
                            k,
                            ["PM"],
                            4
                        )

                    elif text_upper == "SO2":
                        so2 = extract_value_near(
                            page_lines,
                            k,
                            ["SO2"],
                            4
                        )

                    elif text_upper == "NO2":
                        no2 = extract_value_near(
                            page_lines,
                            k,
                            ["NO2"],
                            4
                        )

                    elif text_upper == "CO":
                        co = extract_value_near(
                            page_lines,
                            k,
                            ["CO"],
                            4
                        )

                environmental_blocks.append(
                    {
                        "index": index,
                        "pm25": pm25,
                        "pm10": pm10,
                        "so2": so2,
                        "no2": no2,
                        "co": co,
                    }
                )

        # ------------------------------------------------------------
        # Associate environmental blocks with the nearest useful
        # mine/company name.
        # ------------------------------------------------------------

        text_fallback_records = 0

        for block in environmental_blocks:

            if not any(
                value is not None
                for value in [
                    block["pm25"],
                    block["pm10"],
                    block["so2"],
                    block["no2"],
                    block["co"],
                ]
            ):
                continue

            block_index = block["index"]

            nearest_mine = ""

            # Search backwards for a likely mine name.
            for k in range(
                block_index - 1,
                max(-1, block_index - 30),
                -1
            ):

                candidate = page_lines[k]
                upper = candidate.upper()

                if any(
                    keyword in upper
                    for keyword in mine_keywords
                ):

                    if (
                        "PM" not in upper
                        and "SO2" not in upper
                        and "NO2" not in upper
                        and upper != "CO"
                    ):
                        nearest_mine = candidate
                        break

            if not nearest_mine:

                if possible_mines:
                    nearest_mine = possible_mines[
                        min(
                            range(
                                len(possible_mines)
                            ),
                            key=lambda x: abs(
                                page_lines.index(
                                    possible_mines[x]
                                )
                                - block_index
                            )
                        )
                    ]

            if not nearest_mine:
                continue

            company = ""

            nearest_position = page_lines.index(
                nearest_mine
            )

            for k in range(
                nearest_position - 20,
                min(
                    nearest_position + 1,
                    len(page_lines)
                )
            ):

                if k < 0:
                    continue

                candidate = page_lines[k]

                for company_name in company_names:

                    if (
                        company_name.lower()
                        in candidate.lower()
                    ):
                        company = company_name
                        break

                if company:
                    break

            success = add_record(
                {
                    "company": company,
                    "area": "",
                    "mine_name": nearest_mine,
                    "recorded_at": "",
                    "pm25": block["pm25"],
                    "pm10": block["pm10"],
                    "so2": block["so2"],
                    "no2": block["no2"],
                    "co": block["co"],
                    "device_id": "",
                    "created_by": "",
                }
            )

            if success:
                text_fallback_records += 1

        # ============================================================
        # DIAGNOSTICS
        # ============================================================

        unique_mines = sorted(
            {
                clean(
                    record.get("mine_name")
                )
                for record in records
                if clean(
                    record.get("mine_name")
                )
            }
        )

        print(
            f"CAAQMS: Parsed {len(records)} records."
        )

        print(
            f"CAAQMS: Table records accepted: "
            f"{table_records}"
        )

        print(
            f"CAAQMS: Text fallback records: "
            f"{text_fallback_records}"
        )

        print(
            f"CAAQMS: Live records found: "
            f"{table_records + text_fallback_records}"
        )

        print(
            f"CAAQMS: Found {len(unique_mines)} "
            f"mine names."
        )

        print(
            "CAAQMS sample mines:",
            unique_mines[:30]
        )

        target_keywords = [
            "Bhatadi",
            "Penganga",
            "Saoner",
            "Kusmunda",
            "Gevra",
            "Amadand",
            "Dipka",
            "NCL_CETI",
        ]

        found_targets = []

        for keyword in target_keywords:

            for mine_name in unique_mines:

                if (
                    keyword.lower()
                    in mine_name.lower()
                ):
                    found_targets.append(
                        mine_name
                    )
                    break

        print(
            "CAAQMS target mines found:",
            found_targets
        )

        return records

    except Exception as e:

        print(
            "CAAQMS fetch error:",
            repr(e)
        )

        return []
# ============================================================
# MINE MATCHING
# ============================================================

# ============================================================
# MINE MATCHING
# ============================================================

def match_environment_to_mine(record, mines):

    def clean(value):
        if value is None:
            return ""

        return (
            str(value)
            .strip()
            .lower()
            .replace("_", " ")
            .replace("-", " ")
            .replace(",", " ")
            .replace(".", " ")
            .replace("/", " ")
        )

    record_name = clean(
        record.get("mine_name")
    )

    record_area = clean(
        record.get("area")
    )

    company = clean(
        record.get("company")
    )

    combined = (
        f"{record_name} "
        f"{record_area} "
        f"{company}"
    )

    # ============================================================
    # COAL INDIA SUBSIDIARY DETECTION
    # ============================================================

    subsidiary_aliases = {

        "BCCL": [
            "bharat coking coal",
            "bharat coking coal limited",
            "bccl"
        ],

        "SECL": [
            "south eastern coalfields",
            "south eastern coalfields limited",
            "south eastern coal fields",
            "south eastern coal fields limited",
            "secl"
        ],

        "MCL": [
            "mahanadi coalfields",
            "mahanadi coalfields limited",
            "mcl"
        ],

        "ECL": [
            "eastern coalfields",
            "eastern coalfields limited",
            "ecl"
        ],

        "NCL": [
            "northern coalfields",
            "northern coalfields limited",
            "ncl"
        ],

        "WCL": [
            "western coalfields",
            "western coalfields limited",
            "wcl"
        ]
    }

    record_subsidiary = None

    for subsidiary, aliases in subsidiary_aliases.items():

        for alias in aliases:

            if alias in combined:
                record_subsidiary = subsidiary
                break

        if record_subsidiary:
            break

    # ============================================================
    # KNOWN CAAQMS → DATABASE MINE MAPPINGS
    #
    # These are intentionally based on distinctive mine names.
    # They do NOT use generic words such as "mine", "project",
    # "area", "coal", etc.
    # ============================================================

    mine_aliases = {

        # ---------------- SECL ----------------

        "kusmunda": [
            "kusmunda",
            "secl kusmunda"
        ],

        "gevra": [
            "gevra",
            "secl gevra",
            "gevra opencast",
            "gevra oc"
        ],

        "dipka": [
            "dipka",
            "secl dipka",
            "dipka expansion",
            "dipka expansion project"
        ],

        # ---------------- WCL ----------------

        "bhatadi": [
            "bhatadi"
        ],

        "penganga": [
            "penganga"
        ],

        "saoner": [
            "saoner"
        ],

        "mungoli": [
            "mungoli"
        ],

        "majri": [
            "majri"
        ],

        "makardhokra": [
            "makardhokra"
        ],

        # ---------------- MCL ----------------

        "lakhanpur": [
            "lakhanpur"
        ],

        "basundhara": [
            "basundhara",
            "basundhara west"
        ],

        "bhubaneswari": [
            "bhubaneswari",
            "bhubaneswari coal"
        ],

        "samaleswari": [
            "samaleswari"
        ],

        "lajkura": [
            "lajkura"
        ],

        # ---------------- NCL ----------------

        "jayant": [
            "jayant"
        ],

        "nigahi": [
            "nigahi"
        ],

        "dudhichua": [
            "dudhichua"
        ],

        "bina": [
            "bina"
        ],

        "ncl ceti": [
            "ncl ceti"
        ],

        # ---------------- OTHER ----------------

        "amadand": [
            "amadand"
        ]
    }

    # ============================================================
    # FIRST — EXACT DATABASE NAME MATCH
    # ============================================================

    for mine in mines:

        mine_name = clean(
            mine["name"]
        )

        if not mine_name:
            continue

        if (
            mine_name == record_name
            or mine_name in combined
            or record_name in mine_name
        ):

            mine_subsidiary = str(
                mine["subsidiary"] or ""
            ).upper()

            if (
                record_subsidiary
                and mine_subsidiary
                and record_subsidiary
                != mine_subsidiary
            ):
                continue

            return mine["id"]

    # ============================================================
    # SECOND — KNOWN MINE ALIAS MATCH
    # ============================================================

    matched_target = None

    for target, aliases in mine_aliases.items():

        for alias in aliases:

            alias_clean = clean(alias)

            if (
                alias_clean
                and alias_clean in combined
            ):
                matched_target = target
                break

        if matched_target:
            break

    if matched_target:

        # Search database for the target mine.
        for mine in mines:

            mine_name = clean(
                mine["name"]
            )

            mine_subsidiary = str(
                mine["subsidiary"] or ""
            ).upper()

            # Never cross subsidiaries when both sides
            # identify one.
            if (
                record_subsidiary
                and mine_subsidiary
                and record_subsidiary
                != mine_subsidiary
            ):
                continue

            # The target must be a distinctive part
            # of the database mine name.
            if matched_target in mine_name:

                return mine["id"]

    # ============================================================
    # THIRD — DISTINCTIVE WORD MATCH
    # ============================================================

    generic_words = {
        "coal",
        "mine",
        "mines",
        "project",
        "projects",
        "opencast",
        "open",
        "cast",
        "oc",
        "ugc",
        "ug",
        "underground",
        "area",
        "expansion",
        "limited",
        "ltd",
        "south",
        "eastern",
        "western",
        "northern",
        "central",
        "mahanadi",
        "bharat",
        "coking",
        "fields",
        "field",
        "coalfields",
        "coalfield",
        "m",
        "s",
        "ms"
    }

    record_words = {
        word
        for word in record_name.split()
        if len(word) >= 5
        and word not in generic_words
    }

    # Also include area words because some CAAQMS records
    # put the mine/project name in the area field.
    area_words = {
        word
        for word in record_area.split()
        if len(word) >= 5
        and word not in generic_words
    }

    record_words.update(area_words)

    if record_words:

        for mine in mines:

            mine_name = clean(
                mine["name"]
            )

            mine_subsidiary = str(
                mine["subsidiary"] or ""
            ).upper()

            if (
                record_subsidiary
                and mine_subsidiary
                and record_subsidiary
                != mine_subsidiary
            ):
                continue

            mine_words = {
                word
                for word in mine_name.split()
                if len(word) >= 5
                and word not in generic_words
            }

            # Only accept a distinctive word match.
            common_words = (
                mine_words
                & record_words
            )

            if common_words:

                # Avoid weak matches such as a single
                # subsidiary/location word.
                strong_words = {
                    word
                    for word in common_words
                    if word not in {
                        "central",
                        "eastern",
                        "western",
                        "northern",
                        "south",
                        "fields",
                        "coalfields"
                    }
                }

                if strong_words:
                    return mine["id"]

    # ============================================================
    # NO SAFE MATCH
    #
    # Never randomly assign a CAAQMS reading.
    # ============================================================

    return None

# ============================================================
# ENVIRONMENTAL ANOMALY ML
# ============================================================

def environment_features(row):

    return [

        float(row["pm25"] or 0),

        float(row["pm10"] or 0),

        float(row["so2"] or 0),

        float(row["no2"] or 0),

        float(row["co"] or 0)
    ]


def detect_environmental_anomaly(
    environmental_id
):

    if not ML_AVAILABLE:
        return None

    conn = get_db()

    current = conn.execute("""
        SELECT *
        FROM environmental_data
        WHERE id=?
    """, (
        environmental_id,
    )).fetchone()

    if not current:

        conn.close()

        return None

    history = conn.execute("""
        SELECT *
        FROM environmental_data
        WHERE id != ?
          AND mine_id = ?
          AND pm25 IS NOT NULL
          AND pm10 IS NOT NULL
        ORDER BY recorded_at DESC
        LIMIT 500
    """, (
        environmental_id,
        current["mine_id"]
    )).fetchall()

    if len(history) < 10:

        conn.close()

        return None

    try:

        X = [
            environment_features(row)
            for row in history
        ]

        current_features = [
            environment_features(current)
        ]

        model = IsolationForest(
            n_estimators=150,
            contamination="auto",
            random_state=42
        )

        model.fit(X)

        prediction = model.predict(
            current_features
        )[0]

        raw_score = model.decision_function(
            current_features
        )[0]

        anomaly_score = round(
            max(
                0,
                min(
                    100,
                    (0.5 - raw_score) * 100
                )
            ),
            2
        )

        if prediction == -1:

            if anomaly_score >= 70:
                level = "HIGH"

            elif anomaly_score >= 50:
                level = "MEDIUM"

            else:
                level = "LOW"

        else:

            level = "NORMAL"

            anomaly_score = min(
                anomaly_score,
                49.0
            )

        explanation_parts = []

        parameter_map = {

            "PM2.5": "pm25",

            "PM10": "pm10",

            "SO₂": "so2",

            "NO₂": "no2",

            "CO": "co"
        }

        for parameter, column in parameter_map.items():

            value = current[column]

            if value is None:
                continue

            historical_values = [

                float(row[column])

                for row in history

                if row[column] is not None
            ]

            if len(historical_values) < 5:
                continue

            average = (
                sum(historical_values)
                /
                len(historical_values)
            )

            if average <= 0:
                continue

            deviation = (
                abs(value - average)
                /
                average
            )

            if deviation >= 1.0:

                explanation_parts.append(
                    f"{parameter} is significantly "
                    f"different from historical "
                    f"monitoring patterns."
                )

            elif deviation >= 0.5:

                explanation_parts.append(
                    f"{parameter} differs noticeably "
                    f"from historical patterns."
                )

        if not explanation_parts:

            if level == "NORMAL":

                explanation = (
                    "Environmental pattern is "
                    "consistent with available "
                    "historical observations."
                )

            else:

                explanation = (
                    "The combined environmental "
                    "pattern is unusual compared "
                    "with historical observations."
                )

        else:

            explanation = " ".join(
                explanation_parts[:3]
            )

        conn.execute("""
            INSERT INTO environmental_anomalies
            (
                environmental_id,
                mine_id,
                anomaly_score,
                anomaly_level,
                explanation,
                detected_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (

            environmental_id,

            current["mine_id"],

            anomaly_score,

            level,

            explanation,

            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ))

        conn.commit()

        return {

            "score":
                anomaly_score,

            "level":
                level,

            "explanation":
                explanation
        }

    except Exception as error:

        print(
            "ML ANOMALY ERROR:",
            repr(error)
        )

        return None

    finally:

        conn.close()


# ============================================================
# CACHE CAAQMS DATA
# ============================================================

def cache_caaqms_records(records):

    if not records:
        return 0

    conn = get_db()

    inserted = 0

    try:

        mines = conn.execute("""
            SELECT *
            FROM mines
            ORDER BY id
        """).fetchall()

        for record in records:

            mine_id = match_environment_to_mine(
                record,
                mines
            )

            if mine_id is None:
                continue

            recorded_at = (

                record.get("recorded_at")

                or record.get("record_time")

                or record.get("created_at")

                or datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            device_id = (
                record.get("device_id")
                or ""
            )

            mine_name = (
                record.get("mine_name")
                or ""
            )

            existing = conn.execute("""
                SELECT id
                FROM environmental_data
                WHERE mine_id=?
                  AND device_id=?
                  AND recorded_at=?
                LIMIT 1
            """, (

                mine_id,

                device_id,

                recorded_at
            )).fetchone()

            if existing:
                continue

            cursor = conn.execute("""
                INSERT INTO environmental_data
                (
                    mine_id,
                    pm25,
                    pm10,
                    so2,
                    no2,
                    co,
                    recorded_at,
                    source,
                    company,
                    area,
                    mine_name,
                    device_id,
                    created_by,
                    raw_record
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (

                mine_id,

                record.get("pm25"),

                record.get("pm10"),

                record.get("so2"),

                record.get("no2"),

                record.get("co"),

                recorded_at,

                record.get(
                    "source",
                    CAAQMS_SOURCE
                ),

                record.get("company"),

                record.get("area"),

                mine_name,

                device_id,

                record.get(
                    "created_by",
                    "CAAQMS"
                ),

                json.dumps(
                    record,
                    default=str
                )
            ))

            environmental_id = cursor.lastrowid

            inserted += 1

            # ML is attempted when enough historical data exists.
            detect_environmental_anomaly(
                environmental_id
            )

        conn.commit()

    except Exception as error:

        conn.rollback()

        print(
            "CAAQMS CACHE ERROR:",
            repr(error)
        )

    finally:

        conn.close()

    return inserted


# ============================================================
# ENVIRONMENT DATA WITH CACHE FALLBACK
# ============================================================

def get_environment_data():

    live_records = fetch_caaqms_data()

    if live_records:

        inserted = cache_caaqms_records(
            live_records
        )

        now = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        update_system_status(
            "LIVE",
            CAAQMS_SOURCE,
            successful_time=now,
            records_received=len(
                live_records
            ),
            message=(
                f"CAAQMS refresh successful. "
                f"{len(live_records)} records received; "
                f"{inserted} new records cached."
            )
        )

        # Use the newly received records.

        conn = get_db()

        mines = conn.execute("""
            SELECT *
            FROM mines
            ORDER BY id
        """).fetchall()

        conn.close()

        for record in live_records:

            record["mine_id"] = (
                match_environment_to_mine(
                    record,
                    mines
                )
            )

        return live_records, True

    # --------------------------------------------------------
    # LIVE REQUEST FAILED
    # Use last successful CAAQMS readings.
    # --------------------------------------------------------

    conn = get_db()

    cached = conn.execute("""
        SELECT *
        FROM environmental_data
        WHERE source=?
        ORDER BY recorded_at DESC
        LIMIT 500
    """, (
        CAAQMS_SOURCE,
    )).fetchall()

    conn.close()

    update_system_status(
        "CACHED",
        CAAQMS_SOURCE,
        records_received=len(cached),
        message=(
            "Live CAAQMS request failed. "
            "Showing last successfully cached readings."
        )
    )

    if cached:

        return [
            dict(row)
            for row in cached
        ], False

    # --------------------------------------------------------
    # No CAAQMS cache yet.
    # Return local demonstration data.
    # --------------------------------------------------------

    conn = get_db()

    demo = conn.execute("""
        SELECT *
        FROM environmental_data
        WHERE source='Prototype demonstration data'
        ORDER BY recorded_at DESC
    """).fetchall()

    conn.close()

    return [
        dict(row)
        for row in demo
    ], False


# ============================================================
# LATEST ENVIRONMENT
# ============================================================

def get_latest_environment_for_mine(mine_id, environment=None):

    # ============================================================
    # FIRST PRIORITY: LIVE CAAQMS DATA
    # ============================================================

    if environment:

        live_matches = []

        for record in environment:

            # Only use records explicitly matched to this mine
            if record.get("mine_id") == mine_id:

                source = str(
                    record.get("source") or ""
                ).strip().lower()

                # Prefer official CAAQMS records
                if (
                    "caaqms" in source
                    or "coal india" in source
                ):

                    live_matches.append(record)

        if live_matches:

            live_matches.sort(
                key=lambda x: str(
                    x.get("recorded_at") or ""
                ),
                reverse=True
            )

            return live_matches[0]

    # ============================================================
    # SECOND PRIORITY: ANY MATCHED ENVIRONMENT RECORD
    # ============================================================

    if environment:

        matched = [

            record

            for record in environment

            if record.get("mine_id") == mine_id

        ]

        if matched:

            matched.sort(
                key=lambda x: str(
                    x.get("recorded_at") or ""
                ),
                reverse=True
            )

            return matched[0]

    # ============================================================
    # THIRD PRIORITY: DATABASE CAAQMS CACHE
    # ============================================================

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM environmental_data
        WHERE mine_id=?
          AND (
              LOWER(source) LIKE '%caaqms%'
              OR LOWER(source) LIKE '%coal india%'
          )
        ORDER BY recorded_at DESC
        LIMIT 1
    """, (
        mine_id,
    )).fetchone()

    conn.close()

    if row:

        return dict(row)

    # ============================================================
    # FINAL FALLBACK: HISTORICAL / DEMO DATA
    # ============================================================

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM environmental_data
        WHERE mine_id=?
        ORDER BY recorded_at DESC
        LIMIT 1
    """, (
        mine_id,
    )).fetchone()

    conn.close()

    if row:

        return dict(row)

    return None

# ============================================================
# LATEST ANOMALY
# ============================================================

def get_latest_anomaly_for_mine(
    mine_id
):

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM environmental_anomalies
        WHERE mine_id=?
        ORDER BY detected_at DESC
        LIMIT 1
    """, (
        mine_id,
    )).fetchone()

    conn.close()

    if row:
        return dict(row)

    return None


# ============================================================
# ENVIRONMENTAL RISK
# ============================================================

def calculate_environmental_risk(
    environment
):

    if not environment:
        return 0

    risk = 0

    pm25 = environment.get("pm25")
    pm10 = environment.get("pm10")
    so2 = environment.get("so2")
    no2 = environment.get("no2")
    co = environment.get("co")

    # ========================================================
    # PM2.5
    # Official CAAQMS permissible reference: 60 µg/m³
    # ========================================================

    if pm25 is not None:

        if pm25 >= 100:
            risk += 12

        elif pm25 >= 60:
            risk += 9

        elif pm25 >= 35:
            risk += 5

    # ========================================================
    # PM10
    # Official CAAQMS permissible reference: 100 µg/m³
    # ========================================================

    if pm10 is not None:

        if pm10 >= 180:
            risk += 10

        elif pm10 >= 100:
            risk += 7

        elif pm10 >= 80:
            risk += 4

    # ========================================================
    # SO2
    # ========================================================

    if so2 is not None:

        if so2 >= 80:
            risk += 3

        elif so2 >= 40:
            risk += 2

    # ========================================================
    # NO2
    # ========================================================

    if no2 is not None:

        if no2 >= 80:
            risk += 3

        elif no2 >= 40:
            risk += 2

    # ========================================================
    # CO
    # ========================================================

    if co is not None:

        if co >= 10:
            risk += 3

        elif co >= 4:
            risk += 2

    # ========================================================
    # ENVIRONMENTAL RISK CAP
    # ========================================================

    return min(
        risk,
        25
    )
# ============================================================
# UNIFIED RISK ENGINE
# ============================================================

def calculate_risk_score(
    mine_id,
    environment=None
):

    conn = get_db()

    mine = conn.execute("""
        SELECT *
        FROM mines
        WHERE id=?
    """, (
        mine_id,
    )).fetchone()

    if not mine:

        conn.close()

        return {

            "score": 0,

            "status": "LOW",

            "factors": [],

            "environment": None,

            "components": {},

            "anomaly": None,

            "prediction": None,

            "recommendations": []
        }

    factors = []

    # ========================================================
    # COMPLIANCE — 30 POINTS
    # ========================================================

    compliance_risk = (
        100 - mine["compliance"]
    ) * 0.30

    if mine["compliance"] < 60:

        factors.append(
            f"Low statutory compliance "
            f"({mine['compliance']}%)"
        )

    elif mine["compliance"] < 75:

        factors.append(
            f"Moderate compliance exposure "
            f"({mine['compliance']}%)"
        )

    # ========================================================
    # INSPECTIONS — 25 POINTS
    # ========================================================

    inspections = conn.execute("""
        SELECT
            severity,
            action_status,
            observation
        FROM inspections
        WHERE mine_id=?
    """, (
        mine_id,
    )).fetchall()

    inspection_risk = 0

    for inspection in inspections:

        severity = str(
            inspection["severity"]
        ).lower()

        action_status = str(
            inspection["action_status"]
            or ""
        ).lower()

        if severity == "critical":

            inspection_risk += 20

            factors.append(
                "Critical inspection finding: "
                + inspection["observation"]
            )

        elif severity == "high":

            inspection_risk += 15

            factors.append(
                "High-severity inspection: "
                + inspection["observation"]
            )

        elif severity == "medium":

            inspection_risk += 8

        else:

            inspection_risk += 3

        if action_status == "open":

            inspection_risk += 5

            factors.append(
                "Open corrective action "
                "remains unresolved"
            )

        elif action_status == "escalated":

            inspection_risk += 8

            factors.append(
                "Corrective action "
                "has been escalated"
            )

    inspection_risk = min(
        inspection_risk,
        25
    )

    # ========================================================
    # CONTRACTORS — 20 POINTS
    # ========================================================

    contractors = conn.execute("""
        SELECT
            name,
            performance,
            risk
        FROM contractors
        WHERE mine_id=?
    """, (
        mine_id,
    )).fetchall()

    contractor_risk = 0

    for contractor in contractors:

        contractor_risk_level = str(
            contractor["risk"]
        ).upper()

        performance = (
            contractor["performance"]
        )

        if contractor_risk_level == "HIGH":

            contractor_risk += 12

            factors.append(
                "High-risk contractor: "
                + contractor["name"]
            )

        elif contractor_risk_level == "MEDIUM":

            contractor_risk += 6

        if performance < 60:

            contractor_risk += 8

            factors.append(
                "Low contractor performance "
                f"({performance}%)"
            )

        elif performance < 75:

            contractor_risk += 4

    contractor_risk = min(
        contractor_risk,
        20
    )

    conn.close()

    # ========================================================
    # ENVIRONMENT — 25 POINTS
    # ========================================================

    latest_environment = (
        get_latest_environment_for_mine(
            mine_id,
            environment
        )
    )

    environmental_risk = (
        calculate_environmental_risk(
            latest_environment
        )
    )

    # ========================================================
    # ML ANOMALY SIGNAL
    # ========================================================

    anomaly = (
        get_latest_anomaly_for_mine(
            mine_id
        )
    )

    ml_risk = 0

    if anomaly:

        if anomaly["anomaly_level"] == "HIGH":

            ml_risk = 5

            factors.append(
                "ML anomaly detected in "
                "environmental monitoring pattern"
            )

        elif anomaly["anomaly_level"] == "MEDIUM":

            ml_risk = 3

            factors.append(
                "ML detected an unusual "
                "environmental pattern"
            )

    environmental_risk = min(
        environmental_risk + ml_risk,
        25
    )

    # ========================================================
    # ENVIRONMENT FACTORS
    # ========================================================

    if latest_environment:

        readings = {

            "PM2.5":
                (
                    latest_environment.get(
                        "pm25"
                    ),
                    35
                ),

            "PM10":
                (
                    latest_environment.get(
                        "pm10"
                    ),
                    80
                ),

            "SO₂":
                (
                    latest_environment.get(
                        "so2"
                    ),
                    40
                ),

            "NO₂":
                (
                    latest_environment.get(
                        "no2"
                    ),
                    40
                ),

            "CO":
                (
                    latest_environment.get(
                        "co"
                    ),
                    4
                )
        }

        for parameter, (
            value,
            threshold
        ) in readings.items():

            if (
                value is not None
                and value >= threshold
            ):

                unit = (
                    "mg/m³"
                    if parameter == "CO"
                    else "µg/m³"
                )

                factors.append(
                    f"Elevated {parameter} "
                    f"({value} {unit})"
                )

    # ========================================================
    # INCIDENT PENALTY
    # ========================================================

    conn = get_db()

    incident_row = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(
                CASE
                    WHEN closure_status != 'CLOSED'
                    THEN 1
                    ELSE 0
                END
            ) AS open_count
        FROM incidents
        WHERE mine_id=?
    """, (
        mine_id,
    )).fetchone()

    conn.close()

    total_incidents = (
        incident_row["total"] or 0
    )

    open_incidents = (
        incident_row["open_count"] or 0
    )

    incident_penalty = min(
        total_incidents * 2
        +
        open_incidents * 3,
        10
    )

    if open_incidents > 0:

        factors.append(
            f"{open_incidents} unresolved "
            "incident(s)"
        )

    # ========================================================
    # FINAL SCORE
    # ========================================================

    score = round(

        compliance_risk

        + inspection_risk

        + contractor_risk

        + environmental_risk

        + incident_penalty
    )

    score = max(
        0,
        min(
            score,
            100
        )
    )

    if score >= 75:

        status = "HIGH"

    elif score >= 50:

        status = "MEDIUM"

    else:

        status = "LOW"

    # ========================================================
    # RECOMMENDATIONS
    # ========================================================

    recommendations = []

    if compliance_risk >= 8:

        recommendations.append(
            "Review overdue and due-soon "
            "statutory compliance requirements."
        )

    if inspection_risk >= 10:

        recommendations.append(
            "Prioritize unresolved high-severity "
            "inspection findings."
        )

    if contractor_risk >= 8:

        recommendations.append(
            "Review contractor safety performance "
            "and corrective measures."
        )

    if environmental_risk >= 8:

        recommendations.append(
            "Increase environmental monitoring and "
            "inspect dust/emission control systems."
        )

    if anomaly and anomaly["anomaly_level"] in (
        "HIGH",
        "MEDIUM"
    ):

        recommendations.append(
            "Investigate the unusual environmental "
            "pattern identified by the ML model."
        )

    if open_incidents > 0:

        recommendations.append(
            "Maintain incident response until all "
            "open emergency actions are closed."
        )

    if not recommendations:

        recommendations.append(
            "Continue routine monitoring and "
            "scheduled compliance inspections."
        )

    return {

        "score":
            score,

        "status":
            status,

        "factors":
            factors[:12],

        "environment":
            latest_environment,

        "components": {

            "compliance":
                round(
                    compliance_risk
                ),

            "inspection":
                round(
                    inspection_risk
                ),

            "contractor":
                round(
                    contractor_risk
                ),

            "environment":
                round(
                    environmental_risk
                ),

            "incidents":
                incident_penalty
        },

        "anomaly":
            anomaly,

        "prediction":
            None,

        "recommendations":
            recommendations
    }


# ============================================================
# PERSIST RISK TO DATABASE
# ============================================================

def refresh_all_risk_scores(
    environment=None
):

    if environment is None:

        environment, _ = (
            get_environment_data()
        )

    conn = get_db()

    mines = conn.execute("""
        SELECT id
        FROM mines
    """).fetchall()

    conn.close()

    updated = 0

    for mine in mines:

        result = calculate_risk_score(
            mine["id"],
            environment
        )

        conn = get_db()

        conn.execute("""
            UPDATE mines
            SET
                risk_score=?,
                status=?
            WHERE id=?
        """, (

            result["score"],

            result["status"],

            mine["id"]
        ))

        conn.commit()
        conn.close()

        updated += 1

    return updated


# ============================================================
# AI RISK PREDICTION
# ============================================================

def build_ml_features(
    mine_id,
    environment=None
):

    conn = get_db()

    mine = conn.execute("""
        SELECT *
        FROM mines
        WHERE id=?
    """, (
        mine_id,
    )).fetchone()

    if not mine:

        conn.close()

        return None

    inspection_row = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(
                CASE
                    WHEN severity='High'
                    OR severity='Critical'
                    THEN 1
                    ELSE 0
                END
            ) AS serious,
            SUM(
                CASE
                    WHEN action_status != 'Closed'
                    THEN 1
                    ELSE 0
                END
            ) AS open_actions
        FROM inspections
        WHERE mine_id=?
    """, (
        mine_id,
    )).fetchone()

    contractor_row = conn.execute("""
        SELECT
            AVG(performance) AS performance
        FROM contractors
        WHERE mine_id=?
    """, (
        mine_id,
    )).fetchone()

    incident_row = conn.execute("""
        SELECT
            COUNT(*) AS incidents,
            SUM(
                CASE
                    WHEN closure_status != 'CLOSED'
                    THEN 1
                    ELSE 0
                END
            ) AS open_incidents
        FROM incidents
        WHERE mine_id=?
    """, (
        mine_id,
    )).fetchone()

    conn.close()

    env = get_latest_environment_for_mine(
        mine_id,
        environment
    )

    
    return [
        float(mine["compliance"] or 0),

        float(
            (env or {}).get("pm25") or 0
        ),

        float(
            (env or {}).get("pm10") or 0
        ),

        float(
            (env or {}).get("so2") or 0
        ),

        float(
            (env or {}).get("no2") or 0
        ),

        float(
            (env or {}).get("co") or 0
        ),

        float(
        inspection_row["serious"] if inspection_row and inspection_row["serious"] is not None else 0
        ),

        float(
        inspection_row["open_actions"] if inspection_row and inspection_row["open_actions"] is not None else 0
        ),

        float(
        contractor_row["performance"] if contractor_row and contractor_row["performance"] is not None else 100
        ),

        float(
        incident_row["incidents"] if incident_row and incident_row["incidents"] is not None else 0
        ),

        float(
        incident_row["open_incidents"] if incident_row and incident_row["open_incidents"] is not None else 0
        )
    ]




def ai_risk_prediction(
    mine_id,
    environment=None
):

    if not ML_AVAILABLE:

        return {

            "available": False,

            "prediction": "ML library unavailable",

            "probability": None,

            "explanation":
                "Install scikit-learn to enable "
                "the risk prediction model."
        }

    current = build_ml_features(
        mine_id,
        environment
    )

    if current is None:

        return {

            "available": False,

            "prediction": "No mine data",

            "probability": None,

            "explanation": ""
        }

    # --------------------------------------------------------
    # Build a small governance training set from the
    # existing mine profiles and historical-style perturbations.
    #
    # The model learns the relationship between governance
    # indicators and the unified risk label.
    # --------------------------------------------------------

    conn = get_db()

    mines = conn.execute("""
        SELECT id
        FROM mines
    """).fetchall()

    conn.close()

    training_X = []
    training_y = []

    for mine in mines:

        features = build_ml_features(
            mine["id"],
            environment
        )

        if features is None:
            continue

        risk = calculate_risk_score(
            mine["id"],
            environment
        )

        label = (
            1
            if risk["status"] == "HIGH"
            else 0
        )

        training_X.append(
            features
        )

        training_y.append(
            label
        )

        # Add controlled variations so the model
        # has enough examples to learn boundaries.

        for factor in (
            0.85,
            0.95,
            1.05,
            1.15
        ):

            variation = [
                value
                for value in features
            ]

            variation[0] = max(
                0,
                min(
                    100,
                    variation[0] * factor
                )
            )

            for index in range(
                1,
                6
            ):

                variation[index] = (
                    max(
                        0,
                        variation[index] * factor
                    )
                )

            variation[6] = max(
                0,
                round(
                    variation[6] * factor
                )
            )

            variation[7] = max(
                0,
                round(
                    variation[7] * factor
                )
            )

            variation[8] = max(
                0,
                min(
                    100,
                    variation[8] / factor
                )
            )

            variation[9] = max(
                0,
                round(
                    variation[9] * factor
                )
            )

            variation[10] = max(
                0,
                round(
                    variation[10] * factor
                )
            )

            # Calculate a label using governance logic.

            simulated_compliance_risk = (
                (100 - variation[0])
                * 0.30
            )

            environmental = 0

            if variation[1] >= 100:
                environmental += 10
            elif variation[1] >= 60:
                environmental += 7
            elif variation[1] >= 35:
                environmental += 4

            if variation[2] >= 180:
                environmental += 8
            elif variation[2] >= 100:
                environmental += 6
            elif variation[2] >= 80:
                environmental += 3

            if variation[3] >= 80:
                environmental += 3
            elif variation[3] >= 40:
                environmental += 2

            if variation[4] >= 80:
                environmental += 3
            elif variation[4] >= 40:
                environmental += 2

            if variation[5] >= 10:
                environmental += 3
            elif variation[5] >= 4:
                environmental += 2

            simulated_score = (
                simulated_compliance_risk
                +
                min(
                    variation[6] * 8,
                    25
                )
                +
                min(
                    max(
                        0,
                        (100 - variation[8])
                        * 0.20
                    ),
                    20
                )
                +
                min(
                    environmental,
                    25
                )
                +
                min(
                    variation[9] * 2
                    +
                    variation[10] * 3,
                    10
                )
            )

            training_X.append(
                variation
            )

            training_y.append(
                1
                if simulated_score >= 75
                else 0
            )

    # Ensure both classes exist.

    if len(
        set(training_y)
    ) < 2:

        return {

            "available": False,

            "prediction": "Insufficient training variation",

            "probability": None,

            "explanation":
                "The model requires both low-risk "
                "and high-risk examples."
        }

    try:

        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            random_state=42,
            class_weight="balanced"
        )

        model.fit(
            training_X,
            training_y
        )

        prediction = model.predict(
            [current]
        )[0]

        probabilities = (
            model.predict_proba(
                [current]
            )[0]
        )

        high_probability = 0

        for index, class_value in enumerate(
            model.classes_
        ):

            if class_value == 1:

                high_probability = (
                    probabilities[index]
                )

        prediction_label = (
            "HIGH RISK"
            if prediction == 1
            else "LOW / MODERATE RISK"
        )

        feature_names = [

            "Compliance",

            "PM2.5",

            "PM10",

            "SO₂",

            "NO₂",

            "CO",

            "Serious inspections",

            "Open corrective actions",

            "Contractor performance",

            "Incidents",

            "Open incidents"
        ]

        importance_pairs = list(
            zip(
                feature_names,
                model.feature_importances_
            )
        )

        importance_pairs.sort(
            key=lambda x: x[1],
            reverse=True
        )

        important = [

            name

            for name, importance
            in importance_pairs[:4]

            if importance > 0.02
        ]

        if important:

            explanation = (
                "The model's strongest signals are: "
                +
                ", ".join(
                    important
                )
                +
                "."
            )

        else:

            explanation = (
                "The model evaluated the available "
                "governance and environmental indicators."
            )

        return {

            "available": True,

            "prediction":
                prediction_label,

            "probability":
                round(
                    high_probability * 100,
                    1
                ),

            "explanation":
                explanation,

            "model":
                "Random Forest",

            "training_samples":
                len(training_X),

            "top_features":
                [
                    {
                        "feature": name,
                        "importance":
                            round(
                                float(importance),
                                4
                            )
                    }

                    for name, importance
                    in importance_pairs[:6]
                ]
        }

    except Exception as error:

        print(
            "AI RISK MODEL ERROR:",
            repr(error)
        )

        return {

            "available": False,

            "prediction": "Model error",

            "probability": None,

            "explanation":
                str(error)
        }


# ============================================================
# AI RECOMMENDATION ENGINE
# ============================================================

def get_ai_analysis(
    mine_id,
    environment=None
):

    risk = calculate_risk_score(
        mine_id,
        environment
    )

    prediction = ai_risk_prediction(
        mine_id,
        environment
    )

    return {

        "mine_id":
            mine_id,

        "risk_score":
            risk["score"],

        "risk_status":
            risk["status"],

        "components":
            risk["components"],

        "risk_factors":
            risk["factors"],

        "ml_anomaly":
            risk["anomaly"],

        "risk_prediction":
            prediction,

        "recommendations":
            risk["recommendations"]
    }


# ============================================================
# ALERT GENERATION
# ============================================================

def generate_environment_alerts():

    conn = get_db()

    rows = conn.execute("""
        SELECT
            e.*,
            m.id AS linked_mine_id
        FROM environmental_data e
        LEFT JOIN mines m
            ON e.mine_id = m.id
        WHERE e.source=?
        ORDER BY e.recorded_at DESC
        LIMIT 200
    """, (
        CAAQMS_SOURCE,
    )).fetchall()

    created = 0

    for row in rows:

        mine_id = row["linked_mine_id"]

        if not mine_id:
            continue

        readings = [

            (
                "PM2.5",
                row["pm25"],
                60
            ),

            (
                "PM10",
                row["pm10"],
                100
            ),

            (
                "SO2",
                row["so2"],
                40
            ),

            (
                "NO2",
                row["no2"],
                40
            )
        ]

        for parameter, value, threshold in readings:

            if value is None:
                continue

            if value < threshold:
                continue

            severity = (

                "HIGH"

                if value >= threshold * 1.5

                else "MEDIUM"
            )

            title = (
                f"{parameter} "
                "environmental alert"
            )

            message = (

                f"{parameter} reading of "
                f"{value} exceeds the "
                f"monitoring threshold "
                f"of {threshold}."
            )

            exists = conn.execute("""
                SELECT id
                FROM alerts
                WHERE mine_id=?
                  AND alert_type=?
                  AND created_at=?
            """, (

                mine_id,

                parameter,

                row["recorded_at"]
            )).fetchone()

            if exists:
                continue

            conn.execute("""
                INSERT INTO alerts
                (
                    mine_id,
                    alert_type,
                    severity,
                    title,
                    message,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 'OPEN', ?)
            """, (

                mine_id,

                parameter,

                severity,

                title,

                message,

                row["recorded_at"]
            ))

            created += 1

    conn.commit()
    conn.close()

    return created


def generate_anomaly_alerts():

    if not ML_AVAILABLE:
        return 0

    conn = get_db()

    anomalies = conn.execute("""
        SELECT
            a.*,
            e.recorded_at,
            e.mine_id,
            m.name AS mine_name
        FROM environmental_anomalies a
        JOIN environmental_data e
            ON e.id = a.environmental_id
        JOIN mines m
            ON m.id = a.mine_id
        WHERE a.anomaly_level IN ('HIGH', 'MEDIUM')
        ORDER BY a.detected_at DESC
        LIMIT 100
    """).fetchall()

    created = 0

    for anomaly in anomalies:

        alert_type = "ML_ANOMALY"

        exists = conn.execute("""
            SELECT id
            FROM alerts
            WHERE mine_id=?
              AND alert_type=?
              AND created_at=?
        """, (

            anomaly["mine_id"],

            alert_type,

            anomaly["recorded_at"]
        )).fetchone()

        if exists:
            continue

        severity = (
            "HIGH"
            if anomaly["anomaly_level"] == "HIGH"
            else "MEDIUM"
        )

        title = (
            "ML environmental anomaly detected"
        )

        message = (
            f"Unusual environmental pattern "
            f"detected at {anomaly['mine_name']}. "
            f"Anomaly score: "
            f"{anomaly['anomaly_score']}/100. "
            f"{anomaly['explanation']}"
        )

        conn.execute("""
            INSERT INTO alerts
            (
                mine_id,
                alert_type,
                severity,
                title,
                message,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 'OPEN', ?)
        """, (

            anomaly["mine_id"],

            alert_type,

            severity,

            title,

            message,

            anomaly["recorded_at"]
        ))

        created += 1

    conn.commit()
    conn.close()

    return created


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
def dashboard():

    live_environment, environment_live = (
        get_environment_data()
    )

    refresh_all_risk_scores(
        live_environment
    )

    generate_environment_alerts()
    generate_anomaly_alerts()

    conn = get_db()

    mines = conn.execute("""
        SELECT *
        FROM mines
        ORDER BY risk_score DESC
    """).fetchall()

    inspections = conn.execute("""
        SELECT
            inspections.*,
            mines.name AS mine_name
        FROM inspections
        JOIN mines
            ON mines.id = inspections.mine_id
        ORDER BY inspections.id DESC
        LIMIT 8
    """).fetchall()

    contractors = conn.execute("""
        SELECT
            contractors.*,
            mines.name AS mine_name
        FROM contractors
        JOIN mines
            ON mines.id = contractors.mine_id
        ORDER BY contractors.id DESC
    """).fetchall()

    compliance = conn.execute("""
        SELECT
            compliance.*,
            mines.name AS mine_name
        FROM compliance
        JOIN mines
            ON mines.id = compliance.mine_id
        ORDER BY compliance.id DESC
        LIMIT 8
    """).fetchall()

    total = conn.execute("""
        SELECT COUNT(*)
        FROM mines
    """).fetchone()[0]

    avg_compliance = conn.execute("""
    SELECT AVG(compliance)
    FROM mines
    WHERE status != 'DATA PENDING'
      AND compliance > 0
""").fetchone()[0]

    open_issues = conn.execute("""
        SELECT COUNT(*)
        FROM inspections
        WHERE action_status != 'Closed'
    """).fetchone()[0]

    open_alerts = conn.execute("""
        SELECT COUNT(*)
        FROM alerts
        WHERE status='OPEN'
    """).fetchone()[0]

    open_incidents = conn.execute("""
        SELECT COUNT(*)
        FROM incidents
        WHERE closure_status != 'CLOSED'
    """).fetchone()[0]

    conn.close()

    updated_mines = []

    for mine in mines:

        result = calculate_risk_score(
            mine["id"],
            live_environment
        )

        updated = dict(mine)

        updated["risk_score"] = (
            result["score"]
        )

        updated["status"] = (
            result["status"]
        )

        updated["risk_factors"] = (
            result["factors"]
        )

        updated["risk_components"] = (
            result["components"]
        )

        updated["anomaly"] = (
            result["anomaly"]
        )

        updated["recommendations"] = (
            result["recommendations"]
        )

        updated_mines.append(
            updated
        )

    updated_mines.sort(
        key=lambda x: x["risk_score"],
        reverse=True
    )

    high = sum(

        1

        for mine in updated_mines

        if mine["status"] == "HIGH"
    )

    medium = sum(

        1

        for mine in updated_mines

        if mine["status"] == "MEDIUM"
    )

    system_status = get_system_status()

    return render_template(

        "dashboard.html",

        mines=updated_mines,

        inspections=inspections,

        compliance=compliance,

        contractors=contractors,

        total=total,

        high=high,

        medium=medium,

        open_issues=open_issues,

        open_alerts=open_alerts,

        open_incidents=open_incidents,

        avg_compliance=round(
            avg_compliance or 0
        ),

        live_environment=live_environment,

        environment_live=environment_live,

        system_status=system_status,

        ml_available=ML_AVAILABLE
    )


# ============================================================
# MINE PROFILE
# ============================================================

@app.route(
    "/mine/<int:mine_id>"
)
def mine_detail(mine_id):

    environment, live = (
        get_environment_data()
    )

    refresh_all_risk_scores(
        environment
    )

    generate_environment_alerts()
    generate_anomaly_alerts()

    conn = get_db()

    mine = conn.execute("""
        SELECT *
        FROM mines
        WHERE id=?
    """, (
        mine_id,
    )).fetchone()

    if not mine:

        conn.close()

        return (
            "Mine not found",
            404
        )

    inspections = conn.execute("""
        SELECT *
        FROM inspections
        WHERE mine_id=?
        ORDER BY id DESC
    """, (
        mine_id,
    )).fetchall()

    compliance = conn.execute("""
        SELECT *
        FROM compliance
        WHERE mine_id=?
        ORDER BY due_date
    """, (
        mine_id,
    )).fetchall()

    contractors = conn.execute("""
        SELECT *
        FROM contractors
        WHERE mine_id=?
    """, (
        mine_id,
    )).fetchall()

    alerts = conn.execute("""
        SELECT *
        FROM alerts
        WHERE mine_id=?
        ORDER BY id DESC
        LIMIT 10
    """, (
        mine_id,
    )).fetchall()

    incidents = conn.execute("""
        SELECT *
        FROM incidents
        WHERE mine_id=?
        ORDER BY id DESC
        LIMIT 10
    """, (
        mine_id,
    )).fetchall()

    conn.close()

    risk = calculate_risk_score(
        mine_id,
        environment
    )

    ai_analysis = get_ai_analysis(
        mine_id,
        environment
    )

    recommendation = (

        "Priority management review recommended. "
        "Conduct a targeted safety inspection and "
        "close escalated corrective actions."

        if risk["status"] == "HIGH"

        else

        "Enhanced monitoring recommended. "
        "Review outstanding compliance requirements "
        "and corrective actions."

        if risk["status"] == "MEDIUM"

        else

        "Continue routine monitoring and scheduled "
        "compliance inspections."
    )

    return render_template(

        "mine.html",

        mine=mine,

        inspections=inspections,

        compliance=compliance,

        contractors=contractors,

        alerts=alerts,

        incidents=incidents,

        environment=risk["environment"],

        environment_live=live,

        risk_score=risk["score"],

        risk_status=risk["status"],

        risk_factors=risk["factors"],

        recommendation=recommendation,

        risk_components=risk["components"],

        anomaly=risk["anomaly"],

        ai_analysis=ai_analysis,

        ml_available=ML_AVAILABLE
    )


# ============================================================
# INSPECTOR PORTAL
# ============================================================

@app.route("/inspector")
def inspector():

    if (
        not session.get("logged_in")
        or session.get("role") != "inspector"
    ):

        return redirect(
            url_for("login")
        )

    environment, _ = (
        get_environment_data()
    )

    refresh_all_risk_scores(
        environment
    )

    conn = get_db()

    mines = conn.execute("""
        SELECT *
        FROM mines
        ORDER BY risk_score DESC
    """).fetchall()

    recent_inspections = conn.execute("""
        SELECT
            inspections.*,
            mines.name AS mine_name
        FROM inspections
        JOIN mines
            ON mines.id = inspections.mine_id
        ORDER BY inspections.id DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    return render_template(

        "inspector.html",

        mines=mines,

        recent_inspections=recent_inspections
    )


# ============================================================
# NEW INSPECTION
# ============================================================

@app.route(
    "/inspection/new",
    methods=["GET", "POST"]
)
def new_inspection():

    if (
        not session.get("logged_in")
        or session.get("role") != "inspector"
    ):

        return redirect(
            url_for("login")
        )

    conn = get_db()

    mines = conn.execute("""
        SELECT *
        FROM mines
        ORDER BY name
    """).fetchall()

    if request.method == "POST":

        mine_id = request.form["mine_id"]

        category = request.form["category"]

        observation = request.form["observation"]

        severity = request.form["severity"]

        corrective_action = (
            request.form.get(
                "corrective_action",
                ""
            )
        )

        latitude = (
            request.form.get(
                "latitude"
            )
            or None
        )

        longitude = (
            request.form.get(
                "longitude"
            )
            or None
        )

        created_at = (
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        cursor = conn.execute("""
            INSERT INTO inspections
            (
                mine_id,
                category,
                observation,
                severity,
                latitude,
                longitude,
                created_at,
                corrective_action,
                action_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            mine_id,

            category,

            observation,

            severity,

            latitude,

            longitude,

            created_at,

            corrective_action,

            "Pending"
        ))

        inspection_id = (
            cursor.lastrowid
        )

        conn.commit()
        conn.close()

        audit(

            "Created field inspection",

            "inspection",

            inspection_id,

            observation
        )

        refresh_all_risk_scores()

        return redirect(
            url_for("dashboard")
        )

    conn.close()

    return render_template(

        "inspection.html",

        mines=mines
    )


# ============================================================
# API — MINES
# ============================================================

@app.route("/api/mines")
def api_mines():

    # ------------------------------------------------------------
    # Get the latest environmental data once
    # ------------------------------------------------------------

    environment, live = get_environment_data()


    # ------------------------------------------------------------
    # Load all mines
    # ------------------------------------------------------------

    conn = get_db()

    mines = conn.execute("""
        SELECT *
        FROM mines
        ORDER BY id
    """).fetchall()

    conn.close()


    results = []


    # ------------------------------------------------------------
    # Calculate risk once per mine
    # ------------------------------------------------------------

    for mine in mines:

        risk = calculate_risk_score(
            mine["id"],
            environment
        )


        item = dict(mine)


        item["risk_score"] = (
            risk["score"]
        )

        item["status"] = (
            risk["status"]
        )

        item["risk_factors"] = (
            risk["factors"]
        )

        item["risk_components"] = (
            risk["components"]
        )

        item["environment_live"] = (
            live
        )

        item["environment"] = (
            risk["environment"]
        )

        item["anomaly"] = (
            risk["anomaly"]
        )

        item["recommendations"] = (
            risk["recommendations"]
        )


        # --------------------------------------------------------
        # AI analysis
        # --------------------------------------------------------

        

        results.append(item)


    # ------------------------------------------------------------
    # Highest-risk mines first
    # ------------------------------------------------------------

    results.sort(
        key=lambda x: x["risk_score"],
        reverse=True
    )


    return jsonify(results)

# ============================================================
# API — SINGLE MINE
# ============================================================

@app.route(
    "/api/mine/<int:mine_id>"
)
def api_single_mine(mine_id):

    environment, live = (
        get_environment_data()
    )

    risk = calculate_risk_score(
        mine_id,
        environment
    )

    ai = get_ai_analysis(
        mine_id,
        environment
    )

    conn = get_db()

    mine = conn.execute("""
        SELECT *
        FROM mines
        WHERE id=?
    """, (
        mine_id,
    )).fetchone()

    conn.close()

    if not mine:

        return jsonify({
            "error": "Mine not found"
        }), 404

    result = dict(mine)

    result["risk"] = risk
    result["ai"] = ai
    result["environment_live"] = live

    return jsonify(result)


# ============================================================
# API — AI ANALYSIS
# ============================================================

@app.route(
    "/api/ai-analysis/<int:mine_id>"
)
def api_ai_analysis(mine_id):

    environment, live = (
        get_environment_data()
    )

    analysis = get_ai_analysis(
        mine_id,
        environment
    )

    analysis["environment_live"] = live

    return jsonify(analysis)


# ============================================================
# API — CAAQMS
# ============================================================

@app.route("/api/caaqms")
def api_caaqms():

    records, live = (
        get_environment_data()
    )

    return jsonify({

        "source":
            CAAQMS_SOURCE,

        "live":
            live,

        "cached_fallback":
            not live,

        "count":
            len(records),

        "system_status":
            get_system_status(),

        "records":
            records
    })


# ============================================================
# API — MANUAL REFRESH
# ============================================================

@app.route(
    "/api/refresh-data",
    methods=["POST", "GET"]
)
def refresh_data():

    before = get_system_status()

    records = fetch_caaqms_data()

    if records:

        inserted = cache_caaqms_records(
            records
        )

        now = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        update_system_status(
            "LIVE",
            CAAQMS_SOURCE,
            successful_time=now,
            records_received=len(records),
            message=(
                f"Manual refresh successful. "
                f"{len(records)} records received; "
                f"{inserted} new records cached."
            )
        )

        environment, _ = (
            get_environment_data()
        )

        refresh_all_risk_scores(
            environment
        )

        generate_environment_alerts()
        generate_anomaly_alerts()

        audit(
            "CAAQMS data refresh",
            "environment",
            None,
            f"{len(records)} records received"
        )

        return jsonify({

            "success": True,

            "live": True,

            "records_received":
                len(records),

            "new_records":
                inserted,

            "message":
                "Official CAAQMS data refreshed successfully.",

            "previous_status":
                before
        })

    update_system_status(
        "CACHED",
        CAAQMS_SOURCE,
        records_received=0,
        message=(
            "CAAQMS refresh failed. "
            "Last successful data remains available."
        )
    )

    audit(
        "CAAQMS refresh failed",
        "environment",
        None,
        "Using cached fallback data"
    )

    return jsonify({

        "success": False,

        "live": False,

        "cached_fallback": True,

        "message":
            "Live source unavailable. "
            "Last successful data remains active.",

        "system_status":
            get_system_status()
    })


# ============================================================
# API — ENVIRONMENT
# ============================================================

@app.route("/api/environment")
def api_environment():

    conn = get_db()

    data = conn.execute("""
        SELECT
            environmental_data.*,
            mines.name AS linked_mine,
            mines.subsidiary,
            mines.state
        FROM environmental_data
        LEFT JOIN mines
            ON mines.id =
               environmental_data.mine_id
        ORDER BY environmental_data.recorded_at DESC
        LIMIT 500
    """).fetchall()

    conn.close()

    return jsonify([

        dict(row)

        for row in data
    ])


# ============================================================
# API — ML ANOMALIES
# ============================================================

@app.route("/api/anomalies")
def api_anomalies():

    conn = get_db()

    anomalies = conn.execute("""
        SELECT
            environmental_anomalies.*,
            mines.name AS mine_name,
            environmental_data.recorded_at,
            environmental_data.pm25,
            environmental_data.pm10,
            environmental_data.so2,
            environmental_data.no2,
            environmental_data.co
        FROM environmental_anomalies
        LEFT JOIN mines
            ON mines.id =
               environmental_anomalies.mine_id
        LEFT JOIN environmental_data
            ON environmental_data.id =
               environmental_anomalies.environmental_id
        ORDER BY environmental_anomalies.detected_at DESC
        LIMIT 100
    """).fetchall()

    conn.close()

    return jsonify([

        dict(row)

        for row in anomalies
    ])


# ============================================================
# API — ALERTS
# ============================================================

@app.route("/api/alerts")
def api_alerts():

    generate_environment_alerts()
    generate_anomaly_alerts()

    conn = get_db()

    alerts = conn.execute("""
        SELECT
            alerts.*,
            mines.name AS mine_name
        FROM alerts
        LEFT JOIN mines
            ON mines.id =
               alerts.mine_id
        ORDER BY alerts.id DESC
        LIMIT 100
    """).fetchall()

    conn.close()

    return jsonify([

        dict(row)

        for row in alerts
    ])


# ============================================================
# API — AUDIT
# ============================================================

@app.route("/api/audit")
def api_audit():

    conn = get_db()

    logs = conn.execute("""
        SELECT *
        FROM audit_log
        ORDER BY id DESC
        LIMIT 100
    """).fetchall()

    conn.close()

    return jsonify([

        dict(row)

        for row in logs
    ])


# ============================================================
# API — INSPECTIONS
# ============================================================

@app.route("/api/inspections")
def api_inspections():

    conn = get_db()

    rows = conn.execute("""
        SELECT
            inspections.*,
            mines.name AS mine_name
        FROM inspections
        JOIN mines
            ON mines.id = inspections.mine_id
        ORDER BY inspections.id DESC
        LIMIT 200
    """).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# API — COMPLIANCE
# ============================================================

@app.route("/api/compliance")
def api_compliance():

    conn = get_db()

    rows = conn.execute("""
        SELECT
            compliance.*,
            mines.name AS mine_name
        FROM compliance
        JOIN mines
            ON mines.id = compliance.mine_id
        ORDER BY compliance.due_date
    """).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# API — CONTRACTORS
# ============================================================

@app.route("/api/contractors")
def api_contractors():

    conn = get_db()

    rows = conn.execute("""
        SELECT
            contractors.*,
            mines.name AS mine_name
        FROM contractors
        JOIN mines
            ON mines.id = contractors.mine_id
        ORDER BY contractors.performance ASC
    """).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# MINE PORTAL
# ============================================================

@app.route("/mine-portal")
def mine_portal():

    if (
        not session.get("logged_in")
        or session.get("role") != "mine"
    ):

        return redirect(
            url_for("login")
        )

    environment, _ = (
        get_environment_data()
    )

    refresh_all_risk_scores(
        environment
    )

    conn = get_db()

    mines = conn.execute("""
        SELECT *
        FROM mines
        ORDER BY name
    """).fetchall()

    conn.close()

    updated_mines = []

    for mine in mines:

        risk = calculate_risk_score(
            mine["id"],
            environment
        )

        item = dict(mine)

        item["risk_score"] = (
            risk["score"]
        )

        item["status"] = (
            risk["status"]
        )

        item["recommendations"] = (
            risk["recommendations"]
        )

        updated_mines.append(
            item
        )

    updated_mines.sort(
        key=lambda x: x["risk_score"],
        reverse=True
    )

    return render_template(

        "mine_portal.html",

        mines=updated_mines
    )
@app.route("/mine-registry")
def mine_registry():

    live_environment, environment_live = (
        get_environment_data()
    )

    refresh_all_risk_scores(
        live_environment
    )

    conn = get_db()

    mines = conn.execute("""
        SELECT *
        FROM mines
        ORDER BY name
    """).fetchall()

    conn.close()

    updated_mines = []

    for mine in mines:

        result = calculate_risk_score(
            mine["id"],
            live_environment
        )

        updated = dict(mine)

        updated["risk_score"] = (
            result["score"]
        )

        updated["status"] = (
            result["status"]
        )

        updated["risk_factors"] = (
            result["factors"]
        )

        updated["risk_components"] = (
            result["components"]
        )

        updated["anomaly"] = (
            result["anomaly"]
        )

        updated["recommendations"] = (
            result["recommendations"]
        )

        updated_mines.append(
            updated
        )

    updated_mines.sort(
        key=lambda x: x["risk_score"],
        reverse=True
    )

    subsidiaries = sorted(
        set(
            mine["subsidiary"]
            for mine in updated_mines
            if mine["subsidiary"]
        )
    )

    states = sorted(
        set(
            mine["state"]
            for mine in updated_mines
            if mine["state"]
        )
    )

    return render_template(
        "mine_registry.html",
        mines=updated_mines,
        subsidiaries=subsidiaries,
        states=states,
        environment_live=environment_live
    )

# ============================================================
# INCIDENT MANAGEMENT
# ============================================================

@app.route("/incidents")
def incidents():

    conn = get_db()

    incidents = conn.execute("""
        SELECT
            incidents.*,
            mines.name AS mine_name,
            mines.subsidiary,
            mines.state
        FROM incidents
        JOIN mines
            ON mines.id = incidents.mine_id
        ORDER BY incidents.id DESC
    """).fetchall()

    mines = conn.execute("""
        SELECT *
        FROM mines
        ORDER BY name
    """).fetchall()

    conn.close()

    return render_template(
        "incidents.html",
        incidents=incidents,
        mines=mines
    )


@app.route(
    "/incident/new",
    methods=["GET", "POST"]
)
def new_incident():

    if (
        not session.get("logged_in")
        or session.get("role") != "inspector"
    ):

        return redirect(
            url_for("login")
        )

    conn = get_db()

    mines = conn.execute("""
        SELECT *
        FROM mines
        ORDER BY name
    """).fetchall()

    if request.method == "POST":

        mine_id = request.form["mine_id"]

        incident_type = (
            request.form["incident_type"]
        )

        severity = (
            request.form["severity"]
        )

        description = (
            request.form["description"]
        )

        latitude = (
            request.form.get(
                "latitude"
            )
            or None
        )

        longitude = (
            request.form.get(
                "longitude"
            )
            or None
        )

        occurred_at = (
            request.form.get(
                "occurred_at"
            )
            or datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        reported_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        workers_affected = safe_int(
            request.form.get(
                "workers_affected",
                0
            )
        )

        injured_count = safe_int(
            request.form.get(
                "injured_count",
                0
            )
        )

        missing_count = safe_int(
            request.form.get(
                "missing_count",
                0
            )
        )

        fatality_count = safe_int(
            request.form.get(
                "fatality_count",
                0
            )
        )

        emergency_status = (
            "CRITICAL"
            if severity == "CRITICAL"
            else "ACTIVE"
        )

        evacuation_status = (
            "IN_PROGRESS"
            if severity == "CRITICAL"
            else "NOT_STARTED"
        )

        rescue_status = (
            "REQUIRED"
            if missing_count > 0
            else "NOT_REQUIRED"
        )

        cursor = conn.execute("""
            INSERT INTO incidents
            (
                mine_id,
                incident_type,
                severity,
                description,
                latitude,
                longitude,
                occurred_at,
                reported_at,
                workers_affected,
                injured_count,
                missing_count,
                fatality_count,
                emergency_status,
                evacuation_status,
                rescue_status,
                investigation_status,
                closure_status,
                reported_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            mine_id,

            incident_type,

            severity,

            description,

            latitude,

            longitude,

            occurred_at,

            reported_at,

            workers_affected,

            injured_count,

            missing_count,

            fatality_count,

            emergency_status,

            evacuation_status,

            rescue_status,

            "PENDING",

            "OPEN",

            session.get(
                "username",
                "inspector"
            )
        ))

        incident_id = cursor.lastrowid

        # ----------------------------------------------------
        # CRITICAL ALERT
        # ----------------------------------------------------

        if severity == "CRITICAL":

            conn.execute("""
                INSERT INTO alerts
                (
                    mine_id,
                    alert_type,
                    severity,
                    title,
                    message,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 'OPEN', ?)
            """, (

                mine_id,

                "ACCIDENT",

                "CRITICAL",

                "Critical mine safety incident",

                (
                    f"Critical incident reported: "
                    f"{incident_type}. "
                    f"Workers affected: "
                    f"{workers_affected}. "
                    f"Injured: {injured_count}, "
                    f"Missing: {missing_count}, "
                    f"Fatalities: {fatality_count}. "
                    f"Emergency response required."
                ),

                reported_at
            ))

        conn.commit()
        conn.close()

        audit(
            "Reported mine safety incident",
            "incident",
            incident_id,
            description
        )

        refresh_all_risk_scores()

        return redirect(
            url_for("incidents")
        )

    conn.close()

    # IMPORTANT:
    # Your actual filename is incidents_new.html

    return render_template(
        "incidents_new.html",
        mines=mines
    )


# ============================================================
# API — INCIDENTS
# ============================================================

@app.route(
    "/api/incidents"
)
def api_incidents():

    conn = get_db()

    incidents = conn.execute("""
        SELECT
            incidents.*,
            mines.name AS mine_name,
            mines.subsidiary,
            mines.state
        FROM incidents
        JOIN mines
            ON mines.id = incidents.mine_id
        ORDER BY incidents.id DESC
        LIMIT 100
    """).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in incidents
    ])


# ============================================================
# INCIDENT STATUS UPDATE
# ============================================================

@app.route(
    "/api/incidents/<int:incident_id>/close",
    methods=["POST"]
)
def close_incident(incident_id):

    if not session.get("logged_in"):

        return jsonify({
            "success": False,
            "message": "Login required."
        }), 401

    conn = get_db()

    incident = conn.execute("""
        SELECT *
        FROM incidents
        WHERE id=?
    """, (
        incident_id,
    )).fetchone()

    if not incident:

        conn.close()

        return jsonify({
            "success": False,
            "message": "Incident not found."
        }), 404

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn.execute("""
        UPDATE incidents
        SET
            emergency_status='RESOLVED',
            investigation_status='COMPLETED',
            closure_status='CLOSED',
            closed_at=?
        WHERE id=?
    """, (
        now,
        incident_id
    ))

    conn.commit()
    conn.close()

    audit(
        "Closed mine incident",
        "incident",
        incident_id,
        "Incident marked CLOSED"
    )

    refresh_all_risk_scores()

    return jsonify({
        "success": True,
        "message": "Incident closed successfully."
    })


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        username = request.form.get(
            "username"
        )

        password = request.form.get(
            "password"
        )

        users = {

            "admin": {

                "password":
                    "admin123",

                "role":
                    "admin"
            },

            "inspector": {

                "password":
                    "inspect123",

                "role":
                    "inspector"
            },

            "mine": {

                "password":
                    "mine123",

                "role":
                    "mine"
            }
        }

        user = users.get(
            username
        )

        if (
            user
            and user["password"] == password
        ):

            session["logged_in"] = True

            session["username"] = (
                username
            )

            session["role"] = (
                user["role"]
            )

            audit(

                "User login",

                "user",

                None,

                username
            )

            if user["role"] == "inspector":

                return redirect(
                    url_for("inspector")
                )

            if user["role"] == "mine":

                return redirect(
                    url_for("mine_portal")
                )

            return redirect(
                url_for("dashboard")
            )

        return render_template(

            "login.html",

            error=
                "Invalid username or password."
        )

    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    username = session.get(
        "username",
        "unknown"
    )

    audit(

        "User logout",

        "user",

        None,

        username
    )

    session.clear()

    return redirect(
        url_for("dashboard")
    )


# ============================================================
# HEALTH / STATUS
# ============================================================

@app.route("/api/status")
def api_status():

    conn = get_db()

    mine_count = conn.execute("""
        SELECT COUNT(*)
        FROM mines
    """).fetchone()[0]

    environmental_count = conn.execute("""
        SELECT COUNT(*)
        FROM environmental_data
    """).fetchone()[0]

    incident_count = conn.execute("""
        SELECT COUNT(*)
        FROM incidents
    """).fetchone()[0]

    alert_count = conn.execute("""
        SELECT COUNT(*)
        FROM alerts
        WHERE status='OPEN'
    """).fetchone()[0]

    conn.close()

    return jsonify({

        "platform":
            "SmartCoal Governance & Intelligence Platform",

        "status":
            "Governance Network Online",

        "ml_available":
            ML_AVAILABLE,

        "mine_count":
            mine_count,

        "environmental_records":
            environmental_count,

        "incidents":
            incident_count,

        "open_alerts":
            alert_count,

        "environment":
            get_system_status(),

        "timestamp":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
    })


# ============================================================
# STARTUP
# ============================================================

init_db()


if __name__ == "__main__":

    print()
    print("=" * 60)
    print(" SmartCoal Governance & Intelligence Platform")
    print("=" * 60)
    print(
        " ML available:",
        ML_AVAILABLE
    )
    print(
        " CAAQMS:",
        CAAQMS_URL
    )
    print(
        " Database:",
        DB
    )
    print("=" * 60)
    print()

    app.run(
        debug=True
    )