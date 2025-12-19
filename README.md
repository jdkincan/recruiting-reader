# Recruiting Reader
Python + Selenium project for reading/scraping transfer-portal recruiting information into machine-readable data for downstream analysis.
## Quick start
```
git clone https://github.com/jdkincan/recruiting-reader.git
cd recruiting-reader

python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows PowerShell

pip install -r requirements.txt
```

## Run
From the repo root, run the project’s entrypoint (check notebooks/ for main.ipynb)

## Notes
- You need a working Selenium browser setup (Chrome/Firefox + compatible driver, or Selenium Manager via modern Selenium).
- Scraped outputs are typically written to a local folder like data/.
