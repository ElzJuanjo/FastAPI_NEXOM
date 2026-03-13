# NexOS - Automatización de e-commerce

### Sprint 1 - Fundación

| Archivo                      | Propósito                                        |
| ---------------------------- | ------------------------------------------------- |
| `.env`                     | Variables de entorno                              |
| `infra/config/database.py` | Conexión async a Postgres, Settings con Pydantic |
| `domain/entities/base.py`  | Base, UUIDPk, TimestampMixin, todos los Enums     |
| `domain/entities/user.py`  | Entidades User y UserAuthProvider                 |
| `domain/entities/`         | Registry de entidades para metadata               |
| `main.py`                  | FastAPI con lifespan, CORS, health check          |

### Sprint 2 - Autenticación

| Archivo                                          | Propósito                                                  |
| ------------------------------------------------ | ----------------------------------------------------------- |
| `.env`                                         | (agregar JWT vars)                                          |
| `infra/config/database.py`                     | (agregar JWT al Settings)                                   |
| `infra/config/security.py`                     | Hashing y generación/verificación de JWT.                 |
| `app/dto/auth_dto.py`                          | DTOs para autenticación: request bodies y response bodies. |
| `domain/repositories/user_repository.py`       | Contrato de acceso a datos para User y UserAuthProvider.    |
| `infra/adapters/user_sqlalchemy.py`            | Implementación SQLAlchemy async del UserRepository.        |
| `app/use_cases/auth_register.py`               | Registro de usuario por email.                              |
| `app/use_cases/auth_login.py`                  | Login por email + password.                                 |
| `app/use_cases/auth_refresh.py`                | Renovar access token usando refresh token.                  |
| `interfaces/dependencies/auth_dependencies.py` | Dependencias de inyección para auth.                       |
| `interfaces/api/auth_router.py`                | Endpoints de autenticación: register, login, refresh, me.  |
| `main.py`                                      | (incluir auth_router)                                       |

| Endpoint                   | Descripción                                           |
| -------------------------- | ------------------------------------------------------ |
| POST /api/v1/auth/register | registro por email, retorna user + tokens              |
| POST /api/v1/auth/login    | login por email/password, retorna user + tokens        |
| POST /api/v1/auth/refresh  | renueva access+refresh con refresh token válido       |
| GET /api/v1/auth/me        | retorna el usuario autenticado (requiere Bearer token) |



Ejecución modo desarrollador: `uvicorn main:app --reload --app-dir src`
