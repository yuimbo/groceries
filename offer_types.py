from typing import TypedDict, Optional

class Offer(TypedDict):
    store: str
    name: str
    brand: Optional[str]
    sale_price: float
    ordinary_price: float
    pct_off: float
    unit: str 