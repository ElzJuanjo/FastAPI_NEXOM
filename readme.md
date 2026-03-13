# NexOS - Automatización de e-commerce

### Sprint 1

| Archivo                           | Propósito                                        |
| --------------------------------- | ------------------------------------------------- |
| .env                              | Variables de entorno                              |
| infra/config/database.py          | Conexión async a Postgres, Settings con Pydantic |
| domain/entities/base.py           | Base, UUIDPk, TimestampMixin, todos los Enums     |
| domain/entities/user.py           | Entidades User y UserAuthProvider                 |
| domain/entities/__init__.py | Registry de entidades para metadata               |
| main.py                           | FastAPI con lifespan, CORS, health check          |



Ejecución modo desarrollador: `uvicorn main:app --reload --app-dir src`
