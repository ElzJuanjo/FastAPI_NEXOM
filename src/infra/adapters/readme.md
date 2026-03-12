## Arquitectura hexagonal

Los **adapters** implementan los contratos definidos en `domain/repositories`.

Aquí van:

* SQL
* ORM
* llamadas a APIs externas
* acceso a filesystem

Esta capa depende del dominio,  **no al revés** .
