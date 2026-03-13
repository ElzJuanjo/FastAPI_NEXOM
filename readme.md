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

### Sprint 4 - Marcas y productos

| Archivo                                             | Propósito                                                  |
| --------------------------------------------------- | ----------------------------------------------------------- |
| `domain/entities/brand.py`                        | Entidad Brand — identidad de marca.                        |
| `domain/entities/product.py`                      | Entidad Product — productos gestionados por la plataforma. |
| `domain/repositories/brand_repository.py`         | Contrato de acceso a datos para Brand.                      |
| `domain/repositories/product_repository.py`       | Contrato de acceso a datos para Product.                    |
| `infra/adapters/brand_sqlalchemy.py`              | Implementación SQLAlchemy async del BrandRepository.       |
| `infra/adapters/product_sqlalchemy.py`            | Implementación SQLAlchemy async del ProductRepository.     |
| `app/dto/brand_dto.py`                            | DTOs para Brand.                                            |
| `app/dto/product_dto.py`                          | DTOs para Product.                                          |
| `app/use_cases/brand_crud.py`                     | Casos de uso CRUD para Brand.                               |
| `app/use_cases/product_crud.py`                   | Casos de uso CRUD para Product.                             |
| `interfaces/dependencies/brand_dependencies.py`   | Dependencias de inyección para Brand.                      |
| `interfaces/dependencies/product_dependencies.py` | Dependencias de inyección para Product.                    |
| `interfaces/api/brand_router.py`                  | Endpoints CRUD de Brand, scoped por organización.          |
| `interfaces/api/product_router.py`                | Endpoints CRUD de Product, scoped por organización.        |

### Sprint 5 - Configuración de agentes y tareas

| Archivo                                            | Propósito                                                  |
| -------------------------------------------------- | ----------------------------------------------------------- |
| `domain/entities/agent.py`                       | Entidades AgentConfig y AgentTask.                          |
| `domain/repositories/agent_config_repository.py` | Contrato de acceso a datos para AgentConfig.                |
| `domain/repositories/agent_task_repository.py`   | Contrato de acceso a datos para AgentTask.                  |
| `infra/adapters/agent_config_sqlalchemy.py`      | Implementación SQLAlchemy async del AgentConfigRepository. |
| `infra/adapters/agent_task_sqlalchemy.py`        | Implementación SQLAlchemy async del AgentTaskRepository.   |
| `app/dto/agent_dto.py`                           | DTOs para AgentConfig y AgentTask.                          |
| `app/use_cases/agent_config_crud.py`             | Casos de uso para AgentConfig.                              |
| `app/use_cases/agent_task_crud.py`               | Casos de uso para AgentTask.                                |
| `interfaces/dependencies/agent_dependencies.py`  | Dependencias de inyección para AgentConfig y AgentTask.    |
| `interfaces/api/agent_router.py`                 | Endpoints de AgentConfig y AgentTask.                       |

### Sprint 6 - Flujos y orquestación

| Archivo                                          | Propósito                                               |
| ------------------------------------------------ | -------------------------------------------------------- |
| `domain/entities/flow.py`                      | Entidades Flow y FlowStep — orquestación multi-agente. |
| `domain/repositories/flow_repository.py`       | Contrato de acceso a datos para Flow y FlowStep.         |
| `infra/adapters/flow_sqlalchemy.py`            | Implementación SQLAlchemy async del FlowRepository.     |
| `app/dto/flow_dto.py`                          | DTOs para Flow y FlowStep.                               |
| `app/use_cases/flow_crud.py`                   | Casos de uso para Flow y FlowStep.                       |
| `interfaces/dependencies/flow_dependencies.py` | Dependencias de inyección para Flow.                    |
| `interfaces/api/flow_router.py`                | Endpoints de Flow y FlowStep.                            |
