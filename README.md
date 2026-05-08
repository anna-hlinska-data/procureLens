# 🔍 EU ProcureLens
**AI-Powered Procurement Risk Detection System**
Cardiff Metropolitan University · IST5001 · 2025/2026

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
    ┌──────▼──────┐    ┌──────────────┐
    │ PostgreSQL  │    │   REDIS      │
    │   :5432     │    │   :6379      │
    │  Database   │    │  Celery Broker│
    └─────────────┘    └──────────────┘
```

---

## ⚠️ BEFORE YOU START: Save Your RF Model

In your Jupyter notebook, run:
```python
import pickle, os
os.makedirs('models', exist_ok=True)
pickle.dump(rf_model, open('models/rf_model.pkl', 'wb'))
```

Then copy `rf_model.pkl` into:
```
procurelens/frontend/models/rf_model.pkl
```

**Without this file the app runs in DEMO MODE** (still works, uses country baselines).

---

## 🚀 Quick Start

```bash
# 1. Clone or unzip the project
cd procurelens

# 2. Start everything
docker-compose up --build

# 3. Open the app
# Streamlit UI:  http://localhost
# Django API:    http://localhost/api/docs/
# Django Admin:  http://localhost/admin/
```

**Default admin login:**
- Email: `admin@procurelens.com`
- Password: `admin123`

---

## 📁 Project Structure

```
procurelens/
├── docker-compose.yml          ← Start everything here
│
├── backend/                    ← Django REST API
│   ├── wfmonit/                ← Django settings
│   ├── authentication/         ← User auth (JWT) ✅ ready
│   ├── procurement/            ← Risk analysis API 🆕
│   │   ├── models.py           ← ContractAnalysis, ContractResult
│   │   ├── views.py            ← upload, list, get endpoints
│   │   ├── serializers.py
│   │   └── urls.py
│   ├── manage.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── .env                    ← ⚠️ Edit email settings
│
├── frontend/                   ← Streamlit UI
│   ├── app.py                  ← Main app (6 tabs) ✅
│   ├── risk_engine.py          ← ML risk scoring 🆕
│   ├── mapping.py              ← Column mapping ✅
│   ├── cleaning.py             ← Data cleaning ✅
│   ├── csv_converter.py        ← Format conversion ✅
│   ├── models/
│   │   └── rf_model.pkl        ← ⚠️ Copy from Jupyter
│   ├── requirements.txt
│   └── Dockerfile
│
└── nginx/
    └── nginx.conf              ← Reverse proxy config
```

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
# Start all services
docker-compose up --build

# Stop all services
docker-compose down

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Run Django shell
docker-compose exec backend python manage.py shell

# Run migrations manually
docker-compose exec backend python manage.py migrate

# Run tests (Mohammad)
docker-compose exec backend python manage.py test
docker-compose exec backend pytest tests/

# Restart single service
docker-compose restart backend
docker-compose restart frontend
```

---

## Team

| Name | Role |
|------|------|
| **Anna Hlinska** | ML research · risk_engine.py · Streamlit UI · Django procurement app |
| **Mohammad Ishtiaque Hossain** | Testing · Docker · CI/CD · Deployment |

---

## Research Foundation

- **Dataset:** 10,038,018 EU TED contracts (2006–2025)
- **Model:** Random Forest — CV R²=0.2795, Test R²=0.2613
- **Top predictor:** Country of origin (24.39% importance)
- **Publication:** IJACSA paper (accepted)
