# ClearWake Routing

ClearWake Routing is a B2B API platform designed for logistics companies and cargo fleet operators. The system is an intelligent engine for calculating optimal maritime routes, reducing carbon emissions by utilizing favorable ocean currents and dynamically avoiding protected ecological zones.

### Prerequisites
- Python 3.11+
- MongoDB running locally on port 27017

### Installation

1. Clone the repository
```bash
   git clone <repo-url>
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

7. Open the API docs
```
   http://localhost:8080/docs
```

### Run hooks manually
```bash
pre-commit run --all-files
```
