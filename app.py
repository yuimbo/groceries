# app.py
import re
import json
import math
import time
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from flask import Flask, render_template, send_file, request
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from crawlers import CoopCrawler, IcaCrawler, LidlCrawler
from offer_types import Offer
import concurrent.futures
from io import BytesIO

app = Flask(__name__)

################################################################################
# ----------------------------  1.  DATA SOURCES  -----------------------------#
################################################################################

LINK_URLS = {
    "Coop": "https://www.coop.se/butiker-erbjudanden/coop/coop-hogdalen/",
    "ICA": "https://www.ica.se/erbjudanden/ica-supermarket-hogdalen-1003514/",
}

################################################################################
# -----------------------------  3.  FETCHERS  --------------------------------#
################################################################################

def fetch_matdax_flyer() -> str | None:
    MATDAX_STORE_URL = "https://www.matdax.se/erbjudanden/"
    return MATDAX_STORE_URL

################################################################################
# -----------------------  4.  ROUTE  &  RENDERING  ---------------------------#
################################################################################

coop_crawler = CoopCrawler()
ica_crawler = IcaCrawler()
lidl_crawler = LidlCrawler()

@app.route("/")
def index():    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            'lidl': executor.submit(lidl_crawler.fetch_flyer_url),
            'matdax': executor.submit(fetch_matdax_flyer),
            'coop': executor.submit(coop_crawler.fetch_offers),
            'ica': executor.submit(ica_crawler.fetch_offers)
        }
        lidl_flyer_url = futures['lidl'].result()
        matdax_flyer_url = futures['matdax'].result()
        coop = futures['coop'].result()
        ica = futures['ica'].result()
        deals = sorted(coop + ica, key=lambda d: d["pct_off"], reverse=True)
        
        return render_template(
            "index.html",
            deals=deals,
            flyer_urls={"Lidl": lidl_flyer_url, "Matdax": matdax_flyer_url},
            link_urls=LINK_URLS,
        )

@app.route("/proxy_pdf")
def proxy_pdf():
    """Proxy PDF content from external sources."""
    url = request.args.get('url')
    if not url:
        return "No URL provided", 400
        
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Create a BytesIO object from the content
        pdf_content = BytesIO(response.content)
        
        # Set appropriate headers
        headers = {
            'Content-Type': 'application/pdf',
            'Content-Disposition': 'inline',
            'X-Frame-Options': 'SAMEORIGIN'  # Allow embedding in our own domain
        }
        
        return send_file(
            pdf_content,
            mimetype='application/pdf',
            as_attachment=False,
            download_name='flyer.pdf'
        )
    except Exception as e:
        return f"Error fetching PDF: {str(e)}", 500

################################################################################
# -----------------------------  5.  MAIN  ------------------------------------#
################################################################################

if __name__ == "__main__":
    # Run on 0.0.0.0 so it's reachable on LAN; change port freely.
    app.run(host="0.0.0.0", port=8000, debug=True)
