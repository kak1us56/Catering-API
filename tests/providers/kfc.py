import random
import time
import uuid
from typing import Literal

import httpx
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

OrderStatus = Literal["not started", "cooking", "cooked", "finished"]
STORAGE: dict[str, OrderStatus] = {}
CATERING_API_WEBHOOK_URL = "http://api:8000/webhooks/kfc/5834eb6c-63b9-4018-b6d3-04e170278ec2/"


app = FastAPI(title="KFC API")


class OrderItem(BaseModel):
    dish: str
    quantity: int


class OrderRequestBody(BaseModel):
    order: list[OrderItem]

async def update_order_status(order_id: str):
    ORDER_STATUSES: tuple[OrderStatus, ...] = ("cooking", "cooked", "finished")
    async with httpx.AsyncClient() as client:
        for status in ORDER_STATUSES:
            time.sleep(random.randint(4, 6))
            STORAGE[order_id] = status
            print(f"KFC: [{order_id}] --> {status}")

            try:
                await client.post(
                    CATERING_API_WEBHOOK_URL,
                    json={"id": order_id, "status": status},
                    timeout=5.0,
                )
                print(f"Webhook sent for {order_id} with status={status}")
            except Exception as e:
                print(f"Failed to send webhook for {order_id}: {e}")

@app.post("/api/orders")
async def make_order(body: OrderRequestBody, background_tasks: BackgroundTasks):
    order_id = str(uuid.uuid4())
    STORAGE[order_id] = "not started"
    background_tasks.add_task(update_order_status, order_id)

    return {"id": order_id, "status": "not started"}


@app.get("/api/orders/{order_id}")
async def get_order(order_id: str):
    return STORAGE.get(order_id, {"error": "Nu such order"})