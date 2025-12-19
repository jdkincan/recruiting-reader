# Recruiting Reader
Python + Selenium project for reading/scraping transfer-portal recruiting information into machine-readable data for downstream analysis.
## Quick start
'''git clone https://github.com/jdkincan/recruiting-reader.git
cd recruiting-reader

python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows PowerShell'''

pip install -r requirements.txt
Run
From the repo root, run the project’s entrypoint (check src/ for the main script/module):
python -m src.main
If your entrypoint is a script instead of a module, run it directly:
python src/main.py
Notes
You need a working Selenium browser setup (Chrome/Firefox + compatible driver, or Selenium Manager via modern Selenium).
Scraped outputs are typically written to a local folder in the repo (check for directories like uploaded_data/ or data/).
Notebooks (if present) live in notebooks/ and can be launched with:
jupyter notebook