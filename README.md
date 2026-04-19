# ClearWake Routing

ClearWake Routing is a B2B API platform designed for logistics companies and cargo fleet operators. The system is an intelligent engine for calculating optimal maritime routes, reducing carbon emissions by utilizing favorable ocean currents and dynamically avoiding protected ecological zones.

### Prerequisites
- Python 3.11+
- MongoDB running locally on port 27017

### Installation

1. Clone the repository
```bash
   git clone <https://github.com/tues-2026-pbl-11-klas/bees_project_2>
   cd bees_project_2
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

### Initialize Database (MongoDB)
Run the bootstrap script once to create indexes and seed demo records:

```bash
python -m src.infrastructure.database.bootstrap
```

If you are running with Docker Compose, execute it inside the app container:

```bash
docker-compose exec app python -m src.infrastructure.database.bootstrap
```

The script is idempotent and can be re-run safely.

7. Open the API docs
http://localhost:8080/docs

### Free Map View
The map page uses a free CARTO basemap through Leaflet.

1. Set the style in `.env`:

```bash
MAP_PROVIDER=carto-voyager
```

2. Restart the app:

```bash
docker-compose up --build -d
```

3. Open the map page:
http://localhost:8080/map

Notes:
- `carto-voyager` gives the best default visual style.
- `carto-positron` is a lighter alternative if you want a cleaner look.
- The route and zone overlays still come from the app itself.

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
