# SGOI — Sistema de Gestión Operativa e Inventario

MVP Backend · FastAPI + PostgreSQL + SQLAlchemy + Alembic

---

## Requisitos
- Docker + Docker Compose

## Inicio rápido

```bash
# 1. Clonar y entrar al proyecto
cd sgoi

# 2. Crear el archivo de entorno
cp .env.example .env

# 3. Levantar los servicios
docker compose up -d --build

# 4. Ejecutar migraciones
docker compose exec api alembic upgrade head

# 5. Verificar
curl http://localhost:8000/health
# → {"status":"ok","version":"0.1.0"}

# 6. Ver documentación interactiva
# http://localhost:8000/docs
```

## Comandos Alembic útiles

```bash
# Aplicar todas las migraciones
docker compose exec api alembic upgrade head

# Ver estado actual
docker compose exec api alembic current

# Ver historial
docker compose exec api alembic history

# Revertir última migración
docker compose exec api alembic downgrade -1

# Generar nueva migración automática (tras cambiar modelos)
docker compose exec api alembic revision --autogenerate -m "descripcion del cambio"
```

## Estructura del proyecto

```
sgoi/
├── app/
│   ├── core/
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   └── database.py      # Engine, SessionLocal, Base, get_db()
│   ├── models/
│   │   ├── __init__.py      # Re-exports all models
│   │   ├── part.py          # Part (catálogo de equipos)
│   │   ├── asset.py         # Asset (equipo físico) + AssetStatus
│   │   └── intervention.py  # Intervention, InterventionAsset, Evidence
│   ├── schemas/             # Pydantic schemas (próximo paso)
│   ├── api/routes/          # Endpoints FastAPI (próximo paso)
│   ├── services/            # Lógica de negocio (próximo paso)
│   └── main.py              # App FastAPI
├── alembic/
│   ├── env.py               # Config de Alembic
│   ├── script.py.mako       # Template de migraciones
│   └── versions/
│       └── 0001_initial.py  # Migración inicial (todas las tablas)
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── .gitignore
```

## Modelo de datos

| Tabla               | Descripción                              |
|---------------------|------------------------------------------|
| `parts`             | Catálogo de modelos de equipo (del TAT)  |
| `assets`            | Equipos físicos (serializados o no)      |
| `interventions`     | Reportes de intervención en campo        |
| `intervention_assets` | Equipos asociados a una intervención  |
| `evidences`         | Fotos/archivos adjuntos a reportes       |

## Próximos pasos

- [ ] Schemas Pydantic (request/response)
- [ ] Endpoints: `/import-excel`, `/assets`, `/interventions`
- [ ] Servicio de importación Excel (openpyxl)
- [ ] Generación de PDF (reportlab)
- [ ] Upload de evidencias
