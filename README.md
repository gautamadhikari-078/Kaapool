# KAAPOOL

**Kaapool** is a scalable, modern car-pooling and ride-sharing web platform built using Python and Django. This repository establishes the technical architecture, custom authentication user model, modular application layout, and Django REST Framework API structure designed to serve both the Kaapool website and future mobile applications.

---

## Technology Stack

- **Backend:** Python 3.10+, Django 5.2 LTS, Django REST Framework (`djangorestframework`)
- **Frontend:** Django Templates, HTML5, CSS3, JavaScript (Bootstrap 5 ready)
- **Environment:** `python-dotenv` for configuration, Virtual Environment (`.venv`)
- **Database:** SQLite (Local development default), PostgreSQL (Production ready)
- **Static & Media Management:** Django Staticfiles & Media directory structure
- **Version Control:** Git & GitHub-ready structure

---

## Project Architecture

```
kaapool/
├── manage.py
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── __init__.py
│   ├── core/           # Public informational pages (Home, About, How It Works, Safety, Contact)
│   ├── accounts/       # User management, Custom User Model, Auth, Dashboard, Profile
│   ├── rides/          # Ride creation, search, detail, and ride offering logic
│   ├── bookings/       # Passenger ride bookings & status management
│   ├── payments/       # Transaction history & payment structure placeholder
│   ├── notifications/  # System notifications model & routes
│   └── messaging/      # Driver-passenger inbox communication model & routes
├── templates/
│   ├── base.html
│   ├── components/     # navbar.html, footer.html, messages.html, user_menu.html
│   ├── core/
│   ├── accounts/
│   ├── dashboard/
│   ├── rides/
│   ├── bookings/
│   ├── payments/
│   ├── notifications/
│   └── messaging/
├── static/
│   ├── css/main.css
│   ├── js/main.js
│   └── images/
└── media/              # User photo & document uploads
```

---

## Local Development & Setup Instructions

### 1. Prerequisites
Ensure Python 3.10+ is installed on your system.

### 2. Virtual Environment Setup

Create and activate the virtual environment (`.venv`):

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Environment Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Adjust `.env` variables if necessary (e.g. `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`).

### 5. Run Database Migrations

```bash
python manage.py check
python manage.py makemigrations
python manage.py migrate
```

### 6. Create Superuser (Admin Access)

```bash
python manage.py createsuperuser
```

### 7. Run Development Server

```bash
python manage.py runserver
```

Open your browser and navigate to:
- **Web App:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Django Admin:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
- **REST API v1 Root:** [http://127.0.0.1:8000/api/v1/](http://127.0.0.1:8000/api/v1/)

---

## Available URL Routes Summary

### Public Informational Routes
- `/` — Homepage
- `/about/` — About Kaapool
- `/how-it-works/` — How It Works
- `/safety/` — Safety Guidelines
- `/contact/` — Contact Support

### Authentication & Account Area
- `/signup/` — Registration
- `/login/` — Login
- `/logout/` — Logout
- `/dashboard/` — User Dashboard
- `/profile/` — User Profile

### Carpooling & Ride Routes
- `/rides/` — List / Search Rides
- `/rides/search/` — Search Rides Query
- `/rides/create/` — Offer a Ride
- `/rides/<id>/` — Ride Detail View
- `/rides/my-rides/` — User's Offered Rides

### Bookings & Dashboard Management
- `/bookings/` — List / My Bookings
- `/bookings/<id>/` — Booking Detail
- `/inbox/` — User Inbox & Messages
- `/payments/` — Payment Transaction History
- `/notifications/` — User Notifications

### REST API v1 (DRF Endpoints for Web & Future Mobile App)
- `/api/v1/auth/register/` — User Registration API
- `/api/v1/users/me/` — User Profile API
- `/api/v1/rides/` — Rides List / Create API
- `/api/v1/bookings/` — Bookings API
- `/api/v1/payments/` — Payments API
- `/api/v1/notifications/` — Notifications API
- `/api/v1/messages/` — Messages API

---

## Future Development Roadmap

1. **Phase 1 — Foundation (Current):** Project setup, virtualenv, apps architecture, custom user model, templates, static files, DRF API endpoints.
2. **Phase 2 — Website UI & Styling:** Page-by-page visual design, modern layouts, responsive components.
3. **Phase 3 — Interactive User Features:** Detailed profile settings, avatar upload, user verification workflows.
4. **Phase 4 — Core Carpooling & Booking Logic:** Real-time seat allocation, booking confirmation, ride cancellation rules.
5. **Phase 5 — Messaging & Notifications:** Direct user messaging system and email/SMS notification integration.
6. **Phase 6 — Payment Gateway:** Payment gateway integration (Stripe/Razorpay), refund management, driver payouts.
7. **Phase 7 — Location & Maps:** Google Maps / Mapbox integration for pickup/drop routes and distance calculation.
8. **Phase 8 — Trust & Safety:** Driver license verification, background checks, user ratings & reviews system.
9. **Phase 9 — Mobile Application:** Native or cross-platform mobile apps utilizing the Django REST API backend.
