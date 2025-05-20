# app.py
import re
import json
import math
import time
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from flask import Flask, render_template
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from crawlers import CoopCrawler, ICACrawler
from offer_types import Offer

app = Flask(__name__)

################################################################################
# ----------------------------  1.  DATA SOURCES  -----------------------------#
################################################################################

LIDL_STORE_URL = "https://www.lidl.se/s/sv-SE/butiker/enskede/bussens-vaeg-5/"

LINK_URLS = {
    "Coop": "https://www.coop.se/butiker-erbjudanden/coop/coop-hogdalen/",
    "ICA": "https://www.ica.se/erbjudanden/ica-supermarket-hogdalen-1003514/",
    "lidl": LIDL_STORE_URL,
}

################################################################################
# -----------------------------  3.  FETCHERS  --------------------------------#
################################################################################

def fetch_lidl_flyer() -> str | None:
    soup = BeautifulSoup(requests.get(LIDL_STORE_URL, timeout=20).text, "lxml")
    first_link = soup.find("a", href=lambda x: x and "reklamblad" in x)
    if not first_link:
        print("No reklamblad link found")
        return None
    href = first_link["href"]
    return urljoin(LIDL_STORE_URL, href)

################################################################################
# -----------------------  4.  ROUTE  &  RENDERING  ---------------------------#
################################################################################

coop_crawler = CoopCrawler()
ica_crawler = ICACrawler()

@app.route("/")
def index():    
    coop = coop_crawler.fetch_offers()
    ica = ica_crawler.fetch_offers()
    deals = sorted(coop + ica, key=lambda d: d["pct_off"], reverse=True)
    
    return render_template(
        "index.html",
        deals=deals,
        flyer=fetch_lidl_flyer(),
        link_urls=LINK_URLS,
    )


################################################################################
# -----------------------------  5.  MAIN  ------------------------------------#
################################################################################

if __name__ == "__main__":
    # Run on 0.0.0.0 so it's reachable on LAN; change port freely.
    app.run(host="0.0.0.0", port=8000, debug=True)
