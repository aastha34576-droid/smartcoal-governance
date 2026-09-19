import sqlite3
import requests
import time
from bs4 import BeautifulSoup

DB = "smartcoal.db"

CAAQMS_URL = "https://apps.coalindia.in/ords/f?p=159:11"

# -------------------------------------------------------------------
# OFFICIAL CAAQMS MONITORED MINE NAMES
#
# These are additional mine / mining-project names identified from
# Coal India CAAQMS records.
#
# Governance values are NOT invented.
# New records are inserted as DATA PENDING.
# -------------------------------------------------------------------

MINES = [

    # ================================================================
    # SECL
    # ================================================================

    {
        "name": "Amgaon Open Cast Mine",
        "subsidiary": "SECL",
        "state": "Chhattisgarh",
        "lat": 23.2400,
        "lon": 82.1800
    },

    {
        "name": "Amadand OC Mine Project",
        "subsidiary": "SECL",
        "state": "Madhya Pradesh",
        "lat": 23.1000,
        "lon": 81.9300
    },

    {
        "name": "Pali Underground Mine",
        "subsidiary": "SECL",
        "state": "Chhattisgarh",
        "lat": 22.9500,
        "lon": 82.1100
    },

    {
        "name": "Gevra Opencast Coal Mine",
        "subsidiary": "SECL",
        "state": "Chhattisgarh",
        "lat": 22.336312,
        "lon": 82.545748
    },

    {
        "name": "Kusmunda Coal Mine",
        "subsidiary": "SECL",
        "state": "Chhattisgarh",
        "lat": 22.332635,
        "lon": 82.666666
    },

    {
        "name": "Dipka Expansion Project",
        "subsidiary": "SECL",
        "state": "Chhattisgarh",
        "lat": 22.345077,
        "lon": 82.544192
    },

    {
        "name": "Chirimiri Area Mine",
        "subsidiary": "SECL",
        "state": "Chhattisgarh",
        "lat": 23.1900,
        "lon": 82.3500
    },

    {
        "name": "Jamuna Kotma Mine",
        "subsidiary": "SECL",
        "state": "Madhya Pradesh",
        "lat": 23.1800,
        "lon": 81.9500
    },

    {
        "name": "Bishrampur Mine",
        "subsidiary": "SECL",
        "state": "Chhattisgarh",
        "lat": 23.2000,
        "lon": 83.2500
    },

    {
        "name": "Baikunthpur Mine",
        "subsidiary": "SECL",
        "state": "Chhattisgarh",
        "lat": 23.2500,
        "lon": 82.5600
    },


    # ================================================================
    # MCL
    # ================================================================

    {
        "name": "Lakhanpur OCP",
        "subsidiary": "MCL",
        "state": "Odisha",
        "lat": 21.7451,
        "lon": 83.8401
    },

    {
        "name": "Basundhara West Coal Mine",
        "subsidiary": "MCL",
        "state": "Odisha",
        "lat": 22.059284,
        "lon": 83.7304
    },

    {
        "name": "Bhubaneswari Coal Mine",
        "subsidiary": "MCL",
        "state": "Odisha",
        "lat": 20.961693,
        "lon": 85.160099
    },

    {
        "name": "Samaleswari OCP",
        "subsidiary": "MCL",
        "state": "Odisha",
        "lat": 21.8200,
        "lon": 83.9500
    },

    {
        "name": "Lajkura OCP",
        "subsidiary": "MCL",
        "state": "Odisha",
        "lat": 21.8200,
        "lon": 83.9200
    },


    # ================================================================
    # NCL
    # ================================================================

    {
        "name": "Jayant Coal Mine",
        "subsidiary": "NCL",
        "state": "Madhya Pradesh",
        "lat": 24.1583,
        "lon": 82.6546
    },

    {
        "name": "Nigahi Coal Mine",
        "subsidiary": "NCL",
        "state": "Madhya Pradesh",
        "lat": 24.1350,
        "lon": 82.599444
    },

    {
        "name": "Dudhichua Coal Mine",
        "subsidiary": "NCL",
        "state": "Uttar Pradesh",
        "lat": 24.16474,
        "lon": 82.67287
    },

    {
        "name": "Bina Coal Mine",
        "subsidiary": "NCL",
        "state": "Madhya Pradesh",
        "lat": 24.1700,
        "lon": 82.6300
    },

    {
        "name": "Kakri Coal Mine",
        "subsidiary": "NCL",
        "state": "Uttar Pradesh",
        "lat": 24.1200,
        "lon": 82.7000
    },

    {
        "name": "NCL CETI",
        "subsidiary": "NCL",
        "state": "Madhya Pradesh",
        "lat": 24.2000,
        "lon": 82.6700
    },


    # ================================================================
    # WCL
    # ================================================================

    {
        "name": "Bhatadi Opencast Mine",
        "subsidiary": "WCL",
        "state": "Maharashtra",
        "lat": 20.0700,
        "lon": 79.2500
    },

    {
        "name": "Penganga Opencast Mine",
        "subsidiary": "WCL",
        "state": "Maharashtra",
        "lat": 20.0000,
        "lon": 78.8500
    },

    {
        "name": "Saoner UG Mine",
        "subsidiary": "WCL",
        "state": "Maharashtra",
        "lat": 21.3800,
        "lon": 78.9200
    },

    {
        "name": "Mungoli Nirguda Deep Expansion OC Mine",
        "subsidiary": "WCL",
        "state": "Maharashtra",
        "lat": 19.9300,
        "lon": 78.9500
    }

]



def normalize(value):
    return (
        str(value)
        .strip()
        .lower()
        .replace("opencast", "oc")
        .replace("open cast", "oc")
        .replace("  ", " ")
    )


def main():

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    existing = cursor.execute("""
        SELECT id, name, subsidiary
        FROM mines
    """).fetchall()

    existing_keys = {
        (
            normalize(row["name"]),
            normalize(row["subsidiary"])
        )
        for row in existing
    }

    added = 0
    skipped = 0

    for mine in MINES:

        key = (
            normalize(mine["name"]),
            normalize(mine["subsidiary"])
        )

        if key in existing_keys:
            print(
                f"SKIP     : {mine['name']} "
                f"({mine['subsidiary']})"
            )
            skipped += 1
            continue

        cursor.execute("""
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
        """, (
            mine["name"],
            mine["subsidiary"],
            mine["state"],
            mine["lat"],
            mine["lon"],
            0,
            0,
            "DATA PENDING"
        ))

        print(
            f"ADDED    : {mine['name']} "
            f"({mine['subsidiary']})"
        )

        added += 1

    conn.commit()

    total = cursor.execute("""
        SELECT COUNT(*)
        FROM mines
    """).fetchone()[0]

    conn.close()

    print()
    print("=" * 55)
    print(f"NEW MINES ADDED : {added}")
    print(f"ALREADY PRESENT  : {skipped}")
    print(f"TOTAL MINES      : {total}")
    print("=" * 55)


if __name__ == "__main__":
    main()