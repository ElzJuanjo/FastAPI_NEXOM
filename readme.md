# NexOS - Automatización de e-commerce

Ejecución modo desarrollador: `uvicorn main:app --reload --app-dir src`

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

### Sprint 3 - Organizaciones

| Archivo                                            | Propósito                                                         |
| -------------------------------------------------- | ------------------------------------------------------------------ |
| `domain/entities/plan.py`                        | Definición de planes de suscripción.                             |
| `domain/entities/organization.py`                | Entidades Organization, Subscription y OrganizationMember.         |
| `domain/repositories/plan_repository.py`         | Contrato de acceso a datos para Plan.                              |
| `domain/repositories/organization_repository.py` | Contrato de acceso a datos para Organization y OrganizationMember. |
| `infra/adapters/plan_sqlalchemy.py`              | Implementación SQLAlchemy async del PlanRepository.               |
| `infra/adapters/organization_sqlalchemy.py`      | Implementación SQLAlchemy async del OrganizationRepository.       |
| `app/dto/organization_dto.py`                    | DTOs para Organizations, Plans y Members.                          |
| `app/use_cases/org_create.py`                    | Crear organización.                                               |
| `app/use_cases/org_list.py`                      | Listar organizaciones a las que pertenece un usuario.              |
| `app/use_cases/plan_seed.py`                     | Seed de planes iniciales.                                          |
| `interfaces/dependencies/org_dependencies.py`    | Dependencias de inyección para Organizations y Plans.             |
| `interfaces/api/org_router.py`                   | Endpoints de Organizations y Plans.                                |
| `main.py`                                        | (incluir org_router)                                               |
