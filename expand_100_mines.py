import sqlite3
import time
import requests
from urllib.parse import quote

DB_NAME = "smartcoal.db"

# ============================================================
# SMARTCOAL 100+ MINE REGISTRY
#
# These are registry records.
# We DO NOT invent compliance, inspection or risk values.
#
# Coordinates are obtained through geocoding at import time.
# If a mine cannot be confidently geocoded, it is NOT inserted
# with a fake coordinate.
# ============================================================

MINES = [

    # ========================================================
    # EASTERN COALFIELDS LIMITED
    # ========================================================

    ("Mugma Area", "ECL", "West Bengal"),
    ("Salanpur Area", "ECL", "West Bengal"),
    ("Sodepur Area", "ECL", "West Bengal"),
    ("Satgram Area", "ECL", "West Bengal"),
    ("Sripur Area", "ECL", "West Bengal"),
    ("Kenda Area", "ECL", "West Bengal"),
    ("Bankola Area", "ECL", "West Bengal"),
    ("Kajora Area", "ECL", "West Bengal"),
    ("Pandaveswar Area", "ECL", "West Bengal"),
    ("Jhanjra Project", "ECL", "West Bengal"),
    ("Kunustoria Area", "ECL", "West Bengal"),
    ("Khottadih Project", "ECL", "West Bengal"),
    ("Parasea Area", "ECL", "West Bengal"),
    ("Durgapur Area", "ECL", "West Bengal"),
    ("Bansra Area", "ECL", "West Bengal"),
    ("Kottadih Area", "ECL", "West Bengal"),

    # ========================================================
    # BHARAT COKING COAL LIMITED
    # ========================================================

    ("Barora Area", "BCCL", "Jharkhand"),
    ("Block II Area", "BCCL", "Jharkhand"),
    ("Govindpur Area", "BCCL", "Jharkhand"),
    ("Katras Area", "BCCL", "Jharkhand"),
    ("Sijua Area", "BCCL", "Jharkhand"),
    ("Kusunda Area", "BCCL", "Jharkhand"),
    ("Bastacolla Area", "BCCL", "Jharkhand"),
    ("Lodna Area", "BCCL", "Jharkhand"),
    ("EJ Area", "BCCL", "Jharkhand"),
    ("PB Area", "BCCL", "Jharkhand"),
    ("WJ Area", "BCCL", "Jharkhand"),
    ("CV Area", "BCCL", "Jharkhand"),
    ("Pootkee Balihari Area", "BCCL", "Jharkhand"),
    ("Western Jharia Area", "BCCL", "Jharkhand"),
    ("Eastern Jharia Area", "BCCL", "Jharkhand"),

    # ========================================================
    # CENTRAL COALFIELDS LIMITED
    # ========================================================

    ("Piparwar Area", "CCL", "Jharkhand"),
    ("Magadh Area", "CCL", "Jharkhand"),
    ("Amrapali Area", "CCL", "Jharkhand"),
    ("North Karanpura Area", "CCL", "Jharkhand"),
    ("Hazaribagh Area", "CCL", "Jharkhand"),
    ("Kuju Area", "CCL", "Jharkhand"),
    ("Rajrappa Area", "CCL", "Jharkhand"),
    ("Argada Area", "CCL", "Jharkhand"),
    ("Dhori Area", "CCL", "Jharkhand"),
    ("Bokaro and Kargali Area", "CCL", "Jharkhand"),
    ("Kathara Area", "CCL", "Jharkhand"),
    ("Rajhara Area", "CCL", "Jharkhand"),
    ("Giridih Area", "CCL", "Jharkhand"),
    ("Mandu Area", "CCL", "Jharkhand"),
    ("Churi Area", "CCL", "Jharkhand"),

    # ========================================================
    # MAHANADI COALFIELDS LIMITED
    # ========================================================

    ("Talcher Area", "MCL", "Odisha"),
    ("Jagannath Area", "MCL", "Odisha"),
    ("Kaniha Area", "MCL", "Odisha"),
    ("Hingula Area", "MCL", "Odisha"),
    ("Bharatpur Area", "MCL", "Odisha"),
    ("Lingaraj Area", "MCL", "Odisha"),
    ("Orient Area", "MCL", "Odisha"),
    ("IB Valley Area", "MCL", "Odisha"),
    ("Lakhanpur Area", "MCL", "Odisha"),
    ("Basundhara Area", "MCL", "Odisha"),
    ("Samaleswari Area", "MCL", "Odisha"),
    ("Lajkura Area", "MCL", "Odisha"),
    ("Bhubaneswari Area", "MCL", "Odisha"),

    # ========================================================
    # NORTHERN COALFIELDS LIMITED
    # ========================================================

    ("Jayant Area", "NCL", "Madhya Pradesh"),
    ("Nigahi Area", "NCL", "Madhya Pradesh"),
    ("Dudhichua Area", "NCL", "Uttar Pradesh"),
    ("Bina Area", "NCL", "Madhya Pradesh"),
    ("Kakri Area", "NCL", "Uttar Pradesh"),
    ("Kharia Area", "NCL", "Uttar Pradesh"),
    ("Krishnashila Area", "NCL", "Uttar Pradesh"),
    ("Block B Project", "NCL", "Madhya Pradesh"),
    ("Amlohri Area", "NCL", "Madhya Pradesh"),
    ("Jhingurda Area", "NCL", "Madhya Pradesh"),

    # ========================================================
    # SOUTH EASTERN COALFIELDS LIMITED
    # ========================================================

    ("Gevra Area", "SECL", "Chhattisgarh"),
    ("Kusmunda Area", "SECL", "Chhattisgarh"),
    ("Dipka Area", "SECL", "Chhattisgarh"),
    ("Korba Area", "SECL", "Chhattisgarh"),
    ("Chirimiri Area", "SECL", "Chhattisgarh"),
    ("Baikunthpur Area", "SECL", "Chhattisgarh"),
    ("Bishrampur Area", "SECL", "Chhattisgarh"),
    ("Sohagpur Area", "SECL", "Madhya Pradesh"),
    ("Johilla Area", "SECL", "Madhya Pradesh"),
    ("Hasdeo Area", "SECL", "Chhattisgarh"),
    ("Raigarh Area", "SECL", "Chhattisgarh"),
    ("Bhatgaon Area", "SECL", "Chhattisgarh"),
    ("Jamuna Kotma Area", "SECL", "Madhya Pradesh"),
    ("Anuppur Area", "SECL", "Madhya Pradesh"),
    ("Amgaon Area", "SECL", "Chhattisgarh"),
    ("Pali Area", "SECL", "Chhattisgarh"),

    # ========================================================
    # WESTERN COALFIELDS LIMITED
    # ========================================================

    ("Majri Area", "WCL", "Maharashtra"),
    ("Wani Area", "WCL", "Maharashtra"),
    ("Wani North Area", "WCL", "Maharashtra"),
    ("Umrer Area", "WCL", "Maharashtra"),
    ("Nagpur Area", "WCL", "Maharashtra"),
    ("Kamptee Area", "WCL", "Maharashtra"),
    ("Wardha Valley Area", "WCL", "Maharashtra"),
    ("Chandrapur Area", "WCL", "Maharashtra"),
    ("Ballarpur Area", "WCL", "Maharashtra"),
    ("Yavatmal Area", "WCL", "Maharashtra"),
    ("Penganga Area", "WCL", "Maharashtra"),
    ("Mungoli Area", "WCL", "Maharashtra"),
    ("Saoner Area", "WCL", "Maharashtra"),
    ("Pathakhera Area", "WCL", "Madhya Pradesh"),

    # ========================================================
    # NORTH EASTERN COALFIELDS
    # ========================================================

    ("Margherita Area", "NEC", "Assam"),
    ("Tikak Area", "NEC", "Assam"),
    ("Tirap Area", "NEC", "Assam"),

]


