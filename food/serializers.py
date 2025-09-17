from datetime import date

from .models import Dish, Order, OrderItem, OrderStatus, Restaurant
from .enums import DeliveryProvider
from rest_framework.pagination import LimitOffsetPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

class DishSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dish
        fields = "__all__"

class RestaurantSerializer(serializers.ModelSerializer):
    dishes = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = '__all__'

    def get_dishes(self, obj):
        request = self.context.get('request')

        dishes = obj.dishes.all()

        search_query = request.query_params.get('search')
        if search_query:
            dishes = dishes.filter(name__icontains=search_query)

        paginator = LimitOffsetPagination()
        paginator.limit_param = 2

        page = paginator.paginate_queryset(dishes, request, view=self)

        return DishSerializer(page, many=True).data

class OrderItemSerializer(serializers.ModelSerializer):
    dish = serializers.PrimaryKeyRelatedField(queryset=Dish.objects.all())
    quantity = serializers.IntegerField(min_value=1, max_value=20)

    class Meta:
        model = OrderItem
        fields = ['dish', 'quantity']

class OrderSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(read_only=True)
    items = OrderItemSerializer(many=True)
    eta = serializers.DateField()
    total = serializers.IntegerField(min_value=1, read_only=True)
    status = serializers.ChoiceField(OrderStatus.choices(), read_only=True)
    delivery_provider = serializers.CharField()

    class Meta:
        model = Order
        fields = "__all__"

    @property
    def calculated_total(self) -> int:
        total = 0

        for item in self.validated_data["items"]:
            dish: Dish = item["dish"]
            quantity: int = item["quantity"]
            total += dish.price * quantity

        return total

    def validate_eta(self, value: date):
        if (value - date.today()).days < 1:
            raise ValidationError("ETA must be min 1 day after today.")
        else:
            return value

class KFCOrderSerializer(serializers.Serializer):
    pass