from .enums import OrderStatus
from .providers import kfc, silpo

RESTAURANT_EXTERNAL_TO_INTERNAL: dict[str, dict[str, OrderStatus]] = {
    "silpo": {
        silpo.OrderStatus.NOT_STARTED: OrderStatus.NOT_STARTED,
        silpo.OrderStatus.COOKING: OrderStatus.COOKING,
        silpo.OrderStatus.COOKED: OrderStatus.COOKED,
        silpo.OrderStatus.FINISHED: OrderStatus.FINISHED,
    },
    "kfc": {
        kfc.OrderStatus.NOT_STARTED: OrderStatus.NOT_STARTED,
        kfc.OrderStatus.COOKING: OrderStatus.COOKING,
        kfc.OrderStatus.COOKED: OrderStatus.COOKED,
    },
}