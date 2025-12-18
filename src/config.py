import re
from datetime import datetime
from dataclasses import dataclass

@dataclass
class TL:
    date: datetime
    kind: str
    text: str


WORKERS = 6  # M4 Pro 24GB: 6 is a good start (use 4 if you see RAM pressure)
HEADLESS = True
CACHE_PATH = "data/portal_cache_2025_1217_run2.jsonl"

PORTAL_2025 = "https://247sports.com/season/2025-football/transferportaltop/"
PORTAL_2024 = "https://247sports.com/season/2024-football/transferportaltop/"
DEBUG = False

DATE_LINE_RE = re.compile(r"[A-Za-z]{3}\s+\d{1,2},\s+20\d{2}:\s*\w+")

DATE_RE = re.compile(r"^([A-Za-z]{3}\s+\d{1,2},\s+\d{4}):\s*(.+)$")