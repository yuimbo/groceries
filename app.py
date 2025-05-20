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

app = Flask(__name__)

################################################################################
# ----------------------------  1.  DATA SOURCES  -----------------------------#
################################################################################

COOP_URL = (
    "https://external.api.coop.se/dke/offers/categories/offers/015120"
    "?api-version=v1&clustered=true"
)
COOP_HEADERS = {
    "Ocp-Apim-Subscription-Key": "3804fe145c4e4629ab9b6c755d2e3cfb",
    "Accept": "application/json",
    "User-Agent": "deals-scraper/1.0",
}

ICA_URL = "https://www.ica.se/erbjudanden/ica-supermarket-hogdalen-1003514/"

LIDL_STORE_URL = "https://www.lidl.se/s/sv-SE/butiker/enskede/bussens-vaeg-5/"

LINK_URLS = {
    "Coop": "https://www.coop.se/butiker-erbjudanden/coop/coop-hogdalen/",
    "ICA": ICA_URL,
    "lidl": LIDL_STORE_URL,
}

PRICE_RE = re.compile(r"(\d+)(?::|\.)(\d+)?")  # handles 35:90 / 35.90 / 35:-

################################################################################
# -------------------------  2.  PARSING UTILITIES  ---------------------------#
################################################################################


def _price_text_to_float(text: str) -> float:
    """
    Convert Swedish price fragments like '35:-', '35:90', '35.90'
    to a float 35, 35.90, ...
    """
    text = text.replace(" ", "").replace("-", "-")
    m = PRICE_RE.search(text)
    if not m:
        raise ValueError(f"Unparsable price: {text}")
    krona, ore = m.group(1), m.group(2)
    return float(krona) if ore is None else float(f"{krona}.{ore}")


def _avg_price_from_range(range_str: str) -> float:
    """
    '38:90-50:90' -> 44.9  (mean of endpoints)
    """
    pts = range_str.split("-")
    prices = [_price_text_to_float(p) for p in pts]
    return sum(prices) / len(prices)


################################################################################
# -----------------------------  3.  FETCHERS  --------------------------------#
################################################################################


def fetch_coop_offers() -> list[dict]:
    """Return list of dicts with keys
    store, name, sale_price, ordinary_price, pct_off, unit
    """
    offers = []
    resp = requests.get(COOP_URL, headers=COOP_HEADERS, timeout=20)
    data = resp.json()
    for cat in data.get("categories", []):
        for off in cat.get("offers", []):
            pi = off["priceInformation"]
            ordinary = pi.get("ordinaryPrice")    
            sale = pi.get("discountValue")
            minAmount = pi.get("minimumAmount")
            isItemPriceDiscount = pi.get("isItemPriceDiscount")
            if minAmount and minAmount > 1 and not isItemPriceDiscount:
                sale = sale / minAmount
            if ordinary and sale:
                pct = round((ordinary - sale) / ordinary * 100, 1)
                offers.append(
                    {
                        "store": "Coop",
                        "name": off["content"]["title"],
                        "brand": off["content"].get("brand", None),
                        "sale_price": sale,
                        "ordinary_price": ordinary,
                        "pct_off": pct,
                        "unit": pi.get("unit", ""),
                    }
                )
    return offers


def fetch_ica_offers() -> list[dict]:
    offers = []
    
    # Set up Chrome options for headless browsing
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Initialize the Chrome driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        # Load the page
        driver.get(ICA_URL)
        
        # Wait for articles to be loaded (adjust timeout as needed)
        wait = WebDriverWait(driver, 20)
        articles = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.offers__container article"))
        )
        
        print(str(len(articles)) + " ICA produkter")
        
        for art in articles:
            try:
                # ---------------- Product name ----------------
                name_tag = art.find_element(By.CSS_SELECTOR, "p.offer-card__title")
                name = name_tag.text.strip()

                # ---------------- Sale price ------------------
                first_val = art.find_element(By.CSS_SELECTOR, ".price-splash__text__firstValue")
                first_text = first_val.text.strip().replace(":-", "")
                sale_price = float(first_text)
                
                try:
                    sec_val = art.find_element(By.CSS_SELECTOR, ".price-splash__text__secondaryValue")
                    sale_price += float("0." + sec_val.text.strip())
                except:
                    pass

                # If prefix like "2 för", divide price by qty
                qty = 1
                try:
                    prefix = art.find_element(By.CSS_SELECTOR, ".price-splash__text__prefix")
                    m = re.match(r"\s*(\d+)\s*f[öo]r", prefix.text.strip(), re.I)
                    if m:
                        qty = int(m.group(1))
                except:
                    pass
                    
                sale_price_per_unit = sale_price / qty

                # ---------------- Ordinary price (range) -------
                text = art.find_element(By.CSS_SELECTOR, "p.offer-card__text").text.strip()
                m = re.search(r"Ord\.pris\s+([0-9:.\-]+)", text)
                if not m:
                    # Try non-range format "Ord.pris XX:XX kr."
                    m = re.search(r"Ord\.pris\s+(\d+):(\d+)", text)
                    if not m:
                        print(f"Skipping malformed article (no price): {name}")
                        continue
                    ordinary_price = float(m.group(1)) + float(m.group(2))/100
                else:
                    range_str = m.group(1)
                    ordinary_price = _avg_price_from_range(range_str)
                
                # ---------------- Brand ----------------
                brand = text.split('.')[0]

                pct_off = round(
                    (ordinary_price - sale_price_per_unit) / ordinary_price * 100, 1
                )
                
                # ---
                try:
                    suffix = art.find_element(By.CSS_SELECTOR, ".price-splash__text__suffix")
                    unit = suffix.text.strip().lstrip("/")
                except:
                    unit = 'st'

                offers.append(
                    {
                        "store": "ICA",
                        "name": name,
                        "brand": brand,
                        "sale_price": round(sale_price_per_unit, 2),
                        "ordinary_price": round(ordinary_price, 2),
                        "pct_off": pct_off,
                        "unit": unit,
                    }
                )
            except Exception as e:
                # Skip malformed articles
                print(f"Skipping malformed article: {name if 'name' in locals() else 'unknown'}")
                print(f"Error: {e} on line {e.__traceback__.tb_lineno}")
                continue
    finally:
        driver.quit()
        
    return offers


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
    coop = fetch_coop_offers()
    ica = fetch_ica_offers()
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
