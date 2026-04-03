# ClearWake Routing

ClearWake Routing is a B2B API platform designed for logistics companies and cargo fleet operators. The system is an intelligent engine for calculating optimal maritime routes, reducing carbon emissions by utilizing favorable ocean currents and dynamically avoiding protected ecological zones.

### Prerequisites
- Python 3.11+
- MongoDB running locally on port 27017

### Installation

1. Clone the repository
```bash
   git clone <https://github.com/TUES-2026-PBL-11-klas/Bees_Project_2>
   cd Bees_Project_2
```

2. Create and activate a virtual environment
```bash
   python3 -m venv venv
   source venv/bin/activate        # Mac/Linux
   venv\Scripts\activate           # Windows
```

3. Install dependencies
```bash
   pip install -r requirements.txt
```

4. Install pre-commit hooks
```bash
   pip install pre-commit
   pre-commit install
```

5. Set up environment variables
```bash
   cp .env.example .env
```
   Then open `.env` and fill in your values.

6. Run the application
```bash
uvicorn src.main:app --reload --port 8080
```

### Running with Docker
```bash
docker-compose up --build -d
```

API will be available at http://localhost:8080/docs

7. Open the API docs
http://localhost:8080/docs

### Google Maps (English Labels)
1. Get a Google Maps JavaScript API key from Google Cloud.
2. Put the key in .env:

```bash
MAP_PROVIDER=google
GOOGLE_MAPS_API_KEY=your_real_google_maps_api_key
```

3. Restart the app:

```bash
docker-compose up --build -d
```

4. Open the map page:
http://localhost:8080/map

Notes:
- The app already loads Google with language=en and region=US for English labels.
- If the key is missing or invalid, the map falls back to OpenStreetMap.

### Strategy Tests
Run strategy-only tests:

```bash
pytest -q tests/unit/test_strategy.py
```

Run all unit tests:

```bash
pytest -q tests/unit
```

### Run hooks manually
```bash
pre-commit run --all-files
```
