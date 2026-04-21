"""
Seed Script
Run: python scripts/seed.py --file path/to/profiles.json

Reads the seed JSON file and bulk inserts profiles into the DB.
Idempotent - skips names that already exist.

Seed file shape:
    {
        "profiles": [ { "name": "...", "gender": "...", ... }, ... ]
    }

Age group policy:
    Database uses Stage 1 age groups: child, teenager, adult, senior.
    age_group is always recomputed from age - seed file values are never trusted.
"""

import json
import sys
import argparse
from datetime import datetime, timezone

sys.path.insert(0, ".")

from sqlmodel import Session, select
from app.db.database import engine, create_db_and_tables
from app.models.profile import Profile, generate_uuid7


VALID_GENDERS = {"male", "female"}
BATCH_SIZE = 100


def classify_age_group(age: int) -> str:
    """
    Stage 1 age classification used for persistence.
    child: 0-12, teenager: 13-19, adult: 20-59, senior: 60+
    """
    if age <= 12:
        return "child"
    elif age <= 19:
        return "teenager"
    elif age <= 59:
        return "adult"
    else:
        return "senior"


def normalize_country_id(raw: str) -> str | None:
    cleaned = raw.strip().upper()
    if len(cleaned) == 2 and cleaned.isalpha():
        return cleaned
    return None


def load_records(file_path: str) -> list:
    """
    Loads records from the seed file.
    Handles both shapes:
      - {"profiles": [...]}   ← actual seed file shape
      - [...]                 ← raw array fallback
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        # Try known key first, then fall back to first list value found
        if "profiles" in data:
            return data["profiles"]
        for v in data.values():
            if isinstance(v, list):
                return v

    print("❌ Could not find a list of records in the seed file.")
    sys.exit(1)


def seed(file_path: str):
    create_db_and_tables()

    records = load_records(file_path)

    if not records:
        print("❌ Seed file contains no records.")
        sys.exit(1)

    print(f"📦 Processing {len(records)} records...")

    inserted = 0
    skipped = 0
    seen_in_run: set[str] = set()

    with Session(engine) as session:
        batch_count = 0

        for i, item in enumerate(records):
            try:
                # ── Name ──────────────────────────────────────────────────
                raw_name = item.get("name", "")
                if not isinstance(raw_name, str) or not raw_name.strip():
                    print(f"  ⚠ Record {i}: missing or invalid name — skipped")
                    skipped += 1
                    continue

                name = raw_name.strip().lower()

                if name in seen_in_run:
                    print(f"  ⚠ Record {i} ('{name}'): duplicate within seed file — skipped")
                    skipped += 1
                    continue

                existing = session.exec(
                    select(Profile).where(Profile.name == name)
                ).first()
                if existing:
                    seen_in_run.add(name)
                    skipped += 1
                    continue

                # ── Gender ────────────────────────────────────────────────
                gender = item.get("gender")
                if not gender or gender not in VALID_GENDERS:
                    print(f"  ⚠ Record {i} ('{name}'): null or invalid gender '{gender}' — skipped")
                    skipped += 1
                    continue

                # ── Age ───────────────────────────────────────────────────
                age = item.get("age")
                if age is None:
                    print(f"  ⚠ Record {i} ('{name}'): null age — skipped")
                    skipped += 1
                    continue
                age = int(age)

                # ── Country ───────────────────────────────────────────────
                country_id = normalize_country_id(item.get("country_id", ""))
                if not country_id:
                    print(f"  ⚠ Record {i} ('{name}'): invalid country_id '{item.get('country_id')}' — skipped")
                    skipped += 1
                    continue

                country_name = item.get("country_name", "").strip()
                if not country_name:
                    print(f"  ⚠ Record {i} ('{name}'): missing country_name — skipped")
                    skipped += 1
                    continue

                # ── Build and insert ──────────────────────────────────────
                profile = Profile(
                    id=generate_uuid7(),
                    name=name,
                    gender=gender,
                    gender_probability=float(item.get("gender_probability", 0.0)),
                    age=age,
                    # Always recompute - never trust seed file's age_group value.
                    age_group=classify_age_group(age),
                    country_id=country_id,
                    country_name=country_name,
                    country_probability=float(item.get("country_probability", 0.0)),
                    created_at=datetime.now(timezone.utc),
                )

                session.add(profile)
                seen_in_run.add(name)
                inserted += 1
                batch_count += 1

                if batch_count >= BATCH_SIZE:
                    session.commit()
                    batch_count = 0
                    print(f"  ✓ Committed batch ({inserted} inserted so far)")

            except Exception as e:
                print(f"  ❌ Record {i}: unexpected error — {e} — skipped")
                session.rollback()
                skipped += 1
                continue

        if batch_count > 0:
            session.commit()

    print(f"\n✅ Seeding complete: {inserted} inserted, {skipped} skipped.")
    return inserted, skipped


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed profiles database")
    parser.add_argument("--file", required=True, help="Path to JSON seed file")
    args = parser.parse_args()
    seed(args.file)