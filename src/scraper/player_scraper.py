import re
import time
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.config import DEBUG
from src.utils.utils import body_text, get_text, extract_player_id_247
from src.scraper.data_extractors import (extract_position, extract_transfer_block,
                                 open_timeline, timeline_lines, parse_timeline_events,
                                 get_ncaa_institutions, infer_origin_dest_from_timeline_events)

from src.scraper.hs_scraper import scrape_hs_recruiting_page

def scrape_player(driver, player_url: str):
    driver.get(player_url)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//h1")))
    txt = body_text(driver)

    name = get_text(driver, "//h1", timeout=10)
    pid = extract_player_id_247(player_url)

    # # Position from "POS QB"
    # pos = None
    # m_pos = re.search(r"\bPOS\s+([A-Z]{1,4})\b", txt)
    # if m_pos:
    #     pos = m_pos.group(1)

    pos = extract_position(driver) 


    # Prospect info (HS, City)
    hs_name = re.search(r"HIGH SCHOOL\s+([^\n]+)", txt).group(1).strip() if "HIGH SCHOOL" in txt else None
    city = re.search(r"CITY\s+([^\n]+)", txt).group(1).strip() if "CITY" in txt else None
    hs_city, hs_state = None, None
    if city and "," in city:
        hs_city = city.split(",")[0].strip()
        hs_state = city.split(",")[1].strip()

    # Transfer rankings block (your existing parser)
    t_rating, t_year, t_ovr, t_posrank = extract_transfer_block(txt, pos)

    # HS recruiting URL
    hs_url = None
    try:
        hs_url = driver.find_element(By.XPATH, "//a[contains(., 'View recruiting profile')]").get_attribute("href")
    except Exception:
        anchors = driver.find_elements(By.XPATH, "//a[contains(@href, '/high-school-')]")
        if anchors:
            hs_url = anchors[0].get_attribute("href")

    hs_data = {}
    if hs_url:
        hs_url = hs_url.split("?")[0].rstrip("/")
        hs_data = scrape_hs_recruiting_page(driver, hs_url)

    # ---- Timeline origin/destination ----
    # --- TIMELINE DEBUG CHECK (temporary, remove later) ---
    open_timeline(driver)
    txt2 = body_text(driver)

    lines = timeline_lines(txt2)
    events = parse_timeline_events(lines)

    # HARD ASSERT: we must see Transfer + Enrolled
    if not any(e.kind == "Transfer" for e in events):
        raise RuntimeError("Timeline parsed but no Transfer events found")

    if DEBUG and not any(e.kind == "Enrolled" for e in events):
        print("WARN: no Enrolled events; using commit-based fallback")

    # Optional debug print
    if DEBUG:
        print(f"\nTIMELINE CHECK for {name}")
        for e in events[:8]:
            print(e.date.strftime("%Y-%m-%d"), e.kind, "|", e.text)

    # canonical NCAA schools from institution list (may be hidden; click dropdown if empty)
    cands = get_ncaa_institutions(driver)
    if DEBUG:
        print("INSTITUTION CANDIDATES:", cands)
    if not cands:
        try:
            inst_btn = driver.find_element(By.CSS_SELECTOR, "button[data-js='institution-selector']")
            inst_btn.click()
            time.sleep(0.3)
        except Exception:
            pass
        cands = get_ncaa_institutions(driver)

    origin, dest, commit_dt = infer_origin_dest_from_timeline_events(
        events,
        candidates=cands,
        window_start=datetime(2024, 11, 15),
        window_end=datetime(2025, 8, 1),
    )

    portal_season_year = None
    if commit_dt:
        portal_season_year = commit_dt.year + 1 if commit_dt.month == 12 else commit_dt.year


    # Stars derived from rating (fast + consistent)
    def stars_from_rating(r):
        if r is None: return None
        if r >= 98: return 5
        if r >= 90: return 4
        if r >= 80: return 3
        if r <= 80: return 2
        return 0

    transfer_stars = stars_from_rating(t_rating)
    hs_stars = stars_from_rating(hs_data.get("hs_rating_247")) if hs_data else None

    return {
        "id_247": pid,
        "name": name,
        "pos_247": pos,
        "hs_name": hs_name,
        "hs_city": hs_city,
        "hs_state": hs_state,
        "transfer_rating": t_rating,
        "transfer_year": portal_season_year or t_year,   # prefer timeline-derived portal season year
        "transfer_ovr_rank": t_ovr,
        "transfer_pos_rank": t_posrank,
        "transfer_stars": transfer_stars,
        "transfer_origin": origin,
        "transfer_destination": dest,
        **hs_data,
        "hs_stars": hs_stars,
        "source_hs_url": hs_url,
        "source_player_url": player_url
    }