# ============================================================
# NORMALIZATION
# ============================================================

def normalize(text):
    return (
        str(text)
        .lower()
        .replace("coal mine", "")
        .replace("mine", "")
        .replace("project", "")
        .replace("area", "")
        .replace("opencast", "")
        .replace("open cast", "")
        .replace("underground", "")
        .replace("  ", " ")
        .strip()
    )


# ============================================================
# GEOCODING
# ============================================================

GEOCACHE = {}


def geocode_mine(name, subsidiary, state):

    key = f"{name}|{subsidiary}|{state}"

    if key in GEOCACHE:
        return GEOCACHE[key]

    queries = [
        f"{name}, {subsidiary}, {state}, India",
        f"{name}, {state}, India",
        f"{subsidiary} {name}, India",
    ]

    headers = {
        "User-Agent":
            "SmartCoal-Governance-Platform/1.0"
    }

    for query in queries:

        try:

            url = (
                "https://nominatim.openstreetmap.org/search"
                f"?q={quote(query)}"
                "&format=json"
                "&limit=1"
            )

            response = requests.get(
                url,
                headers=headers,
                timeout=15
            )

            if response.status_code != 200:
                continue

            data = response.json()

            if data:

                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])

                GEOCACHE[key] = (
                    lat,
                    lon
                )

                time.sleep(1.1)

                return (
                    lat,
                    lon
                )

        except Exception:
            pass

    GEOCACHE[key] = None

    return None


# ============================================================
# DATABASE
# ============================================================

conn = sqlite3.connect(DB_NAME)
conn.row_factory = sqlite3.Row

existing = conn.execute("""
    SELECT
        id,
        name,
        subsidiary,
        state,
        lat,
        lon
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
unresolved = []


for name, subsidiary, state in MINES:

    key = (
        normalize(name),
        normalize(subsidiary)
    )

    if key in existing_keys:

        print(
            f"SKIP     : {name} ({subsidiary})"
        )

        skipped += 1
        continue

    print(
        f"SEARCH   : {name} ({subsidiary})..."
    )

    coords = geocode_mine(
        name,
        subsidiary,
        state
    )

    if not coords:

        print(
            f"UNRESOLVED: {name} ({subsidiary})"
        )

        unresolved.append(
            (
                name,
                subsidiary,
                state
            )
        )

        continue

    lat, lon = coords

    conn.execute("""
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
        name,
        subsidiary,
        state,
        lat,
        lon,
        0,
        0,
        "DATA PENDING"
    ))

    conn.commit()

    print(
        f"ADDED    : {name} ({subsidiary})"
    )

    added += 1


total = conn.execute("""
    SELECT COUNT(*)
    FROM mines
""").fetchone()[0]


conn.close()


print()
print("=" * 65)
print(
    f"NEW MINES ADDED : {added}"
)
print(
    f"ALREADY PRESENT  : {skipped}"
)
print(
    f"UNRESOLVED       : {len(unresolved)}"
)
print(
    f"TOTAL MINES      : {total}"
)
print("=" * 65)


if unresolved:

    print()
    print("THESE WERE NOT INSERTED:")
    print("-" * 65)

    for name, subsidiary, state in unresolved:

        print(
            f"- {name} | {subsidiary} | {state}"
        )

    print()
    print(
        "No fake coordinates were created for unresolved mines."
    )