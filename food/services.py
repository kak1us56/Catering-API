from dataclasses import asdict, dataclass, field
from time import sleep

from celery.schedules import crontab

from cateringproject import celery_app
from food.providers import uklon
from shared.cache import CacheService
from shared.llm import LLMService
from users.models import Role, User

from .enums import OrderStatus
from .mapper import RESTAURANT_EXTERNAL_TO_INTERNAL
from .models import Dish, Order, OrderItem, Restaurant
from .providers import kfc, silpo
from .serializers import DishSerializer, OrderSerializer

# from django.db.models import QuerySet


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
        comments.append(f"Delivery to the {rest_name}")

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


def get_food_recommendations(user_id: int) -> dict:
    cache = CacheService()

    try:
        items = cache.get("recommendations", str(user_id))
        if items and "dishes" in items:
            return {"recommendations": items["dishes"]}
    except TypeError:
        print("There is no data with recommendations in the cache")
        return {"recommendations": []}


@celery_app.task(queue="default")
def generate_recommendations():
    """Generate recommendations for each user in the system and put them to the cache."""

    LIMIT_ORDERS = 5
    RECOMMENDATION_THRESHOLD = 2
    users = User.objects.filter(role=Role.CUSTOMER)
    llm = LLMService()
    cache = CacheService()

    for user in users:
        print(f"✨ Checking orders for {user.email}")
        last_orders = user.orders.filter(status=OrderStatus.DELIVERED).order_by("-id")[:LIMIT_ORDERS]
        if not last_orders.exists():
            print(f"⏩ User {user.email} has no delivered orders. Skipping.")
            continue

        order_serializer = OrderSerializer(last_orders, many=True)

        print("+++++++++++++++++++++++")
        print(order_serializer.data)
        print("+++++++++++++++++++++++")

        prompt = f"""
        Below you can see the list of orders:
        {order_serializer.data}

        Return me up to {RECOMMENDATION_THRESHOLD} top dishes according to this list.
        Return it without any verbosity except of comma separated ids.

        The response will be used in Python to split data by comma and
        convert to the integer all the ids.
        """

        response = llm.ask(prompt)
        print(f"✨ LLM Result: {response}")

        try:
            dishes_ids: list[int] = [int(dish_id) for dish_id in response.split(",")]
        except ValueError as error:
            raise ValueError(f"LLM return invalid IDs for dishes: {response}") from error

        dishes = Dish.objects.filter(id__in=dishes_ids)
        if dishes.count() != len(dishes_ids):
            raise ValueError("Some of returned dishes are not in the database")

        serializer = DishSerializer(dishes, many=True)
        value = {"dishes": serializer.data}
        cache.set(namespace="recommendations", key=str(user.pk), value=value)
        print(f"✅ Data saved to the cache: {value}")


celery_app.conf.beat_schedule = {
    "execute-generating-recommendations-every-24h": {
        "task": "food.services.generate_recommendations",
        "schedule": crontab(hour=0),
    },
}
celery_app.conf.timezone = "UTC"
