import re
from typing import List
from functools import lru_cache, wraps
from time import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from .base import Crawler
from offer_types import Offer

def timed_lru_cache(seconds: int, maxsize: int = 128):
    def wrapper_decorator(func):
        func = lru_cache(maxsize=maxsize)(func)
        func.lifetime = seconds
        func.expiration = time() + seconds

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if time() >= func.expiration:
                func.cache_clear()
                func.expiration = time() + func.lifetime
            return func(*args, **kwargs)

        return wrapped_func
    return wrapper_decorator

class ICACrawler(Crawler):
    def __init__(self):
        super().__init__("ICA")
        self.url = "https://www.ica.se/erbjudanden/ica-supermarket-hogdalen-1003514/"
        self.price_re = re.compile(r"(\d+)(?::|\.)(\d+)?")  # handles 35:90 / 35.90 / 35:-

    def _price_text_to_float(self, text: str) -> float:
        """Convert Swedish price fragments like '35:-', '35:90', '35.90' to a float."""
        text = text.replace(" ", "").replace("-", "-")
        m = self.price_re.search(text)
        if not m:
            raise ValueError(f"Unparsable price: {text}")
        krona, ore = m.group(1), m.group(2)
        return float(krona) if ore is None else float(f"{krona}.{ore}")

    def _avg_price_from_range(self, range_str: str) -> float:
        """'38:90-50:90' -> 44.9  (mean of endpoints)"""
        pts = range_str.split("-")
        prices = [self._price_text_to_float(p) for p in pts]
        return sum(prices) / len(prices)

    @timed_lru_cache(seconds=300)  # 5 minutes cache
    def fetch_offers(self) -> List[Offer]:
        """Return list of offers from ICA."""
        offers: List[Offer] = []
        
        # Set up Chrome options for headless browsing
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Initialize the Chrome driver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        try:
            # Load the page
            driver.get(self.url)
            
            # Wait for articles to be loaded
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
                        ordinary_price = self._avg_price_from_range(range_str)
                    
                    # ---------------- Brand ----------------
                    brand = text.split('.')[0]

                    # ---
                    try:
                        suffix = art.find_element(By.CSS_SELECTOR, ".price-splash__text__suffix")
                        # TODO: If suffix has "pant", it is not unit but rather an extra fee
                        unit = suffix.text.strip().lstrip("/")
                    except:
                        unit = 'st'

                    offers.append(
                        self._create_offer(
                            name=name,
                            sale_price=sale_price_per_unit,
                            ordinary_price=ordinary_price,
                            unit=unit,
                            brand=brand,
                        )
                    )
                except Exception as e:
                    # Skip malformed articles
                    print(f"Skipping malformed article: {name if 'name' in locals() else 'unknown'}")
                    print(f"Error: {e} on line {e.__traceback__.tb_lineno}")
                    continue
        finally:
            driver.quit()
            
        return offers 