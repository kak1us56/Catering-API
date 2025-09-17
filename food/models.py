from django.db import models
from django.conf import settings
from .enums import OrderStatus

# Create your models here.
class Restaurant(models.Model):
    class Meta:
        db_table = "restaurants"

    name = models.CharField(max_length=255, null=False)
    address = models.TextField(null=False)

    def __str__(self) -> str:
        return self.name

class Dish(models.Model):
    class Meta:
        db_table = "dishes"

    name = models.CharField(max_length=255, null=False)
    price = models.PositiveIntegerField(null=False)
    restaurant = models.ForeignKey("Restaurant", on_delete=models.CASCADE, related_name="dishes")

    def __str__(self) -> str:
        return self.name

class Order(models.Model):
    class Meta:
        db_table = "orders"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=25,
        choices=OrderStatus.choices,
        default=OrderStatus.NOT_STARTED,
    )
    delivery_provider = models.CharField(max_length=255, null=True, blank=True)
    eta = models.DateField()
    total = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f"[{self.pk}] {self.status} for {self.user.email}"

    def items_by_restaurant(self) -> dict["Restaurant", models.QuerySet["OrderItem"]]:
        results = {}

        qs = self.items.select_related('dish__restaurant')

        restaurants = {item.dish.restaurant for item in qs}

        for restaurant in restaurants:
            results[restaurant] = qs.filter(dish__restaurant=restaurant)

        return results

    def delivery_meta(self) -> tuple[str, str]:
        return (
            self.items.select_related("dish__restaurant").values_list(
                "dish__restaurant",
                "dish__restaurant__address",
            ).distinct()
        )



class OrderItem(models.Model):
    class Meta:
        db_table = "order_items"

    order = models.ForeignKey(
        "Order",
        on_delete=models.CASCADE,
        related_name="items",
    )
    dish = models.ForeignKey(
        "Dish",
        on_delete=models.CASCADE,
    )
    quantity = models.SmallIntegerField()

    def __str__(self) -> str:
        return f"[{self.order.pk}] {self.dish.name}: {self.quantity}"
