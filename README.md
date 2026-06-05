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

### Authentication

The API ships with JWT-based auth and role-based access control (admin / operator / viewer).

1. Bootstrap the first admin for a company:
```bash
curl -X POST http://localhost:8080/api/v1/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"company_id": "<oid>", "email": "you@example.com", "password": "supersecret", "role": "admin"}'
```

2. Log in to get a bearer token:
```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "supersecret"}'
```

3. Call protected endpoints with `Authorization: Bearer <token>`. Use `/api/v1/auth/me` to verify.

Set `JWT_SECRET` in `.env` to a long random value in any non-dev environment.

### Background jobs

The platform has an in-process task queue for GRIB ingest, analytics rollups, AI reroutes, and weather refresh. Admins can enqueue jobs by name and inspect their state:

```bash
curl -X POST http://localhost:8080/api/v1/jobs/grib_ingest \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"path": "/data/currents.grib2"}'
```

Production deployments can swap the in-process implementation for an RQ + Redis backend; the `TaskQueue` interface (`src/infrastructure/queue/task_queue.py`) is the only thing that needs to change.

### Architecture diagrams

See [docs/architecture.md](docs/architecture.md) for the module map, class diagrams (routing, AI, auth/tenancy), sequence diagrams (route calculation, JWT login, background jobs), and deployment topology.

### Tests
Run strategy-only tests:

```bash
pytest -q tests/unit/test_strategy.py
```

Run all unit tests:

```bash
pytest -q tests/unit
```

Run the full suite with coverage:

```bash
pytest --cov=src --cov-report=term tests/
```

### Run hooks manually
```bash
pre-commit run --all-files
```
