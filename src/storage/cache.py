import os, json
from tqdm.auto import tqdm

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


from src.config import HEADLESS, CACHE_PATH
from src.scraper.player_scraper import scrape_player

# ---------- DRIVER FACTORY ----------
def make_driver(headless=HEADLESS):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--lang=en-US")
    return webdriver.Chrome(options=opts)

# ---------- CHECKPOINT CACHE ----------
def load_cache(path=CACHE_PATH):
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, "r") as f:
        for line in f:
            try:
                d = json.loads(line)
                # key by source_player_url (your scrape_player returns it)
                k = (d.get("source_player_url") or "").rstrip("/")
                if k:
                    out[k] = d
            except:
                pass
    return out

def append_cache(d, path=CACHE_PATH):
    with open(path, "a") as f:
        f.write(json.dumps(d) + "\n")

# ---------- WORKER SCRAPE (ONE DRIVER PER TASK) ----------
def scrape_one(url):
    drv = make_driver(headless=HEADLESS)
    try:
        d = scrape_player(drv, url)  # <-- uses YOUR working function
        # normalize key
        if "source_player_url" in d and d["source_player_url"]:
            d["source_player_url"] = d["source_player_url"].rstrip("/")
        else:
            d["source_player_url"] = url.rstrip("/")
        return d
    finally:
        try: drv.quit()
        except: pass