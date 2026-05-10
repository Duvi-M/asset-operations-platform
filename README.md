# Field Operations & Inventory Management System

A full-stack web application for managing field operations, equipment inventory, technical interventions, QR-based asset lookup, evidence uploads, and PDF reporting.

This project is designed as a general-purpose operational system that can be adapted for maintenance teams, technical service providers, internal asset tracking, inspection workflows, and field support operations.

## Overview

The application helps teams keep a structured record of physical assets and field work.

It includes:

- Inventory and asset management.
- QR-based asset scanning.
- Intervention reporting.
- Evidence upload with image validation.
- PDF report generation.
- Excel-based inventory import.
- JWT authentication with user roles.
- Audit logging for key actions.
- Progressive Web App support for mobile usage.

## Features

- User authentication with JWT.
- Role-based access control for `admin` and `technician` users.
- Admin bootstrap endpoint for creating the first administrator.
- Asset catalog with filtering and pagination.
- Parts catalog.
- QR code generation for assets.
- QR / serial / internal-code scan lookup.
- Field intervention creation and tracking.
- Association of assets with interventions.
- Image evidence upload.
- Cloudinary support for production image storage.
- Local media storage fallback for development.
- PDF generation for intervention reports.
- Excel import workflow for bulk inventory loading.
- Audit logging for login, scans, interventions, asset association, and evidence uploads.
- Health check endpoint with database validation.
- Request ID middleware for backend traceability.
- React dashboard with protected routes.
- Mobile-friendly PWA setup with service worker and offline page.

## Tech Stack

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- Pydantic
- JWT-style HMAC tokens
- ReportLab
- Pillow
- OpenPyXL
- Cloudinary
- Uvicorn

### Frontend

- React
- Vite
- React Router
- jsQR
- CSS
- Service Worker / PWA manifest

### Infrastructure

- Docker
- Docker Compose
- Render-ready backend startup script
- Vercel frontend configuration

## Project Structure

```text
.
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   ├── router.py
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── assets.py
│   │       ├── import_excel.py
│   │       ├── interventions.py
│   │       └── parts.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── logging.py
│   │   └── security.py
│   ├── models/
│   ├── schemas/
│   ├── scripts/
│   ├── services/
│   └── main.py
├── alembic/
├── public/
│   ├── manifest.webmanifest
│   ├── offline.html
│   └── sw.js
├── src/
│   ├── auth/
│   ├── components/
│   ├── pages/
│   ├── services/
│   ├── App.jsx
│   ├── main.jsx
│   └── registerServiceWorker.js
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── package.json
├── start.sh
├── vercel.json
└── vite.config.js
```

## Main Workflows

### Authentication

Users sign in with email and password. The backend returns an access token used by the frontend to access protected API routes.

Supported roles:

- admin
- technician

Admins can access administrative workflows such as asset creation, part management, and Excel imports. Technicians can access operational workflows such as asset lookup and intervention reporting.

### Asset Management

The system stores physical assets with identifying information such as serial number, internal code, part reference, status, and location.

Assets can be searched, filtered, viewed, and linked to interventions.

### QR Scanning

Each asset can have a generated QR code.

The scan endpoint can resolve assets by:

- Internal QR format.
- Serial number.
- Internal asset code.

The frontend includes camera-based QR scanning using jsQR.

### Interventions

Users can create intervention records with field details such as type, location, technician, date, description, associated assets, and supporting evidence.

### Evidence Uploads

Intervention evidence can be uploaded as images.

In production, image files can be stored using Cloudinary. In local development, the application can fall back to local media storage.

### PDF Reports

Interventions can be exported as PDF reports, including structured intervention data and available evidence.

### Excel Import

Admins can import inventory data from .xlsx files. The import process supports validation, row-level error handling, and upsert behavior for parts and assets.

### Audit Logging

Important user actions are recorded in audit logs, including authentication, scans, intervention creation, asset association, and evidence uploads.

## API

The backend exposes a versioned REST API under:

/api/v1

Main API areas:

- /api/v1/auth
- /api/v1/parts
- /api/v1/assets
- /api/v1/interventions
- /api/v1/import

Interactive API documentation:

/docs

Health check:

/health

## Local Development

### Prerequisites

- Docker
- Docker Compose
- Node.js
- npm

### Environment Variables

Create a .env file in the project root.

Example:

```env
DATABASE_URL=postgresql://asset_ops_user:asset_ops_pass@db:5432/asset_ops_db
AUTO_CREATE_TABLES=false
AUTH_SECRET_KEY=replace-this-with-a-secure-secret
ACCESS_TOKEN_EXP_MINUTES=720
AUTH_ISSUER=asset-operations-platform
MEDIA_DIR=/app/media
CLOUDINARY_URL=
```

For production, always set a secure AUTH_SECRET_KEY.

### Start Backend and Database

```bash
docker compose up -d --build
```

### Run Migrations

```bash
docker compose exec api alembic upgrade head
```

### Check Backend Health

```bash
curl http://localhost:8000/health
```

### Open API Docs

```text
http://localhost:8000/docs
```

## Frontend Development

Install dependencies:

```bash
npm install
```

Start the Vite development server:

```bash
npm run dev
```

Build for production:

```bash
npm run build
```

Preview production build:

```bash
npm run preview
```

## Database Migrations

Apply all migrations:

```bash
docker compose exec api alembic upgrade head
```

Check current migration:

```bash
docker compose exec api alembic current
```

View migration history:

```bash
docker compose exec api alembic history
```

Create a new autogenerated migration:

```bash
docker compose exec api alembic revision --autogenerate -m "describe_change"
```

## Deployment Notes

### Backend

The backend is prepared for deployment on platforms such as Render.

The included startup script runs migrations before starting the API:

```bash
./start.sh
```

Equivalent command:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Frontend

The frontend includes a vercel.json configuration for Vercel deployment with SPA rewrites.

Set the backend API URL in Vercel using:

```env
VITE_API_URL=https://your-backend-url.example.com
```

## Security Notes

Before publishing or deploying:

- Do not commit .env files.
- Use a strong production AUTH_SECRET_KEY.
- Review CORS settings for your production domain.
- Keep database credentials outside the repository.
- Avoid committing generated files such as node_modules, build artifacts, local media, cache files, or .DS_Store.
- Rotate any credentials that were ever committed accidentally.

## Example Use Cases

- Field service reporting.
- Maintenance operations.
- Technical inspection workflows.
- Equipment lifecycle tracking.
- Internal asset inventory systems.
- Evidence-based work documentation.
- Operational reporting for distributed teams.

## License

Add a license before publishing this repository.

Common options:

- MIT for permissive open-source use.
- Apache-2.0 for permissive use with explicit patent terms.
- GPL-3.0 for copyleft/open redistribution requirements.

## Nota adicional

Pequeña nota aparte: para publicarlo abierto, revisaría antes `.env`, `node_modules`, `dist`, `out`, `__pycache__` y `.DS_Store`, porque en este repo aparecen algunos de esos archivos/carpetas. No cambié nada, solo te lo marco para cuando hagas el clone/rename.