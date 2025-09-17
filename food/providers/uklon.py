import enum
import os
from dataclasses import asdict, dataclass

import httpx

class OrderStatus(enum.StrEnum):
    NOT_STARTED = "not started"
    DELIVERY = "delivery"
    DELIVERED = "delivered"

@dataclass
class OrderRequestBody:
    addresses: list[str]
    comments: list[str]

@dataclass
class OrderResponse:
    order_id: str
    status: OrderStatus
    location: tuple[float, float]
    addresses: list[str]
    comments: list[str]

    @property
    def id(self):
        return self.order_id

class Client:
    BASE_URL = os.getenv("UKLON_BASE_URL", "http://uklon-mock:8003/drivers/orders")

    @classmethod
    def create_order(cls, order: OrderRequestBody):
        response: httpx.Response = httpx.post(cls.BASE_URL, json=asdict(order))
        response.raise_for_status()
        return OrderResponse(**response.json())

    @classmethod
    def get_order(cls, order_id: str):
        response: httpx.Response = httpx.get(f"{cls.BASE_URL}/{order_id}")
        response.raise_for_status()
        return OrderResponse(**response.json())