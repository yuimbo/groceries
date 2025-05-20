from abc import ABC, abstractmethod
from typing import List
from offer_types import Offer

class Crawler(ABC):
    """Base class for all store crawlers."""
    
    def __init__(self, store_name: str):
        self.store_name = store_name
    
    @abstractmethod
    def fetch_offers(self) -> List[Offer]:
        """Fetch offers from the store.
        
        Returns:
            List[Offer]: List of offers from the store.
        """
        pass
    
    def _create_offer(
        self,
        name: str,
        sale_price: float,
        ordinary_price: float,
        unit: str = "st",
        brand: str | None = None,
    ) -> Offer:
        """Helper method to create an offer with consistent structure.
        
        Args:
            name: Product name
            sale_price: Sale price
            ordinary_price: Ordinary price
            unit: Unit (e.g. "st", "kg", "l")
            brand: Brand name (optional)
            
        Returns:
            Offer: A properly structured offer
        """
        pct_off = round((ordinary_price - sale_price) / ordinary_price * 100, 1)
        return {
            "store": self.store_name,
            "name": name,
            "brand": brand,
            "sale_price": round(sale_price, 2),
            "ordinary_price": round(ordinary_price, 2),
            "pct_off": pct_off,
            "unit": unit,
        } 