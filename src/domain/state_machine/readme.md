## Patrón maquinas de estado

Se definen los estados, para sacar todas esas condiciones con varios booleanos o ifs aninados.

Ejemplo: payment_machine.py

```
from enum import Enum

class PaymentState(str, Enum):
    IDLE = "IDLE"
    LOADING = "LOADING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"

class PaymentEvent(str, Enum):
    PAY = "PAY"
    RESOLVE = "RESOLVE"
    REJECT = "REJECT"

machine: dict[PaymentState, dict[PaymentEvent, PaymentState]] = {
    PaymentState.IDLE: {
        PaymentEvent.PAY: PaymentState.LOADING
    },
    PaymentState.LOADING: {
        PaymentEvent.RESOLVE: PaymentState.SUCCESS,
        PaymentEvent.REJECT: PaymentState.ERROR
    }
}

def transition(current_state: PaymentState, event: PaymentEvent) -> PaymentState:

    if current_state not in machine:
        return current_state

    next_state = machine[current_state].get(event)

    if next_state:
        return next_state

    return current_state
```

Uso:

```
state = PaymentState.IDLE

state = transition(state, PaymentEvent.PAY)
print(state) #PaymentState.LOADING

state = transition(state, PaymentEvent.RESOLVE)
print(state) #PaymentState.SUCCESS
```
