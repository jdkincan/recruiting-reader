from selenium import webdriver
from selenium.webdriver.chrome.options import Options


# Selenium setup
def make_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,1000")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # helps reduce some bot friction
    opts.add_argument("--lang=en-US")
    driver = webdriver.Chrome(options=opts)  # Selenium Manager will fetch driver if needed
    driver.set_page_load_timeout(45)
    return driver
