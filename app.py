import time
import logging
import os
import requests
from flask import Flask, render_template, send_file, request, jsonify
from crawlers import CoopCrawler, IcaCrawler, LidlCrawler
import concurrent.futures
from io import BytesIO
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Configuration
class Config:
    STORE_URLS = {
        "Coop": "https://www.coop.se/butiker-erbjudanden/coop/coop-hogdalen/",
        "ICA": "https://www.ica.se/erbjudanden/ica-supermarket-hogdalen-1003514/",
    }
    MATDAX_URL = "https://www.matdax.se/erbjudanden/"
    TIMEOUT = 30
    MAX_RETRIES = 3
    RATE_LIMIT = (60, 100)  # (window, max_requests)

app = Flask(__name__)
app.config.from_object(Config)

# Rate limiting decorator
def rate_limit(f):
    requests = {}
    @wraps(f)
    def decorated_function(*args, **kwargs):
        now = time.time()
        ip = request.remote_addr
        requests[ip] = [t for t in requests.get(ip, []) if now - t < Config.RATE_LIMIT[0]]
        if len(requests.get(ip, [])) >= Config.RATE_LIMIT[1]:
            return jsonify({"error": "Rate limit exceeded"}), 429
        requests.setdefault(ip, []).append(now)
        return f(*args, **kwargs)
    return decorated_function


def fetch_matdax_flyer() -> str | None:
    try: return Config.MATDAX_URL
    except Exception as e:
        logger.error(f"Matdax error: {e}")
        return None

################################################################################
# -----------------------  ROUTES  ---------------------------#
################################################################################

coop_crawler = CoopCrawler()
ica_crawler = IcaCrawler()
lidl_crawler = LidlCrawler()

@app.route("/")
@rate_limit
def index():    
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                'lidl': executor.submit(lidl_crawler.fetch_flyer_url),
                'matdax': executor.submit(fetch_matdax_flyer),
                'coop': executor.submit(coop_crawler.fetch_offers),
                'ica': executor.submit(ica_crawler.fetch_offers)
            }
            
            results = {}
            for key, future in futures.items():
                try:
                    results[key] = future.result(timeout=Config.TIMEOUT)
                except Exception as e:
                    logger.error(f"{key} error: {e}")
                    results[key] = [] if key in ['coop', 'ica'] else None
            
            deals = sorted(results['coop'] + results['ica'], key=lambda d: d["pct_off"], reverse=True)
            
            return render_template(
                "index.html",
                deals=deals,
                flyer_urls={"Lidl": results['lidl'], "Matdax": results['matdax']},
                link_urls=Config.STORE_URLS,
            )
    except Exception as e:
        logger.error(f"Index error: {e}")
        return render_template("error.html", error="Failed to fetch deals"), 500

@app.route("/proxy_pdf")
@rate_limit
def proxy_pdf():
    url = request.args.get('url')
    if not url or not url.startswith(('http://', 'https://')):
        return jsonify({"error": "Invalid URL"}), 400
        
    try:
        response = requests.get(url, stream=True, timeout=Config.TIMEOUT)
        response.raise_for_status()
        return send_file(
            BytesIO(response.content),
            mimetype='application/pdf',
            as_attachment=False,
            download_name='flyer.pdf'
        )
    except Exception as e:
        logger.error(f"PDF error: {e}")
        return jsonify({"error": "Failed to fetch PDF"}), 500

################################################################################
# -----------------------------  MAIN  ------------------------------------#
################################################################################

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host="0.0.0.0", port=port, debug=debug)
