import sqlite3
import random
from datetime import datetime, timedelta

DB = "smartcoal.db"

conn = sqlite3.connect(DB)

# ------------------------------------------------------------
# Historical environmental baseline
# ------------------------------------------------------------

mine_ids = [1, 2, 3, 4, 5]

now = datetime.now()

for mine_id in mine_ids:

    for i in range(15):

        timestamp = (
            now - timedelta(hours=(i + 1) * 6)
        ).strftime("%Y-%m-%d %H:%M:%S")

        # Normal historical environmental variation
        pm25 = round(random.uniform(12, 28), 2)
        pm10 = round(random.uniform(25, 60), 2)
        so2 = round(random.uniform(10, 30), 2)
        no2 = round(random.uniform(15, 40), 2)
        co = round(random.uniform(0.5, 2.5), 2)

        conn.execute("""
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
                created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mine_id,
            pm25,
            pm10,
            so2,
            no2,
            co,
            timestamp,
            "Historical Baseline",
            "Coal India",
            "Historical Monitoring Area",
            f"Mine {mine_id} Historical Station",
            f"baseline_{mine_id}",
            "ML Baseline"
        ))

conn.commit()
conn.close()

print("ML historical baseline created successfully.")
print("75 historical environmental observations added.")