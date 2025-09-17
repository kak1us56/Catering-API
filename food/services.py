from time import sleep
from dataclasses import dataclass, asdict, field

from django.db.models import QuerySet

from .mapper import RESTAURANT_EXTERNAL_TO_INTERNAL
from shared.cache import CacheService
from cateringproject.celery import app as celery_app
from food.providers import uklon

from .providers import kfc, silpo
from .models import Order, OrderItem, Restaurant
from .enums import OrderStatus

@dataclass
class TrackingOrder:
    restaurants: dict = field(default_factory=dict)
    delivery: dict = field(default_factory=dict)

def all_orders_cooked(order_id: int):
    cache = CacheService()
    tracking_order = TrackingOrder(**cache.get(namespace="orders", key=str(order_id)))
    print(f"Checking if all orders are cooked: {tracking_order.restaurants}")

    if all((payload["status"] == OrderStatus.COOKED for _, payload in tracking_order.restaurants.items())):
        Order.objects.filter(id=order_id).update(status=OrderStatus.COOKED)
        print(f"Order {order_id} has been cooked.")

        order_delivery.delay(order_id)

        return True
    else:
        print(f"Not all orders are cooked: {tracking_order=}")

        return False

@celery_app.task(queue="default")
def order_delivery(order_id: int):
    print("DELIVERY PROCESSING")

    provider = uklon.Client()
    cache = CacheService()
    order = Order.objects.get(id=order_id)

    order.status = OrderStatus.DELIVERY_LOOKUP
    order.save()

    addresses: list[str] = []
    comments: list[str] = []

    for rest_name, address in order.delivery_meta():
        addresses.append(address)
        comments.append(f'Delivery to the {rest_name}')

    order.status = OrderStatus.DELIVERED
    order.save()

    _response: uklon.OrderResponse = provider.create_order(
        uklon.OrderRequestBody(addresses=addresses, comments=comments),
    )

    tracking_order = TrackingOrder(**cache.get("orders", str(order.pk)))
    tracking_order.delivery["status"] = OrderStatus.DELIVERY
    tracking_order.delivery["location"] = _response.location

    current_status: uklon.OrderStatus = _response.status

    while current_status != OrderStatus.DELIVERED:
        response = provider.get_order(_response.id)

        print(f"🚙 Uklon [{response.status}]: 📍 {response.location}")

        if current_status == response.status:
            sleep(1)
            continue

        current_status = response.status

        tracking_order.delivery["location"] = response.location

        cache.set("orders", str(order_id), asdict(tracking_order))

    print(f"🏁 UKLON [{response.status}]: 📍 {response.location}")

    Order.objects.filter(id=order_id).update(status=OrderStatus.DELIVERED)

    tracking_order.delivery["status"] = OrderStatus.DELIVERED
    # cache.delete("orders", str(order_id))

    print("✅ DONE with Delivery")

@celery_app.task(queue="high_priority")
def order_in_silpo(order_id: int, items: list[dict]):
    items = [OrderItem.objects.get(id=item["id"]) for item in items]

    client = silpo.Client()
    cache = CacheService()
    restaurant = Restaurant.objects.get(name="Silpo")

    def get_internal_status(status: silpo.OrderStatus) -> OrderStatus:
        return RESTAURANT_EXTERNAL_TO_INTERNAL["silpo"][status]

    cooked = False
    while not cooked:
        sleep(1)

        tracking_order = TrackingOrder(**cache.get("orders", str(order_id)))
        silpo_order = tracking_order.restaurants.get(str(restaurant.pk))
        if not silpo_order:
            raise ValueError("No Silpo in orders processing")

        print(f"CURRENT SILPO ORDER STATUS: {silpo_order['status']}")

        if not silpo_order["external_id"]:
            response: silpo.OrderResponse = client.create_order(
                silpo.OrderRequestBody(
                    order=[silpo.OrderItem(dish=item.dish.name, quantity=item.quantity) for item in items]
                )
            )
            internal_status: OrderStatus = get_internal_status(response.status)

            tracking_order.restaurants[str(restaurant.pk)] |= {
                "external_id": response.id,
                "status": internal_status,
            }

            cache.set("orders", str(order_id), asdict(tracking_order), ttl=3600)
        else:
            response = client.get_order(silpo_order["external_id"])
            internal_status: OrderStatus = get_internal_status(response.status)

            print(f"Tracking for Silpo Order with HTTP GET /api/order. Status: {internal_status}")

            if silpo_order["status"] != internal_status:
                tracking_order.restaurants[str(restaurant.pk)]["status"] = internal_status
                print(f"Silpo order status changed to {internal_status}")
                cache.set("orders", str(order_id), asdict(tracking_order), ttl=3600)

                if internal_status == OrderStatus.COOKING:
                    Order.objects.filter(id=order_id).update(status=OrderStatus.COOKING)

                if internal_status == OrderStatus.COOKED:
                    cooked = True
                    all_orders_cooked(order_id)

@celery_app.task(queue="high_priority")
def order_in_kfc(order_id: int, items: list[dict]):
    client = kfc.Client()
    cache = CacheService()
    restaurant = Restaurant.objects.get(name="KFC")

    def get_internal_status(status: silpo.OrderStatus) -> OrderStatus:
        return RESTAURANT_EXTERNAL_TO_INTERNAL["kfc"][status]

    tracking_order = TrackingOrder(**cache.get(namespace="orders", key=str(order_id)))

    response: kfc.OrderResponse = client.create_order(
        kfc.OrderRequestBody(
            order=[kfc.OrderItem(dish=item["dish__name"], quantity=item["quantity"]) for item in items]
        )
    )
    internal_status = get_internal_status(response.status)

    tracking_order.restaurants[str(restaurant.pk)] |= {
        "external_id": response.id,
        "status": internal_status,
    }

    print(f"Created KFC Order. External ID: {response.id} Status: {internal_status}")
    cache.set("orders", str(order_id), asdict(tracking_order), ttl=3600)

    cache.set(
        namespace="kfc_orders",
        key=response.id,
        value={
            "internal_order_id": order_id,
        },
        ttl=3600,
    )

    if all_orders_cooked(order_id):
        cache.set(namespace="orders", key=str(order_id), value=asdict(tracking_order), ttl=3600)
        Order.objects.filter(id=order_id).update(status=OrderStatus.COOKED)

def schedule_order(order: Order):
    cache = CacheService()
    tracking_order = TrackingOrder()

    items_by_restaurants = order.items_by_restaurant()
    for restaurant, items in items_by_restaurants.items():
        tracking_order.restaurants[str(restaurant.pk)] = {
            "external_id": None,
            "status": OrderStatus.NOT_STARTED,
        }

    cache.set("orders", str(order.pk), asdict(tracking_order), ttl=3600)

    for restaurant, items in items_by_restaurants.items():
        match restaurant.name.lower():
            case "kfc":
                # order_in_kfc.delay(order.pk, list(items.values("id", "dish__name", "quantity")))
                order_in_kfc(order.pk, list(items.values("id", "dish__name", "quantity")))
            case "silpo":
                order_in_silpo.delay(order.pk, list(items.values("id", "dish__name", "quantity")))
            case _:
                raise ValueError(f"Restaurant {restaurant.name} is not supported")