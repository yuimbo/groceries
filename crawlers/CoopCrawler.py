import requests
from typing import List
from .Crawler import Crawler
from .cache_utils import timed_lru_cache
from offer_types import Offer

class CoopCrawler(Crawler):
    def __init__(self):
        super().__init__("Coop")
        self.url = (
            "https://external.api.coop.se/dke/offers/categories/offers/015120"
            "?api-version=v1&clustered=true"
        )
        self.headers = {
            "Ocp-Apim-Subscription-Key": "3804fe145c4e4629ab9b6c755d2e3cfb",
            "Accept": "application/json",
            "User-Agent": "deals-scraper/1.0",
        }

    @timed_lru_cache(seconds=300)  # 5 minutes cache
    def fetch_offers(self) -> List[Offer]:
        """Return list of offers from Coop."""
        offers: List[Offer] = []
        resp = requests.get(self.url, headers=self.headers, timeout=20)
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
                    offers.append(
                        self._create_offer(
                            name=off["content"]["title"],
                            sale_price=sale,
                            ordinary_price=ordinary,
                            unit=pi.get("unit", ""),
                            brand=off["content"].get("brand", None),
                        )
                    )
        return offers 