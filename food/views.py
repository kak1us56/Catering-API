import csv
import io
import json
from dataclasses import asdict
from datetime import date
from django.shortcuts import render
from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework import permissions, routers, serializers, viewsets, filters
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import action, permission_classes, api_view
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import ValidationError
from django.db import transaction
from rest_framework.pagination import LimitOffsetPagination
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework

from users.models import Role, User
from shared.cache import CacheService
from .mapper import RESTAURANT_EXTERNAL_TO_INTERNAL
from .providers import kfc

from .models import Dish, Order, OrderItem, OrderStatus, Restaurant
from .serializers import OrderSerializer, KFCOrderSerializer, RestaurantSerializer, OrderItemSerializer, DishSerializer
from .enums import DeliveryProvider
from .services import schedule_order, all_orders_cooked, TrackingOrder

class RestaurantFilters(rest_framework.FilterSet):
    class Meta:
        model = Restaurant
        fields = ['name']

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, 'role', None) == Role.ADMIN

class FoodAPIViewSet(viewsets.GenericViewSet):
    queryset = Restaurant.objects.all()
    authentication_classes = [JWTAuthentication]

    def get_permissions(self):
        if self.action == 'create_dish':
            return [IsAdmin()]
        return super().get_permissions()

    @action(methods=["post"], detail=False, url_path=r"orders")
    def create_order(self, request: Request) -> Response:
        serializer = OrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assert type(request.user) is User
        print('create_order')
        with transaction.atomic():
            order = Order.objects.create(
                status=OrderStatus.NOT_STARTED,
                user=request.user,
                delivery_provider="uklon",
                eta=serializer.validated_data["eta"],
                total=serializer.calculated_total,
            )

            items = serializer.validated_data["items"]
            for dish_order in items:
                instance = OrderItem.objects.create(
                    dish=dish_order["dish"],
                    quantity=dish_order["quantity"],
                    order=order,
                )
                print(f"New Dish Order Item is created: {instance.pk}")

        print(f"New Food Order is created: {order.pk}. ETA: {order.eta}")

        schedule_order(order)

        return Response(OrderSerializer(order).data, status=201)

    # @action(methods=["get"], detail=False)
    # def dishes(self, request: Request) -> Response:
    #     restaurants = Restaurant.objects.all()
    #     serializer = RestaurantSerializer(restaurants, many=True)
    #     return Response(data=serializer.data)

    @action(methods=["post", "get"], detail=False, url_path=r"dishes")
    def dishes(self, request: Request) -> Response:
        if request.method == "POST":
            if not IsAdmin().has_permission(request, self):
                return Response({"detail": "You do not have permission to perform this action."}, status=403)

            serializer = DishSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            serializer.save()

            return Response(DishSerializer(serializer.instance).data, status=201)

        if request.method == "GET":
            restaurants = Restaurant.objects.all()

            filtered_queryset = RestaurantFilters(request.GET, queryset=restaurants).qs

            serializer = RestaurantSerializer(filtered_queryset, many=True, context={"request": request})
            return Response(data=serializer.data)

# @api_view(["POST"])
# @permission_classes([IsAdmin])
def import_dishes(request):
    if not IsAdmin().has_permission(request, view=None):
        return Response({"detail": "You do not have permission to perform this action."}, status=403)

    if request.method != "POST":
        raise ValueError("Only POST requests are allowed.")

    csv_file = request.FILES.get("file")
    if csv_file is None:
        raise ValueError("CSV file not found.")

    decoded = csv_file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))
    total = 0

    for row in reader:
        restaurant_name = row["restaurant"]
        try:
            rest = Restaurant.objects.get(name__icontains=restaurant_name.lower())
        except Restaurant.DoesNotExist:
            print("Skipping restaurant " + restaurant_name)
        else:
            print(f"{restaurant_name} not found.")

        Dish.objects.create(name=row["name"], restaurant=rest, price=int(row["price"]))
        total += 1

    print(f"{total} restaurants uploaded to the database.")

    return redirect(request.META.get("HTTP_REFERER", "/"))

@csrf_exempt
def kfc_webhook(request):
    print("KFC Webhook is Handled")

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    print(f"KFC webhook payload: {data}")

    external_id = data.get("id") or data.get("order_id")
    if not external_id:
        return JsonResponse({"error": "Missing external_id"}, status=400)

    cache = CacheService()
    restaurant = Restaurant.objects.get(name="KFC")
    kfc_cache_order = cache.get("kfc_orders", key=external_id)

    if not kfc_cache_order:
        print(f'KFC webhook received for unknown order_id={external_id}')
        return JsonResponse({"error": "Order not found"}, status=404)

    def get_internal_status(status: kfc.OrderStatus) -> OrderStatus:
        return RESTAURANT_EXTERNAL_TO_INTERNAL["kfc"][status]

    order: Order = Order.objects.get(id=kfc_cache_order["internal_order_id"])
    tracking_order = TrackingOrder(**cache.get(namespace="orders", key=str(order.pk)))

    internal_status: OrderStatus = get_internal_status(data["status"])
    print(f"Mapped internal status: {internal_status}")
    tracking_order.restaurants[str(restaurant.pk)] |= {
        "external_id": data["id"],
        "status": internal_status,
    }

    cache.set(namespace="orders", key=str(order.pk), value=asdict(tracking_order), ttl=3600)

    if internal_status == OrderStatus.COOKED:
        all_orders_cooked(order.pk)

    return JsonResponse({"message": "ok"})

router = routers.DefaultRouter()
router.register(prefix="", viewset=FoodAPIViewSet, basename="food")