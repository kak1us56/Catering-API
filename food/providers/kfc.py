import enum
import os
from dataclasses import dataclass, asdict

import httpx

class OrderStatus(enum.StrEnum):
    NOT_STARTED = "not started"
    COOKING = "cooking"
    COOKED = "cooked"
    FINISHED = "finished"

@dataclass
class OrderItem:
    dish: str
    quantity: int

@dataclass
class OrderRequestBody:
    order: list[OrderItem]

@dataclass
class OrderResponse:
    id: str
    status: OrderStatus

class Client:
    BASE_URL = os.getenv("KFC_BASE_URL", "http://kfc-mock:8001/api/orders")

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