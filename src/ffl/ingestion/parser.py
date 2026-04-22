"""
ATF FFL fixed-width text file parser.

The ATF publishes a fixed-width ASCII file (changed from tab-delimited in Sept 2013).
The file has a header row and a dashes separator row before data begins.
All fields are right-padded with spaces; encoding is latin-1 (ISO-8859-1).

Column positions derived from ATF source documentation and sample data analysis:
  Sample row: "9 82 005 01 7C 01714 GEBO INC       ACE HARDWARE & ELEMENT..."
"""

import logging
import re
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# (start_inclusive, end_exclusive) — 0-indexed, per pandas read_fwf convention
# Source: ATF fixed-width layout verified against sample data
ATF_COLSPECS = [
    (0,   1),    # lic_regn          — 1 char, ATF region (1–9)
    (2,   4),    # lic_dist          — 2 chars, IRS district
    (5,   8),    # lic_cnty          — 3 chars, FIPS county
    (9,  11),    # lic_type          — 2 chars, license type (01–11)
    (12, 14),    # lic_xprdte        — 2 chars, expiration encoding (digit + letter)
    (15, 20),    # lic_seqn          — 5 chars, sequence number
    (21, 46),    # app_license_name  — 25 chars, legal name (applicant)
    (46, 81),    # business_name     — 35 chars, DBA / trade name
    (81, 108),   # premise_street    — 27 chars
    (108, 130),  # premise_city      — 22 chars
    (130, 132),  # premise_state     — 2 chars
    (133, 142),  # premise_zip       — 9 chars (may include ZIP+4 with hyphen)
    (142, 169),  # mail_street       — 27 chars
    (169, 191),  # mail_city         — 22 chars
    (191, 193),  # mail_state        — 2 chars
    (194, 203),  # mail_zip          — 9 chars
    (203, 213),  # voice_phone       — 10 chars (digits only)
]

ATF_COLNAMES = [
    "lic_regn",
    "lic_dist",
    "lic_cnty",
    "lic_type",
    "lic_xprdte",
    "lic_seqn",
    "app_license_name",  # legal name
    "business_name",     # DBA / trade name
    "premise_street",
    "premise_city",
    "premise_state",
    "premise_zip",
    "mail_street",
    "mail_city",
    "mail_state",
    "mail_zip",
    "voice_phone",
]

VALID_LICENSE_TYPES = {"01", "02", "03", "06", "07", "08", "09", "10", "11"}

# ATF expiration month encoding: letter → month number (I is skipped)
MONTH_LETTER_MAP = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6,
    "G": 7, "H": 8, "J": 9, "K": 10, "L": 11, "M": 12,
}

_PO_BOX_RE = re.compile(r"^P\.?\s*O\.?\s*BOX", re.IGNORECASE)


def decode_expiration(xprdte: str | None) -> date | None:
    """
    Decode ATF 2-char expiration field to a date.

    Format: {last digit of year}{month letter}
    Example: '7C' → year ends in 7, month C = March → March of nearest matching year.
    The day is set to the last day of that month.
    """
    if not xprdte or len(xprdte) < 2:
        return None
    try:
        year_digit = int(xprdte[0])
        month = MONTH_LETTER_MAP.get(xprdte[1].upper())
        if month is None:
            return None
        today = date.today()
        decade_base = (today.year // 10) * 10
        year = decade_base + year_digit
        # If more than 3 years in the past, advance by 10 (next decade)
        if year < today.year - 3:
            year += 10
        # Last day of month
        if month == 12:
            last_day = date(year + 1, 1, 1).toordinal() - date(year, 12, 1).toordinal()
            last_day = 31
        else:
            last_day = (date(year, month + 1, 1).toordinal() - date(year, month, 1).toordinal())
        return date(year, month, last_day)
    except (ValueError, KeyError):
        return None


def build_ffl_number(row: pd.Series) -> str:
    """Construct canonical FFL number from the 6 ATF component fields."""
    parts = [
        str(row.get("lic_regn") or "").strip(),
        str(row.get("lic_dist") or "").strip(),
        str(row.get("lic_cnty") or "").strip(),
        str(row.get("lic_type") or "").strip(),
        str(row.get("lic_xprdte") or "").strip(),
        str(row.get("lic_seqn") or "").strip(),
    ]
    return "-".join(parts)


def normalize_zip(zip_raw: str | None) -> tuple[str | None, str | None]:
    """Return (zip5, zip4) from raw 9-char ZIP field."""
    if not zip_raw:
        return None, None
    cleaned = zip_raw.strip().replace("-", "")
    if len(cleaned) >= 9:
        return cleaned[:5], cleaned[5:9]
    if len(cleaned) == 5:
        return cleaned, None
    return cleaned or None, None


def is_po_box(street: str | None) -> bool:
    return bool(street and _PO_BOX_RE.match(street.strip()))


def parse_atf_file(path: Path) -> pd.DataFrame:
    """
    Parse an ATF fixed-width FFL text file into a normalized DataFrame.

    The file has a header row + dashes separator row before data (skiprows=2).
    Encoding is latin-1. All fields read as str to preserve leading zeros.

    Returns a DataFrame with ATF_COLNAMES columns plus:
      - ffl_number       (str)
      - expiration_date  (date | None)
      - premise_zip5     (str | None)
      - premise_zip4     (str | None)
      - mail_zip5        (str | None)
      - is_po_box_premise (bool)
    """
    logger.info("Parsing ATF file: %s", path)

    df = pd.read_fwf(
        path,
        colspecs=ATF_COLSPECS,
        names=ATF_COLNAMES,
        dtype=str,
        skiprows=2,
        encoding="latin-1",
        na_values=[""],
        keep_default_na=False,
    )

    # Strip whitespace from all string columns
    for col in df.columns:
        df[col] = df[col].where(df[col].isna(), df[col].str.strip())

    # Replace empty strings with None
    df = df.replace({"": None})

    # Drop rows missing essential fields
    df = df.dropna(subset=["app_license_name", "lic_type"])

    # Keep only known license types
    df = df[df["lic_type"].isin(VALID_LICENSE_TYPES)].copy()

    if df.empty:
        logger.warning("No valid records found after filtering")
        return df

    # Derive FFL number
    df["ffl_number"] = df.apply(build_ffl_number, axis=1)

    # Decode expiration date
    df["expiration_date"] = df["lic_xprdte"].apply(decode_expiration)

    # Normalize ZIP codes
    zip_parsed = df["premise_zip"].apply(normalize_zip)
    df["premise_zip5"] = zip_parsed.apply(lambda x: x[0])
    df["premise_zip4"] = zip_parsed.apply(lambda x: x[1])

    mail_zip_parsed = df["mail_zip"].apply(normalize_zip)
    df["mail_zip5"] = mail_zip_parsed.apply(lambda x: x[0])

    # Flag PO box premise addresses (exclude from geocoding)
    df["is_po_box_premise"] = df["premise_street"].apply(is_po_box)

    # Clean phone to digits only
    df["voice_phone"] = df["voice_phone"].str.replace(r"\D", "", regex=True).str[:10]

    logger.info("Parsed %d valid FFL records from %s", len(df), path)
    return df
