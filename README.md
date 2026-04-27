# NubeRush

Backend de NubeRush con FastAPI, SQLAlchemy 2.0, Alembic y PostgreSQL/Supabase.

## Estado

La Sesion 1 deja cerrada la capa de datos y migraciones:

- `backend/app/db/models.py` es la fuente de verdad del schema.
- Alembic versiona y aplica los cambios de schema.
- La migracion inicial es `backend/alembic/versions/7a5ba742b190_initial_schema.py`.
- `updated_at` se mantiene a nivel de base de datos con triggers PostgreSQL.

## Base de datos

Desde `backend/`:

```bash
python -m alembic upgrade head
```

Para resetear el schema versionado:

```bash
python -m alembic downgrade base
```

El proyecto usa `DATABASE_URL` desde `backend/.env`. Debe apuntar a PostgreSQL/Supabase.

## Arranque local

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload
```

Todavia no incluye autenticacion completa, RBAC aplicado en endpoints, integracion de pagos ni apps cliente/driver.
