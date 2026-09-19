import sqlite3

DB_NAME = "smartcoal.db"

# ============================================================
# SMARTCOAL - VERIFIED MINE DATABASE EXPANSION
# ============================================================

MINES = [
    {
        "name": "Gevra Coal Mine",
        "subsidiary": "SECL",
        "state": "Chhattisgarh",
        "lat": 22.336312,
        "lon": 82.545748,
    },
    {
        "name": "Kusmunda Coal Mine",
        "subsidiary": "SECL",
        "state": "Chhattisgarh",
        "lat": 22.332635,
        "lon": 82.666666,
    },
    {
        "name": "Dipka Coal Mine",
        "subsidiary": "SECL",
        "state": "Chhattisgarh",
        "lat": 22.345077,
        "lon": 82.544192,
    },
    {
        "name": "Lakhanpur Coal Mine",
        "subsidiary": "MCL",
        "state": "Odisha",
        "lat": 21.7451,
        "lon": 83.8401,
    },
    {
        "name": "Basundhara (West) Coal Mine",
        "subsidiary": "MCL",
        "state": "Odisha",
        "lat": 22.059284,
        "lon": 83.7304,
    },
    {
        "name": "Bhubaneswari Coal Mine",
        "subsidiary": "MCL",
        "state": "Odisha",
        "lat": 20.961693,
        "lon": 85.160099,
    },
    {
        "name": "Jayant Coal Mine",
        "subsidiary": "NCL",
        "state": "Madhya Pradesh",
        "lat": 24.1583,
        "lon": 82.6546,
    },
    {
        "name": "Nigahi Coal Mine",
        "subsidiary": "NCL",
        "state": "Madhya Pradesh",
        "lat": 24.135,
        "lon": 82.599444,
    },
    {
        "name": "Dudhichua Coal Mine",
        "subsidiary": "NCL",
        "state": "Uttar Pradesh",
        "lat": 24.16474,
        "lon": 82.67287,
    },
    {
        "name": "Bina Coal Mine",
        "subsidiary": "NCL",
        "state": "Madhya Pradesh",
        "lat": 24.17,
        "lon": 82.63,
    },
]


def add_mines():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row

    inserted = 0
    skipped = 0

    try:
        for mine in MINES:

            existing = conn.execute(
                """
                SELECT id
                FROM mines
                WHERE LOWER(name) = LOWER(?)
                  AND LOWER(subsidiary) = LOWER(?)
                LIMIT 1
                """,
                (
                    mine["name"],
                    mine["subsidiary"],
                ),
            ).fetchone()

            if existing:
                skipped += 1

                print(
                    f"SKIPPED  : {mine['name']} "
                    f"({mine['subsidiary']}) - already exists"
                )

                continue

            conn.execute(
                """
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
                """,
                (
                    mine["name"],
                    mine["subsidiary"],
                    mine["state"],
                    mine["lat"],
                    mine["lon"],
                    0,
                    0,
                    "DATA PENDING",
                ),
            )

            inserted += 1

            print(
                f"ADDED    : {mine['name']} "
                f"({mine['subsidiary']})"
            )

        conn.commit()

        total = conn.execute(
            "SELECT COUNT(*) FROM mines"
        ).fetchone()[0]

        print()
        print("=" * 60)
        print("SMARTCOAL MINE DATABASE UPDATE COMPLETE")
        print("=" * 60)
        print(f"New mines added : {inserted}")
        print(f"Already present : {skipped}")
        print(f"Total mines now : {total}")
        print("=" * 60)

    except Exception as exc:
        conn.rollback()

        print()
        print("DATABASE UPDATE FAILED")
        print(f"Reason: {exc}")

        raise

    finally:
        conn.close()


if __name__ == "__main__":
    add_mines()