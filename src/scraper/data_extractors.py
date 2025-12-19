import re
import time
from datetime import datetime

from rapidfuzz import process, fuzz

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.config import TL
from src.config import DATE_RE

from src.utils.utils import body_text
from src.utils.utils import _has_date_lines
from src.utils.utils import is_school_event
from src.utils.utils import most_recent_other


# extract transfer elements
def extract_transfer_block(txt: str, pos: str | None):
    if "247SPORTS TRANSFER RANKINGS" not in txt:
        return None, None, None, None
    m = re.search(r"247SPORTS TRANSFER RANKINGS\s+(\d+)\s+\((\d{4})\)", txt)
    rating = int(m.group(1)) if m else None
    year = int(m.group(2)) if m else None
    ovr = int(re.search(r"\bOVR\s+(\d+)\b", txt).group(1)) if re.search(r"\bOVR\s+(\d+)\b", txt) else None

    # pos rank: restrict search to after transfer header
    after = txt.split("247SPORTS TRANSFER RANKINGS", 1)[1]
    pos_rank = None
    if pos:
        m2 = re.search(rf"\b{re.escape(pos)}\s+(\d+)\b", after)
        pos_rank = int(m2.group(1)) if m2 else None
    return rating, year, ovr, pos_rank

def extract_position(driver):
    # DOM-first: metrics list
    try:
        el = driver.find_element(
            By.XPATH,
            "//ul[contains(@class,'metrics-list')]//li[.//span[normalize-space()='Pos']]//span[last()]"
        )
        pos = el.text.strip()
        if pos:
            return pos.upper()
    except Exception:
        pass

    # fallback: text
    txt = body_text(driver)
    m = re.search(r"\bPOS\b\s*([A-Za-z]{1,10})\b", txt, flags=re.IGNORECASE)
    return m.group(1).strip().upper() if m else None

# extract transfer origin and destination blocks from timeline 
def expand_timeline(driver, max_clicks=40):
    # Only click "Load more" buttons INSIDE the timeline area
    for _ in range(max_clicks):
        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//*[@id='timeline']//button[contains(.,'Load more') or contains(.,'Load More')]")
                )
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            time.sleep(0.15)
            driver.execute_script("arguments[0].click();", btn)  # JS click avoids interception
            time.sleep(0.5)
        except Exception:
            break

def open_timeline(driver, tries=3):
    # Goal: end with timeline date lines present in body text.
    for attempt in range(tries):
        # Ensure page is loaded
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//h1")))

        # If date lines already exist, we're done
        if _has_date_lines(driver):
            return True

        # 1) Jump to #timeline (hash link if available)
        try:
            a = driver.find_element(By.XPATH, "//a[@href='#timeline' and normalize-space()='Timeline']")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", a)
            time.sleep(0.15)
            driver.execute_script("arguments[0].click();", a)
        except Exception:
            pass

        # 2) Scroll to the actual timeline container if present
        try:
            section = driver.find_element(By.CSS_SELECTOR, "#timeline")
            driver.execute_script("arguments[0].scrollIntoView({block:'start'});", section)
            time.sleep(0.25)
        except Exception:
            pass

        # 3) Expand entries
        expand_timeline(driver)

        # 4) Poll for date lines (don’t use a brittle WebDriverWait lambda here)
        t0 = time.time()
        while time.time() - t0 < 10:
            if _has_date_lines(driver):
                return True
            time.sleep(0.25)

        # Retry strategy: small scroll jiggle + (optional) soft refresh by reloading same URL
        driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(0.25)
        driver.execute_script("window.scrollBy(0, -300);")
        time.sleep(0.25)

        if attempt < tries - 1:
            driver.get(driver.current_url)  # reload and try again

    return False

def timeline_lines(txt: str):
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    # keep only timeline-ish region
    u = [ln.upper() for ln in lines]
    if "TIMELINE" in u:
        start = u.index("TIMELINE")
        lines = lines[start:]
    # cut off when you hit unrelated sections
    for stop_token in ["IN PICTURES", "ARTICLES", "CBS SPORTS DIGITAL"]:
        if stop_token in [x.upper() for x in lines]:
            stop = [x.upper() for x in lines].index(stop_token)
            lines = lines[:stop]
            break
    return lines

def parse_timeline_events(lines):
    events = []
    i = 0
    while i < len(lines):
        m = DATE_RE.match(lines[i])
        if m:
            dt = datetime.strptime(m.group(1), "%b %d, %Y")
            kind = m.group(2).strip()  # Transfer / Enrolled / Commit / Signed
            text = lines[i+1].strip() if i+1 < len(lines) else ""
            events.append(TL(date=dt, kind=kind, text=text))
            i += 2
        else:
            i += 1
    return events

def extract_school_fragment(event_text: str):
    """
    From a timeline description line, extract the trailing school fragment.
    Handles: "commits to X", "enrolls at X"
    """
    m = re.search(r"\b(transfers to|commits to|committed to|enrolls at)\s+(.+)$", event_text, flags=re.IGNORECASE)
    if not m:
        return None
    frag = m.group(2).strip()
    return frag

