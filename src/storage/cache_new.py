import os, json, time, threading, queue
from tqdm.auto import tqdm

from src.config import HEADLESS, CACHE_PATH
from src.scraper.player_scraper import scrape_player

# ---------------- DRIVER FACTORY ----------------
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def make_driver(headless=True):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--lang=en-US")

    # Big speed wins:
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 1,
        "profile.managed_default_content_settings.fonts": 2,
        "profile.managed_default_content_settings.cookies": 1,
        "profile.default_content_setting_values.notifications": 2,
    }
    opts.add_experimental_option("prefs", prefs)

    # Selenium 4: set capabilities through options
    opts.set_capability("pageLoadStrategy", "eager")

    return webdriver.Chrome(options=opts)


# ---------------- CACHE ----------------
def load_cache(path=CACHE_PATH):
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, "r") as f:
        for line in f:
            try:
                d = json.loads(line)
                k = (d.get("source_player_url") or "").rstrip("/")
                if k:
                    out[k] = d
            except:
                pass
    return out

# ---------------- WRITER THREAD ----------------
STOP = object()
write_q = queue.Queue(maxsize=10000)

def writer_thread(path: str):
    with open(path, "a", buffering=1) as f:  # line-buffered
        while True:
            item = write_q.get()
            if item is STOP:
                write_q.task_done()
                break
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            write_q.task_done()

# ---------------- WORKER (REUSE ONE DRIVER) ----------------
def worker(work_q: "queue.Queue[str]", pbar: tqdm, recycle_every: int = 100):
    drv = make_driver(headless=HEADLESS)
    n = 0
    try:
        while True:
            url = work_q.get()
            if url is STOP:
                work_q.task_done()
                break

            try:
                d = scrape_player(drv, url)  # unchanged
                # normalize key
                if "source_player_url" in d and d["source_player_url"]:
                    d["source_player_url"] = d["source_player_url"].rstrip("/")
                else:
                    d["source_player_url"] = url.rstrip("/")

                write_q.put(d)

            except Exception as e:
                # optional: log failures
                write_q.put({"source_player_url": url.rstrip("/"), "error": str(e)})

            finally:
                n += 1
                pbar.update(1)
                work_q.task_done()

            # recycle driver periodically to prevent slowdown/crashes
            if recycle_every and (n % recycle_every == 0):
                try:
                    drv.quit()
                except:
                    pass
                drv = make_driver(headless=HEADLESS)

    finally:
        try:
            drv.quit()
        except:
            pass

# ---------------- RUNNER ----------------
def run_scrape(urls, out_path=CACHE_PATH, num_workers=6, recycle_every=100):
    # load cache and skip already done
    cache = load_cache(out_path)
    urls_norm = [u.rstrip("/") for u in urls]
    todo = [u for u in urls_norm if u not in cache]

    work_q = queue.Queue(maxsize=5000)

    # start writer
    wt = threading.Thread(target=writer_thread, args=(out_path,), daemon=True)
    wt.start()

    # enqueue work
    for u in todo:
        work_q.put(u)

    # start workers
    pbar = tqdm(total=len(todo), desc="Scraping", unit="player")
    threads = []
    for _ in range(num_workers):
        t = threading.Thread(target=worker, args=(work_q, pbar, recycle_every), daemon=True)
        t.start()
        threads.append(t)

    # stop workers
    for _ in range(num_workers):
        work_q.put(STOP)

    # wait work done
    work_q.join()
    pbar.close()

    # stop writer
    write_q.put(STOP)
    write_q.join()
    wt.join(timeout=5)

    return len(todo), len(cache)

