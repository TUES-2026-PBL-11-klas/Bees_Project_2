# ClearWake Architecture

This document describes how the ClearWake Routing platform is wired together: the major modules, how a request travels through the stack, and how the pieces are deployed. All diagrams are Mermaid so they render directly in GitHub.

## Module map

```mermaid
flowchart TD
  subgraph Client
    UI[Map UI<br/>src/static/map.html]
  end

  subgraph API[FastAPI app — src/main.py]
    Router[Aggregate router<br/>src/api/router.py]
    AuthDep[get_current_user / require_role<br/>src/api/auth_dependencies.py]
  end

  subgraph Domain[Core domain]
    Strategy[Routing strategies<br/>FastestStrategy, EcoStrategy, CurrentAwareStrategy]
    Optimizer[Draft/Trim optimizer]
    AISvc[AIService<br/>anomaly, ETA, reroute, recommendations]
    Currents[Ocean currents<br/>grib_parser + current_grid]
    Spatial[Zone spatial service]
  end

  subgraph Infra[Infrastructure]
    Repos[(Repositories<br/>Mongo + Mongoengine)]
    Queue[TaskQueue<br/>InProcessTaskQueue]
    WS[WebSocketManager]
    Cache[Route LRU cache]
  end

  UI -->|REST + WS| Router
  Router --> AuthDep
  Router --> Strategy
  Router --> Optimizer
  Router --> AISvc
  Router --> Currents
  Router --> Queue
  Router --> Cache
  Strategy --> Spatial
  Strategy --> Currents
  AISvc --> Repos
  AISvc --> WS
  Queue --> AISvc
  Queue --> Currents
  Cache -.cache-aside.-> Strategy
  Spatial --> Repos
  Optimizer -.consulted by.- Router

  classDef infra fill:#0b1120,stroke:#60a5fa,color:#f1f5f9;
  classDef domain fill:#1a2332,stroke:#4ade80,color:#f1f5f9;
  class Infra,Repos,Queue,WS,Cache infra
  class Domain,Strategy,Optimizer,AISvc,Currents,Spatial domain
```

## Class diagram — routing layer

```mermaid
classDiagram
  class RoutingStrategy {
    <<abstract>>
    +calculate_route(graph, start, end, vessel) Optional~List~Waypoint~~
  }
  class FastestStrategy
  class EcoStrategy {
    -spatial_service: ZoneSpatialService
  }
  class CurrentAwareStrategy {
    -_base: RoutingStrategy
    -_current_data: dict
    -_weather_data: dict
  }
  RoutingStrategy <|-- FastestStrategy
  RoutingStrategy <|-- EcoStrategy
  RoutingStrategy <|-- CurrentAwareStrategy

  class VesselConstraints {
    +vessel_type: str
    +max_draft_m: float
    +max_speed_knots: float
    +fuel_consumption_rate: float
    +fuel_multiplier: float
    +length_m: float
    +beam_m: float
    +max_cargo_t: float
    +cargo_weight_t: float
    +trim_m: float
    +hydro_resistance_coef: float
  }

  class DraftTrimInput {
    +length_m, beam_m, max_draft_m
    +speed_knots
    +cargo_weight_t, max_cargo_t
    +wave_height_m, water_depth_m
  }
  class DraftTrimResult {
    +optimal_trim_m
    +optimal_mean_draft_m
    +fuel_savings_pct
    +notes: list[str]
  }
  DraftTrimInput ..> DraftTrimResult : optimize(input)

  RoutingStrategy ..> VesselConstraints : uses
  VesselConstraints ..> DraftTrimInput : feeds
```

## Class diagram — AI subsystem

```mermaid
classDiagram
  class AIService {
    +handle_reroute_request()
    +generate_recommendations()
    +scan_anomalies()
    +predict_eta()
    -_ai_repo
    -_route_repo
    -_vessel_repo
  }
  class AnomalyDetector
  class ETAPredictor
  class RerouteEngine
  class RecommendationEngine
  class WebSocketManager {
    +connect(ws, vessel_id, company_id)
    +broadcast(message)
    +send_to_vessel(vessel_id, message)
    +send_to_company(company_id, message)
  }

  AIService o-- AnomalyDetector
  AIService o-- ETAPredictor
  AIService o-- RerouteEngine
  AIService o-- RecommendationEngine
  AIService ..> WebSocketManager : emits notifications
```

## Class diagram — auth + tenancy

```mermaid
classDiagram
  class Company {
    +name
    +email
    +status
    +api_keys: list~ApiKey~
  }
  class User {
    +company_id: ObjectId
    +email
    +password_hash
    +role: admin|operator|viewer
    +is_active
  }
  class FleetProfile {
    +company_id
    +name
    +vessel_ids
    +default_optimization_mode
    +emission_target_kg_co2_per_nm
  }
  class BillingData {
    +company_id (unique)
    +billing_email
    +subscription_tier
    +usage: list~UsageRecord~
  }
  class Vessel {
    +company_id
    +imo_number
    +vessel_type
    +specs: VesselSpecs
  }

  Company "1" --> "*" User
  Company "1" --> "*" FleetProfile
  Company "1" --> "1" BillingData
  Company "1" --> "*" Vessel
  FleetProfile "1" --> "*" Vessel : groups
```

## Sequence — `/routes/calculate` happy path

