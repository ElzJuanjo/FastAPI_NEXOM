## Patrón Observer

Los eventos permiten notificar que algo importante ha ocurrido en el sistema sin acoplar directamente los componentes que reaccionan a ese evento.

En lugar de que una parte del sistema llame directamente a otra, se publica un evento y cualquier observador interesado puede reaccionar a él.

Esto permite construir sistemas más desacoplados y extensibles.

Ejemplo conceptual:

Cuando se crea una orden, el sistema puede publicar un evento "order_created". Distintos componentes podrían reaccionar a este evento:

* enviar un email
* registrar un log
* iniciar un proceso de pago
* actualizar estadísticas

El componente que crea la orden no necesita saber quién escuchará el evento. Solo lo publica.

Este patrón ayuda a evitar dependencias directas entre componentes del dominio o de la aplicación.

El objetivo es proporcionar un mecanismo simple para la comunicación desacoplada entre distintas partes del sistema.

NOTAS:

Esto usa Singleton (Unica instancia en todo el programa), por lo que siempre debe llamarse "broker = EventBroker().get_instance()
Recordar usar el unsubscribe, y mantener solo los necesarios.
