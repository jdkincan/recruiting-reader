from typing import List

import time
from tqdm.auto import tqdm

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 247 scraping primitives
def click_load_more_until_done(
    driver: webdriver.Chrome,
    timeout: int = 12,
    max_clicks: int = 200
) -> None:
    for _ in tqdm(range(max_clicks), desc="Clicking 'Load More'", unit="click"):
        try:
            btn = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(., 'Load More Players') or contains(., 'Load More')]"
                ))
            )
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", btn
            )
            time.sleep(0.3)
            btn.click()
            time.sleep(0.8)  # let items render
        except Exception:
            break


def scrape_portal_player_links(
    driver: webdriver.Chrome,
    portal_url: str
) -> List[str]:
    driver.get(portal_url)
    time.sleep(1.5)

    click_load_more_until_done(driver)

    anchors = driver.find_elements(
        By.XPATH,
        "//a[contains(@href, '/player/') and not(contains(@href, '#'))]"
    )

    urls = []
    for a in tqdm(anchors, desc="Collecting player links", unit="link"):
        href = a.get_attribute("href")
        if href and "/player/" in href:
            urls.append(href.split("?")[0].rstrip("/"))

    # dedupe while preserving order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            out.append(u)
            seen.add(u)

    return out