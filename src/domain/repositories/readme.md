## Arquitectura hexagonal

**Qué va aquí**

* Contratos de acceso a datos.
* Interfaces para repositorios.

**Qué NO va aquí**

* SQL
* ORM
* lógica de negocio

Esto permite que el dominio  **no dependa de la base de datos** .
