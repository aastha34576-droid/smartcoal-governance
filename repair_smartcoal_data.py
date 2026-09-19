
import sqlite3

DB = "smartcoal.db"


def table_columns(cur, table):
    return [
        row[1]
        for row in cur.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()
    ]


def add_column_if_missing(cur, table, column, definition):
    cols = table_columns(cur, table)

    if column not in cols:
        cur.execute(
            f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}'
        )
        print(f"Added {table}.{column}")


def clean_text(value):
    return str(value or "").strip().lower()


def main():

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print()
    print("==========================================")
    print(" SMARTCOAL DATA REPAIR")
    print("==========================================")
    print()

    # ============================================================
    # 1. ADD SAFE DATA-METADATA COLUMNS
    # ============================================================

    add_column_if_missing(
        cur,
        "mines",
        "data_source",
        "TEXT"
    )

    add_column_if_missing(
        cur,
        "mines",
        "data_confidence",
        "TEXT"
    )

    add_column_if_missing(
        cur,
        "mines",
        "environmental_status",
        "TEXT"
    )

    add_column_if_missing(
        cur,
        "mines",
        "last_live_update",
        "TEXT"
    )

    add_column_if_missing(
        cur,
        "mines",
        "governance_status",
        "TEXT"
    )

    add_column_if_missing(
        cur,
        "environmental_data",
        "data_status",
        "TEXT"
    )

    add_column_if_missing(
        cur,
        "environmental_data",
        "data_confidence",
        "TEXT"
    )

    print()
    print("Metadata columns checked.")
    print()

    # ============================================================
    # 2. CLASSIFY ENVIRONMENTAL DATA
    #
    # LIVE     = official CAAQMS
    # BASELINE = historical / ML baseline / legacy data
    # UNKNOWN  = unverified
    # ============================================================

    env_rows = cur.execute(
        "SELECT * FROM environmental_data"
    ).fetchall()

    live_count = 0
    baseline_count = 0
    unknown_count = 0

    for row in env_rows:

        source = clean_text(
            row["source"]
            if "source" in row.keys()
            else ""
        )

        raw_text = " ".join(
            clean_text(row[key])
            for key in row.keys()
        )

        # Official CAAQMS
        if (
            "caaqms" in source
            or "coal india caaqms" in raw_text
        ):

            status = "LIVE"
            confidence = "OFFICIAL_LIVE"

            live_count += 1

        # Historical / ML baseline
        elif (
            "historical baseline" in source
            or "ml baseline" in raw_text
            or "historical monitoring" in raw_text
        ):

            status = "BASELINE"
            confidence = "HISTORICAL_BASELINE"

            baseline_count += 1

        # Old environmental portal data
        elif (
            "coal india environmental monitoring portal"
            in source
        ):

            status = "BASELINE"
            confidence = "LEGACY_PORTAL_BASELINE"

            baseline_count += 1

        # Anything else
        else:

            status = "UNKNOWN"
            confidence = "UNVERIFIED"

            unknown_count += 1

        cur.execute(
            """
            UPDATE environmental_data
            SET data_status = ?,
                data_confidence = ?
            WHERE id = ?
            """,
            (
                status,
                confidence,
                row["id"]
            )
        )

    print("Environmental records classified.")
    print()

    # ============================================================
    # 3. UPDATE EACH MINE
    #
    # LIVE:
    #   Has official CAAQMS data.
    #
    # BASELINE:
    #   Has only historical data.
    #
    # NO_DATA:
    #   Has no environmental data.
    # ============================================================

    mines = cur.execute(
        "SELECT * FROM mines ORDER BY id"
    ).fetchall()

    for mine in mines:

        mine_id = mine["id"]

        # --------------------------------------------------------
        # Find latest official LIVE environmental record
        # --------------------------------------------------------

        live_record = cur.execute(
            """
            SELECT MAX(recorded_at)
            FROM environmental_data
            WHERE mine_id = ?
              AND data_status = 'LIVE'
            """,
            (mine_id,)
        ).fetchone()[0]

        # --------------------------------------------------------
        # Check whether any environmental data exists
        # --------------------------------------------------------

        total_env = cur.execute(
            """
            SELECT COUNT(*)
            FROM environmental_data
            WHERE mine_id = ?
            """,
            (mine_id,)
        ).fetchone()[0]

        # --------------------------------------------------------
        # Determine environmental status
        # --------------------------------------------------------

        if live_record:

            environmental_status = "LIVE"
            last_live_update = live_record

        elif total_env > 0:

            environmental_status = "BASELINE"
            last_live_update = None

        else:

            environmental_status = "NO_DATA"
            last_live_update = None

        # --------------------------------------------------------
        # Determine source/confidence
        # --------------------------------------------------------

        if live_record:

            data_source = "Coal India CAAQMS"
            data_confidence = "OFFICIAL_LIVE"

        elif total_env > 0:

            data_source = "Historical / legacy environmental data"
            data_confidence = "BASELINE_ONLY"

        else:

            data_source = "No environmental source connected"
            data_confidence = "NO_DATA"

        # ========================================================
        # GOVERNANCE DATA
        #
        # Compliance = 0 was being used as a placeholder.
        #
        # We DO NOT want:
        #
        # compliance 0
        # risk 30
        # LOW
        #
        # to look like a real assessment.
        # ========================================================

        compliance = mine["compliance"]

        if (
            compliance is None
            or float(compliance) <= 0
        ):

            cur.execute(
                """
                UPDATE mines
                SET compliance = NULL,
                    risk_score = NULL,
                    status = 'NO_DATA',
                    data_source = ?,
                    data_confidence = ?,
                    environmental_status = ?,
                    last_live_update = ?,
                    governance_status = 'NO_DATA'
                WHERE id = ?
                """,
                (
                    data_source,
                    data_confidence,
                    environmental_status,
                    last_live_update,
                    mine_id
                )
            )

        else:

            # Preserve the existing assessed risk.
            risk = mine["risk_score"]

            if risk is None:

                risk = 100 - float(compliance)

            # Keep risk between 0 and 100.
            risk = int(
                round(
                    max(
                        0,
                        min(
                            100,
                            float(risk)
                        )
                    )
                )
            )

            # ----------------------------------------------------
            # SINGLE RISK CLASSIFICATION
            # ----------------------------------------------------

            if risk >= 75:

                risk_status = "HIGH"

            elif risk >= 50:

                risk_status = "MEDIUM"

            else:

                risk_status = "LOW"

            cur.execute(
                """
                UPDATE mines
                SET risk_score = ?,
                    status = ?,
                    data_source = ?,
                    data_confidence = ?,
                    environmental_status = ?,
                    last_live_update = ?,
                    governance_status = 'ASSESSED'
                WHERE id = ?
                """,
                (
                    risk,
                    risk_status,
                    data_source,
                    data_confidence,
                    environmental_status,
                    last_live_update,
                    mine_id
                )
            )

    print("Mine records repaired.")
    print()

    # ============================================================
    # 4. INDEXES
    # ============================================================

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_env_mine_status
        ON environmental_data(mine_id, data_status)
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_mines_risk_status
        ON mines(status)
        """
    )

    conn.commit()

    # ============================================================
    # 5. FINAL REPORT
    # ============================================================

    mine_count = cur.execute(
        "SELECT COUNT(*) FROM mines"
    ).fetchone()[0]

    env_count = cur.execute(
        "SELECT COUNT(*) FROM environmental_data"
    ).fetchone()[0]

    print()
    print("==========================================")
    print(" REPAIR COMPLETE")
    print("==========================================")
    print()

    print(f"Total mines: {mine_count}")
    print(f"Environmental records: {env_count}")
    print(f"LIVE environmental records: {live_count}")
    print(f"BASELINE environmental records: {baseline_count}")
    print(f"UNKNOWN environmental records: {unknown_count}")

    print()
    print("==========================================")
    print(" MINE STATUS")
    print("==========================================")

    for row in cur.execute(
        """
        SELECT status, COUNT(*)
        FROM mines
        GROUP BY status
        ORDER BY status
        """
    ):

        print(
            f"{row[0]}: {row[1]}"
        )

    print()
    print("==========================================")
    print(" ENVIRONMENTAL STATUS")
    print("==========================================")

    for row in cur.execute(
        """
        SELECT data_status, COUNT(*)
        FROM environmental_data
        GROUP BY data_status
        ORDER BY data_status
        """
    ):

        print(
            f"{row[0]}: {row[1]}"
        )

    print()
    print("==========================================")
    print(" SAMPLE MINES")
    print("==========================================")

    for row in cur.execute(
        """
        SELECT
            id,
            name,
            compliance,
            risk_score,
            status,
            environmental_status,
            data_confidence
        FROM mines
        ORDER BY id
        LIMIT 15
        """
    ):

        print(
            tuple(row)
        )

    print()
    print("==========================================")

    conn.close()


if __name__ == "__main__":
    main()
