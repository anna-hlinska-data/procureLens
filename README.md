# 🔍 EU ProcureLens
**AI-Powered Procurement Risk Detection System**
Cardiff Metropolitan University · IST5001 · 2025/2026

ProcureLens takes public procurement contract data (EU TED format, CSV/Excel), normalises it,
predicts the expected contract value with a Random Forest model and flags contracts whose actual
value deviates strongly from the prediction.

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    NGINX :80                        │
│         Reverse proxy for all services              │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
    ┌──────▼──────┐           ┌───────▼──────┐
    │   DJANGO    │           │  STREAMLIT   │
    │  :8000      │           │   :8501      │
    │  Backend    │◄──────────│  Frontend    │
    │  REST API   │ requests  │  6-tab UI    │
    └──────┬──────┘           └──────────────┘
           │
    ┌──────▼──────┐    ┌───────────────┐
    │ PostgreSQL  │    │   REDIS       │
    │   :5432     │    │   :6379       │
    │  Database   │    │ Celery Broker │
    └─────────────┘    └───────────────┘
```

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/anna-hlinska-data/procureLens.git
cd procureLens

# 2. Configure environment
cp backend/.env.example backend/.env
#    fill in SECRET_KEY, POSTGRES_PASSWORD (also inside DATABASE_URL)
#    and DJANGO_SUPERUSER_PASSWORD

# 3. Add the trained model (see below)

# 4. Start everything
docker-compose up --build
```

| Service | URL |
|---------|-----|
| Streamlit UI | http://localhost |
| API docs (Swagger) | http://localhost/api/docs/ |
| Django Admin | http://localhost/admin/ |

The admin account is created on first start from `DJANGO_SUPERUSER_EMAIL` /
`DJANGO_SUPERUSER_PASSWORD` in `backend/.env`.

### Model file

The trained Random Forest model (`rf_model.pkl`, ~12 MB) is not stored in git.
Download it from the [Releases](https://github.com/anna-hlinska-data/procureLens/releases) page
and put it into:

```
frontend/models/rf_model.pkl
```

**Without this file the app runs in DEMO MODE** (still works, uses country baselines).

---

## 📁 Project Structure

```
procureLens/
├── docker-compose.yml          ← Start everything here
│
├── backend/                    ← Django REST API
│   ├── procurelens/            ← Django settings, urls, celery
│   ├── authentication/         ← User auth (JWT)
│   ├── procurement/            ← Risk analysis API
│   │   ├── models.py           ← ContractAnalysis, ContractResult
│   │   ├── views.py            ← upload, list, get endpoints
│   │   ├── serializers.py
│   │   └── urls.py
│   ├── manage.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── .env.example            ← Copy to .env
│
├── frontend/                   ← Streamlit UI
│   ├── app.py                  ← Main app (6 tabs)
│   ├── csv_converter.py        ← Format conversion (CSV, Excel, PDF)
│   ├── mapping.py              ← Fuzzy column mapping
│   ├── cleaning.py             ← Data cleaning
│   ├── risk_engine.py          ← ML risk scoring
│   ├── models/                 ← rf_model.pkl (download separately)
│   ├── requirements.txt
│   └── Dockerfile
│
├── samples/                    ← Example TED contract files
│
└── nginx/
    └── nginx.conf              ← Reverse proxy config
```

Folders `frontend/input_files`, `original_files`, `converted_csv`, `mapped_files` and
`cleaned_files` are created at runtime by the pipeline and are not tracked in git.

---

## 🔌 API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/v1/auth/register/` | Register new user |
| POST | `/api/v1/auth/login/` | Get JWT tokens |
| POST | `/api/v1/auth/token/refresh/` | Refresh token |
| GET  | `/api/v1/auth/profile/` | User profile |
| POST | `/api/v1/procurement/upload/` | Upload & analyse file |
| GET  | `/api/v1/procurement/analyses/` | List all analyses |
| GET  | `/api/v1/procurement/analyses/<id>/` | Get full results |
| GET  | `/api/v1/procurement/analyses/<id>/high-risk/` | High risk only |
| GET  | `/api/docs/` | Swagger documentation |

---

## 🔴🟡🟢 Risk Score Formula

```
Risk Score = |actual_value - predicted_value| / predicted_value

🔴 HIGH:   score > 0.5  OR  2+ critical fields missing
🟡 MEDIUM: score 0.2–0.5
🟢 LOW:    score < 0.2
```

---

## Useful Commands

```bash
docker-compose up --build                              # start all services
docker-compose down                                    # stop all services
docker-compose logs -f backend                         # follow backend logs
docker-compose exec backend python manage.py shell     # Django shell
docker-compose exec backend python manage.py migrate   # run migrations
docker-compose exec backend python manage.py test      # run tests
```

---

## Research Foundation

- **Dataset:** 10,038,018 EU TED contracts (2006–2025)
- **Model:** Random Forest — CV R²=0.2795, Test R²=0.2613
- **Top predictor:** Country of origin (24.39% importance)
- **Publication:** IJACSA paper (accepted)

---

## Author

**Anna Hlinska** — [github.com/anna-hlinska-data](https://github.com/anna-hlinska-data)
