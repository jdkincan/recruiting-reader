import re
import time

from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.config import DATE_LINE_RE
from src.config import SCHOOL_EVENT_RE

# helper functions for web scraping with selenium
def get_text(driver, xpath, timeout=10):
    el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))
    return el.text.strip()

def body_text(driver):
    return driver.find_element(By.TAG_NAME, "body").text

def extract_player_id_247(url: str):
    m = re.search(r"/player/[^/]+-(\d+)", url)
    return int(m.group(1)) if m else None

def _has_date_lines(driver) -> bool:
    try:
        txt = driver.find_element(By.TAG_NAME, "body").text
        return DATE_LINE_RE.search(txt) is not None
    except Exception:
        return False
    
def is_school_event(text: str) -> bool:
    return bool(text) and SCHOOL_EVENT_RE.search(text) is not None

def most_recent_other(candidates, exclude=None):
    for c in candidates or []:
        if c and c != exclude:
            return c
    return None