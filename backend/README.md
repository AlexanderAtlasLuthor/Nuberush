# NubeRush Backend

## Schema y migraciones

- La fuente de verdad del schema es `app/db/models.py`.
- Alembic versiona el schema en `alembic/versions/`.
- La migracion inicial es `7a5ba742b190_initial_schema.py`.
- PostgreSQL/Supabase es el target de base de datos.
- `updated_at` se actualiza con triggers DB-level (`set_updated_at()`).

## Levantar base desde cero

```bash
python -m alembic upgrade head
```

## Resetear schema versionado

```bash
python -m alembic downgrade base
```

`DATABASE_URL` se lee desde `.env` y debe apuntar a PostgreSQL/Supabase.
