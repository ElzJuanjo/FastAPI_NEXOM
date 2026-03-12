## Clean Architecture

Ejemplo de uso conceptual:

Un endpoint necesita ejecutar un caso de uso. En lugar de crear manualmente el repositorio, el broker de eventos y el use case dentro del endpoint, solicita una dependencia que se encarga de construirlos.

Esto centraliza la creación de objetos y evita repetir lógica de inicialización en múltiples rutas.

Qué va aquí:

* funciones que construyen repositorios
* funciones que construyen use cases
* dependencias de autenticación
* dependencias de base de datos
* dependencias compartidas entre endpoints

Qué NO va aquí:

* lógica de negocio
* SQL
* reglas del dominio
* implementación de repositorios
* definición de entidades

Esta carpeta pertenece a la capa de interfaces porque su propósito es ayudar a preparar el entorno necesario para atender una solicitud externa.
