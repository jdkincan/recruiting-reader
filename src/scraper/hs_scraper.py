import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.utils.utils import body_text

def scrape_hs_recruiting_page(driver, hs_url: str):
    driver.get(hs_url)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//h1")))
    txt = body_text(driver)

    # ---- Normalize into clean lines ----
    raw_lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    # Remove css/garbage lines like ".st0{fill-rule:...}"
    lines = []
    for ln in raw_lines:
        if ln.startswith(".") and "{" in ln and "}" in ln:
            continue
        if "fill-rule" in ln or "clip-rule" in ln or "st0{" in ln:
            continue
        lines.append(ln)

    # Helper: find first index of a token (case-insensitive)
    def idx_of(token: str):
        token_u = token.upper()
        for i, ln in enumerate(lines):
            if ln.upper() == token_u:
                return i
        return None

    # ---- CLASS ----
    hs_class = None
    i = idx_of("CLASS")
    if i is not None and i + 1 < len(lines) and lines[i+1].isdigit():
        hs_class = int(lines[i+1])

    # ---- 247SPORTS block (non-composite) ----
    hs_rating_247 = None
    hs_natl_rank = None
    hs_pos = None
    hs_pos_rank = None

    i247 = idx_of("247SPORTS")
    if i247 is not None:
        # Next numeric line after 247SPORTS is rating
        for j in range(i247 + 1, min(i247 + 10, len(lines))):
            if re.fullmatch(r"\d{1,3}", lines[j]):
                hs_rating_247 = int(lines[j])
                break

    inatl = idx_of("NATL.")
    if inatl is not None:
        # Next numeric line after NATL. is natl rank
        for j in range(inatl + 1, min(inatl + 6, len(lines))):
            if re.fullmatch(r"\d{1,6}", lines[j]):
                hs_natl_rank = int(lines[j])
                # Next token+number pair after natl is position + pos rank (skip state line later)
                # Find first [A-Z]{1,4} then number
                for k in range(j + 1, min(j + 10, len(lines))):
                    if re.fullmatch(r"[A-Z]{1,4}", lines[k]):
                        # avoid "CA", "TX" etc being misread as position only if it's two letters AND appears after QB line
                        # but for HS pages this first one after natl is usually position (QB/WR/RB/ATH/CB/S/LB/EDGE/OT/IOL/DL)
                        if k + 1 < len(lines) and re.fullmatch(r"\d{1,6}", lines[k+1]):
                            hs_pos = lines[k].upper()
                            hs_pos_rank = int(lines[k+1])
                            break
                break

    # ---- 247SPORTS COMPOSITE® block ----
    composite_rating = None
    composite_natl = None
    composite_pos = None
    composite_pos_rank = None

    # Find "247SPORTS COMPOSITE®" or "247SPORTS COMPOSITE"
    icomp = None
    for token in ["247SPORTS COMPOSITE®", "247SPORTS COMPOSITE"]:
        icomp = idx_of(token)
        if icomp is not None:
            break

    if icomp is not None:
        # Next float after comp token is rating (0.9981)
        for j in range(icomp + 1, min(icomp + 12, len(lines))):
            if re.fullmatch(r"\d\.\d+", lines[j]):
                composite_rating = float(lines[j])
                break
        # Find NATL. after composite header (search forward)
        for j in range(icomp, min(icomp + 30, len(lines))):
            if lines[j].upper() == "NATL.":
                # next numeric is composite natl rank
                for k in range(j + 1, min(j + 6, len(lines))):
                    if re.fullmatch(r"\d{1,6}", lines[k]):
                        composite_natl = int(lines[k])
                        # next token+number is composite pos + rank
                        for t in range(k + 1, min(k + 12, len(lines))):
                            if re.fullmatch(r"[A-Z]{1,4}", lines[t]) and t + 1 < len(lines) and re.fullmatch(r"\d{1,6}", lines[t+1]):
                                composite_pos = lines[t].upper()
                                composite_pos_rank = int(lines[t+1])
                                break
                        break
                break

    return {
        "hs_class": hs_class,
        "hs_rating_247": hs_rating_247,
        # "hs_natl_rank": hs_natl_rank,
        "hs_pos": hs_pos,
        # "hs_pos_rank": hs_pos_rank,
        "composite_rating": composite_rating,
        "composite_natl_rank": composite_natl,
        # "composite_pos": composite_pos,
        "composite_pos_rank": composite_pos_rank,
        # "hs_stars": hs_stars,
        "source_hs_url": hs_url
    }
