# 🏟️ VenueFlow — Smart Stadium Experience Platform

> AI-powered crowd management for large-scale sporting venues.
> Built for **PromptWars: Virtual** — Physical Event Experience challenge.

[![Cloud Run](https://img.shields.io/badge/Deployed_on-Cloud_Run-blue?logo=google-cloud)](https://cloud.google.com/run)
[![Vertex AI](https://img.shields.io/badge/AI-Vertex_AI_Gemini-orange?logo=google)](https://cloud.google.com/vertex-ai)

---

## 🎯 Problem Statement

Large-scale sporting venues face three core challenges:
- **Crowd movement** — dangerous bottlenecks at exits and gates
- **Waiting times** — long unpredictable queues at concessions, restrooms
- **Real-time coordination** — staff unable to respond fast enough to emerging hotspots

VenueFlow solves all three with a dual-mode AI platform.

---

## ✨ Features

### 🎟️ Fan Mode
| Feature | Description |
|---|---|
| **Crowd Analyzer** | Upload a crowd photo → Gemini Vision estimates density, wait time, recommends action |
| **Route Finder** | GPS-based routing to nearest uncrowded exit/food/restroom/medical |
| **AI Chat Assistant** | Natural language Q&A in 7+ languages |
| **Multilingual Support** | All responses translated via Cloud Translation API |

### 👮 Staff Mode
| Feature | Description |
|---|---|
| **Live Heatmap** | Real-time zone occupancy from Firebase, auto-refreshes every 30s |
| **Alert Broadcast** | Create multilingual alerts, stored in Firebase, translated instantly |
| **AI Staff Insights** | Gemini analyses all zones and generates deployment recommendations |
| **Zone Updates** | Staff manually update occupancy readings in real-time |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────┐
│       React Frontend (Cloud Run)      │
│  Fan View │ Staff View │ AI Chat      │
└──────────────┬───────────────────────┘
               │ REST API
┌──────────────▼───────────────────────┐
│      FastAPI Backend (Cloud Run)      │
│  /api/fan/* │ /api/staff/* │ /health  │
└───┬──────────────────┬───────────────┘
    │                  │
┌───▼──────────┐  ┌────▼────────────┐
│ Vertex AI    │  │ Firebase RTDB   │
│ Gemini Flash │  │ (Live zones +   │
│ Vision + Chat│  │  alerts)        │
└──────────────┘  └─────────────────┘
    │
┌───▼──────────────────────────────────┐
│ Google Maps Platform (Routes +        │
│ Places Nearby)                        │
└──────────────────────────────────────┘
    │
┌───▼──────────────────────────────────┐
│ Cloud Translation API                 │
│ (10+ languages, TTL-cached)          │
└──────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- GCP project with billing enabled
- APIs enabled: Vertex AI, Maps Platform, Cloud Translation, Firebase

### Local Development

```bash
# Clone and setup
git clone https://github.com/YOUR_USERNAME/venueflow
cd venueflow/backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run backend
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# Open frontend (in another terminal)
cd ../frontend
python -m http.server 3000
# Visit http://localhost:3000
```

### Run Tests

```bash
cd backend
pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## ☁️ Deploy to Cloud Run

### Option 1: Cloud Build (Recommended)

```bash
gcloud builds submit --config cloudbuild.yaml \
  --project YOUR_PROJECT_ID
```

### Option 2: Manual Deploy

```bash
# Backend
gcloud run deploy venueflow-backend \
  --source ./backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=YOUR_PROJECT_ID,GOOGLE_MAPS_API_KEY=YOUR_KEY

# Frontend
gcloud run deploy venueflow-frontend \
  --source ./frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

---

## 🔑 Environment Variables

| Variable | Description |
|---|---|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_LOCATION` | Vertex AI region (default: us-central1) |
| `GEMINI_MODEL` | Gemini model (default: gemini-2.0-flash-001) |
| `GOOGLE_MAPS_API_KEY` | Maps Platform API key |
| `FIREBASE_DATABASE_URL` | Firebase RTDB URL |
| `FIREBASE_CREDENTIALS_PATH` | Path to service account JSON |

---

## 🧪 Test Coverage

```
tests/test_venueflow.py
├── TestImageUtils        (6 tests) — LANCZOS downscale, size validation
├── TestSchemas           (4 tests) — Pydantic validation, bounds checking
├── TestHealth            (4 tests) — /health endpoint, service status
├── TestFanAnalyze        (3 tests) — Image upload, MIME type, 503 handling
├── TestFanChat           (2 tests) — AI chat, empty message validation
├── TestFanRoute          (2 tests) — Route response, invalid destination
├── TestStaffHeatmap      (2 tests) — Zone fetch, Firebase failure
└── TestStaffAlerts       (2 tests) — Alert creation, message validation
```

---

## 🔒 Security

- All secrets via environment variables (never hardcoded)
- Non-root Docker user
- Input validation via Pydantic on every endpoint
- Image size and MIME type validation before AI processing
- GZip middleware for response compression
- Security headers via nginx

---

## 🌐 Google Services Used

1. **Vertex AI (Gemini 2.0 Flash)** — Crowd photo analysis + AI chat + staff insights
2. **Google Maps Platform** — Walking directions + Places Nearby
3. **Cloud Translation API** — 10+ language support, TTL-cached
4. **Firebase Realtime Database** — Live zone data + alert persistence
5. **Cloud Run** — Serverless deployment for both frontend and backend

---

Built with ❤️ for PromptWars: Virtual — Physical Event Experience Challenge
