# Handla - Mat-deals

Aggregates grocery deals from Swedish supermarkets (Coop, ICA, Lidl, Matdax).

## Setup

```bash
git clone https://github.com/yourusername/handla.git
cd handla
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
# Visit http://localhost:8000
```

## Config

Environment variables:
- `PORT`: Server port (default: 8000)
- `FLASK_ENV`: Set to 'development' for debug mode
- `TIMEOUT`: Request timeout in seconds (default: 30)
- `MAX_RETRIES`: Max retries for failed requests (default: 3)
- `RATE_LIMIT`: Rate limit (window, max_requests) (default: 60, 100)

## Structure

```
handla/
├── app.py              # Main app
├── crawlers/           # Store crawlers
├── static/css/         # Styles
├── templates/          # HTML
└── requirements.txt    # Dependencies
```

## License

MIT
