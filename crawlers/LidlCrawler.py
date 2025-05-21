import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from .Crawler import Crawler
from .cache_utils import timed_lru_cache

class LidlCrawler(Crawler):
    """Crawler for Lidl store flyers."""
    
    def __init__(self):
        super().__init__("Lidl")
        self.store_url = "https://www.lidl.se/s/sv-SE/butiker/enskede/bussens-vaeg-5/"
    
    @timed_lru_cache(seconds=300)  # 5 minutes cache
    def fetch_flyer_url(self):
        """Fetch the current flyer URL from Lidl.
        
        Returns:
            str | None: URL to the PDF flyer, or None if not found
        """
        # Set up Chrome options for headless browsing
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Initialize the Chrome driver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        try:
            driver.get(self.store_url)
            
            # Wait for the flyer carousel to load
            wait = WebDriverWait(driver, 20)
            title = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "p.leaflet-carousel__title"))
            )
            
            # Find the ERBJUDANDEN title
            titles = driver.find_elements(By.CSS_SELECTOR, "p.leaflet-carousel__title")
            target_title = None
            for t in titles:
                if t.text.strip().startswith("ERBJUDANDEN"):
                    target_title = t
                    break
            
            if not target_title:
                print("No matching title found")
                return None
                
            # Get the parent li and find the link
            element = target_title
            while element.tag_name != "li":
                element = element.find_element(By.XPATH, "./..")
            li = element
            link = li.find_element(By.TAG_NAME, "a")
            flyer_url = link.get_attribute("href")
            
            # Navigate to the flyer page
            driver.get(flyer_url)
            
            # Wait for the page to load and find the PDF link
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # If cookie popup, click accept
            try:
                accept_button = wait.until(
                    EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
                )
                accept_button.click()
            except:
                # Continue if cookie popup not found
                pass
            
            # Click the menu button
            menu_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Meny']"))
            )
            try:
                menu_button.click()
            except:
                driver.save_screenshot("temp/lidl_error.png")
                print("Failed to click menu button - see temp/lidl_error.png for page state")
                raise
            
            # Wait a moment for any animations/changes after clicking
            time.sleep(1)
            
            pdf_links = driver.find_elements(By.CSS_SELECTOR, "a[href$='.pdf']")
            
            print(pdf_links)
            
            if pdf_links:
                return pdf_links[0].get_attribute("href")
            return None
            
        finally:
            driver.quit() 
            
    def fetch_offers(self):
        """Not implemented for Lidl crawler.
        
        Returns:
            List[Offer]: Empty list since not implemented
        """
        raise NotImplementedError("fetch_offers() is not implemented for Lidl crawler")