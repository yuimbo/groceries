# app.py
import re
import json
import math
import time
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from flask import Flask, render_template_string
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

HTML_TEMPLATE = """
<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8">
  <title>Veckans bästa mat-deals</title>
  <style>
    body{font-family:sans-serif;margin:2rem;background:#fafafa;}
    h1{text-align:center;}
    table{border-collapse:collapse;width:100%;margin-bottom:3rem;}
    th,td{padding:.65rem 1rem;border-bottom:1px solid #ddd;text-align:left;}
    th{background:#eee;}
    .badge{display:inline-block;padding:.1rem .35rem;font-size:.75rem;
           color:#fff;border-radius:.25rem;margin-right:.4rem;}
    .Coop{background:#019247}.ICA{background:#DB000B}
    .brand{font-size:.8rem;color:#666;}
  </style>
</head>
<body>
  <h1>Veckans bästa deals – sorterat på högst %-rabatt</h1>

  <table>
    <thead>
      <tr><th>Butik</th><th>Produkt</th><th>Reapris</th>
          <th>Ord. pris</th><th>%-rabatt</th></tr>
    </thead>
    <tbody>
      {% for o in deals %}
        <tr>
          <td><a class="badge {{o.store}}" href="{{link_urls[o.store]}}" target="_blank">{{o.store}}</a></td>
          <td>{{o.name}} {% if o.brand %}<span class="brand">{{o.brand}}</span>{% endif %}</td>
          <td>{{o.sale_price}} kr/{{o.unit}}</td>
          <td>{{o.ordinary_price}} kr/{{o.unit}}</td>
          <td><strong>{{o.pct_off}} %</strong></td>
        </tr>
      {% endfor %}
    </tbody>
  </table>

  {% if flyer %}
    <h2>Lidl reklamblad</h2>
    <p><a href="{{flyer}}" target="_blank" rel="noopener">Öppna veckans Lidl-blad (PDF / bild)</a></p>
    <iframe src="{{flyer}}" style="width:100%;min-height:80vh;border:none;"></iframe>
  {% endif %}
</body>
</html>
"""


@app.route("/")
def index():
    coop_crawler = CoopCrawler()
    ica_crawler = ICACrawler()
    
    coop = coop_crawler.fetch_offers()
    ica = ica_crawler.fetch_offers()
    deals = sorted(coop + ica, key=lambda d: d["pct_off"], reverse=True)
    
    return render_template_string(
        HTML_TEMPLATE,
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