def resolve_school_fragment(fragment: str, candidates: list[str]):
    """
    Resolve a possibly-truncated fragment ("Georgia Tech Yellow...") to a canonical school ("Georgia Tech").
    """
    if not fragment or not candidates:
        return None

    frag = fragment.replace("...", "").strip()

    # exact containment check (fast path)
    frag_low = frag.lower()
    for c in candidates:
        if c.lower() in frag_low or frag_low in c.lower():
            return c

    # fuzzy match
    best = process.extractOne(frag, candidates, scorer=fuzz.partial_ratio)
    if best and best[1] >= 80:
        return best[0]
    return None

def infer_origin_dest_from_timeline_events(events, candidates, window_start, window_end):
    """
    events: newest-first list[TL]
    returns origin, dest, dt, status in {"committed","portal_only","none"}
    """

    # --- find destination (newest school-bearing Transfer event in window) ---
    dest = None
    dest_dt = None
    dest_idx = None

    for i, e in enumerate(events):
        if not (window_start <= e.date <= window_end):
            continue
        if e.kind.lower() != "transfer":
            continue
        if not is_school_event(e.text):
            continue

        frag = extract_school_fragment(e.text)
        cand = resolve_school_fragment(frag, candidates) if frag else None

        # FALLBACK: truncated "commits to..." -> use most recent institution
        cand = cand or most_recent_other(candidates)

        if cand:
            dest = cand
            dest_dt = e.date
            dest_idx = i
            break

    # --- if destination found, origin is nearest earlier school-bearing event that resolves ---
    if dest_dt is not None:
        origin = None

        for j in range(dest_idx + 1, len(events)):  # walk backwards in time (older events)
            e = events[j]
            if e.date >= dest_dt:
                continue
            if not is_school_event(e.text):
                continue

            frag = extract_school_fragment(e.text)
            cand = resolve_school_fragment(frag, candidates) if frag else None
            cand = cand or most_recent_other(candidates, exclude=dest)   # fallback
            if cand and cand != dest:
                origin = cand
                break

        # fallback: pick any other candidate school
        if not origin and candidates:
            others = [c for c in candidates if c != dest]
            origin = others[0] if others else None

        return origin, dest, dest_dt, "committed"

    # --- portal-only case (entered portal but no destination) ---
    portal_dt = None
    portal_idx = None
    for i, e in enumerate(events):
        if not (window_start <= e.date <= window_end):
            continue
        if e.kind.lower() == "transfer" and "entered the transfer portal" in (e.text or "").lower():
            portal_dt = e.date
            portal_idx = i
            break

    if portal_dt is not None:
        origin = None
        for j in range(portal_idx + 1, len(events)):
            e = events[j]
            if e.date >= portal_dt:
                continue
            if not is_school_event(e.text):
                continue
            frag = extract_school_fragment(e.text)
            cand = resolve_school_fragment(frag, candidates) if frag else None
            cand = cand or most_recent_other(candidates, exclude=dest)   # fallback
            if cand and cand != dest:
                origin = cand
                break

        if not origin and candidates:
            origin = candidates[0]

        return origin, None, portal_dt, "portal_only"

    return None, None, None, "none"

# Extract NCAA institution names from the institution dropdown using fuzzy matching
def get_ncaa_institutions(driver):
    """
    Returns canonical NCAA institution names from the institution dropdown.
    Works even when list is hidden by reading from hrefs.
    Example: ["Auburn", "Georgia Tech"]
    """
    # ensure dropdown is opened at least once
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button[data-js='institution-selector']")
        btn.click()
        time.sleep(0.2)
    except Exception:
        pass

    names = []

    # pull from hrefs (reliable) + fallback to text
    els = driver.find_elements(By.CSS_SELECTOR, "a.profile-card__institution-list-link")
    for a in els:
        href = (a.get_attribute("href") or "").strip()
        txt = (a.text or "").strip()

        # Prefer href pattern: .../college-123456  (NCAA entries)
        if "/college-" in href:
            # The anchor text may be empty if hidden; parse school from URL path segment after /player/.../
            # Example href: https://247sports.com/player/eric-singleton-jr-46134398/college-328493
            # We can't get school directly from URL, so use txt if present
            if txt:
                # "Auburn (NCAA)" -> "Auburn"
                if "(NCAA)" in txt:
                    names.append(txt.replace("(NCAA)", "").strip())
                else:
                    # sometimes just "Auburn"
                    names.append(txt.strip())
            else:
                # fallback: use the page itself to map college-IDs to school names
                # We'll collect the college IDs now; mapping happens below.
                pass

    # If text-based names worked, dedupe and return
    names = [n for n in names if n]
    if names:
        seen, out = set(), []
        for n in names:
            if n not in seen:
                out.append(n); seen.add(n)
        return out

    # HARD fallback (works even when hidden): use institution block HTML and parse the anchor text from outerHTML
    # outerHTML includes the text even if not visible to Selenium .text sometimes.
    names = []
    for a in els:
        html = a.get_attribute("outerHTML") or ""
        m = re.search(r">([^<]+)\(NCAA\)<", html)
        if m:
            names.append(m.group(1).strip())
        else:
            m2 = re.search(r">([^<]+)</a>", html)
            if m2 and "HS" not in m2.group(1):
                names.append(m2.group(1).replace("(NCAA)","").strip())

    names = [n for n in names if n]
    seen, out = set(), []
    for n in names:
        if n not in seen:
            out.append(n); seen.add(n)
    return out