```mermaid
sequenceDiagram
  autonumber
  participant Client
  participant Router as routes router
  participant Cache as Route LRU cache
  participant Strategy
  participant Optimizer as DraftTrim optimizer
  participant Repo as Route + History repos

  Client->>Router: POST /api/v1/routes/calculate
  Router->>Cache: get(start, end, vessel, mode)
  alt cache hit
    Cache-->>Router: cached waypoints + stats
  else cache miss
    Router->>Strategy: calculate_route(graph, ...)
    Strategy-->>Router: path: list[Waypoint]
    Router->>Router: build waypoints + base stats
    Router->>Optimizer: optimize(input) if cargo data
    Optimizer-->>Router: optimal trim + fuel_savings_pct
    Router->>Cache: set(key, waypoints + stats)
  end
  Router->>Repo: persist route + RouteHistory
  Router-->>Client: 200 + waypoints + stats + cache_hit
```

## Sequence — JWT login + protected call

```mermaid
sequenceDiagram
  autonumber
  participant Client
  participant Auth as auth router
  participant Sec as security helpers
  participant Repo as UserRepository
  participant Protected as any protected endpoint
  participant Dep as get_current_user

  Client->>Auth: POST /auth/login { email, password }
  Auth->>Repo: get_by_email
  Repo-->>Auth: User
  Auth->>Sec: verify_password(hash)
  Sec-->>Auth: ok
  Auth->>Sec: issue_access_token(user_id, company_id, role)
  Sec-->>Auth: jwt
  Auth-->>Client: { access_token, expires_in }

  Client->>Protected: Authorization: Bearer jwt
  Protected->>Dep: dependency
  Dep->>Sec: decode_access_token
  Sec-->>Dep: payload
  Dep->>Repo: get_by_id(user_id)
  Repo-->>Dep: User
  Dep-->>Protected: User
  Protected-->>Client: 200
```

## Sequence — background job

```mermaid
sequenceDiagram
  autonumber
  participant Admin
  participant JobsRouter as jobs router
  participant Queue as InProcessTaskQueue
  participant Handler as job handler
  participant Domain as core service

  Admin->>JobsRouter: POST /api/v1/jobs/grib_ingest { path: "..." }
  JobsRouter->>Queue: enqueue(name, payload)
  Queue-->>JobsRouter: Job(id, status=pending)
  JobsRouter-->>Admin: 200 { id, status }
  par worker thread
    Queue->>Handler: fn(**payload)
    Handler->>Domain: load_auto(path)
    Domain-->>Handler: CurrentGrid
    Handler-->>Queue: result dict
  end
  Admin->>JobsRouter: GET /api/v1/jobs/{id}
  JobsRouter->>Queue: get(id)
  Queue-->>JobsRouter: Job(status=completed, result)
  JobsRouter-->>Admin: 200 { ..., status, result }
```

## Deployment

```mermaid
flowchart LR
  subgraph k8s[Kubernetes cluster<br/>deploy/kubernetes]
    direction TB
    Ingress[Ingress / LoadBalancer]
    subgraph App[ClearWake API Pods]
      FA1[FastAPI + InProcessTaskQueue]
      FA2[FastAPI + InProcessTaskQueue]
    end
    Prom[Prometheus<br/>deploy/prometheus]
  end

  subgraph Mongo[MongoDB Atlas / managed]
    DB[(clearwake DB)]
  end

  subgraph Upstream[Upstream APIs]
    OM[Open-Meteo Marine]
    RV[RainViewer]
  end

  Client[Browser / B2B integrator] -->|HTTPS| Ingress
  Ingress --> FA1
  Ingress --> FA2
  FA1 --> DB
  FA2 --> DB
  FA1 -->|httpx| OM
  FA2 -->|httpx| OM
  FA1 -.metrics.-> Prom
  FA2 -.metrics.-> Prom

  classDef ext fill:#1a2332,stroke:#94a3b8,color:#f1f5f9;
  class Upstream,Mongo ext
```

Each API pod runs its own `InProcessTaskQueue` — jobs that need cross-pod coordination should move to RQ + Redis (the `TaskQueue` interface is the swap-point).

## API surface (high level)

| Group              | Path prefix                | Notes |
|--------------------|---------------------------|-------|
| Auth (JWT)         | `/api/v1/auth`             | login, register (admin), bootstrap-admin, me |
| Routes             | `/api/v1/routes`           | calculate (LRU-cached), batch, history, landmask |
| Routing meta       | `/api/v1/routing`          | strategy info |
| Vessels            | `/api/v1/vessels`          | CRUD, subtype factory |
| Fleet              | `/api/v1/fleet`            | legacy fleet ops |
| Fleet profiles     | `/api/v1/fleet-profiles`   | tenant-scoped, issue #86 |
| Companies          | `/api/v1/companies`        | tenant management |
| Billing data       | `/api/v1/billing-data`     | one per company, issue #86 |
| Zones              | `/api/v1/zones`            | spatial zones |
| AI                 | `/api/v1/ai`               | reroute, recommendations, anomalies, ETA |
| AI notifications   | `/ws/ai/notifications`     | WebSocket |
| Weather            | `/api/v1/weather`          | marine, route weather, currents |
| Analytics          | `/api/v1/analytics`        | aggregates |
| Port scheduling    | `/api/v1/port-scheduling`  |  |
| Optimization       | `/api/v1/optimization`     | draft/trim helper |
| Jobs (admin)       | `/api/v1/jobs`             | issue #85 |

Full OpenAPI is available at `/docs` (Swagger UI) and `/openapi.json` once the app is running.
