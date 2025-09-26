from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from food.models import Dish, Order, OrderItem, Restaurant

User = get_user_model()


#  Calculate day for an order
def order_day_calculate():
    today = datetime.today().date()
    order_day = today + timedelta(days=2)
    order_day_str = order_day.strftime("%Y-%m-%d")

    return order_day_str


class OrderTestCase(TestCase):
    def setUp(self) -> None:
        self.anonymous = APIClient()
        self.client = APIClient()
        self.admin = APIClient()

        self.admin_client = User.objects.create_superuser(email="admin@admin.com", password="admin")
        self.admin_client.save()

        self.john = User.objects.create_user(email="john@email.com", password="@Dm1n#LKJ", phone_number="1111111111")
        self.john.is_active = True
        self.john.save()

        # JWT Token claim
        response_admin = self.admin.post(
            reverse("obtain_token"),
            {
                "email": "admin@admin.com",
                "password": "admin",
            },
        )

        assert response_admin.status_code == status.HTTP_200_OK, response_admin.json()
        token_admin = response_admin.data["access"]

        self.admin.credentials(HTTP_AUTHORIZATION=f"Bearer {token_admin}")

        response_client = self.client.post(
            reverse("obtain_token"),
            {
                "email": "john@email.com",
                "password": "@Dm1n#LKJ",
            },
        )

        assert response_client.status_code == status.HTTP_200_OK, response_client.json()
        token_client = response_client.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_client}")

        # Populate Data
        self.rest1 = Restaurant.objects.create(name="Silpo", address="123 Main St")
        self.rest2 = Restaurant.objects.create(name="KFC", address="456 Elm St")

        self.dish1 = Dish.objects.create(restaurant=self.rest1, name="Dish 1", price=100)
        self.dish2 = Dish.objects.create(restaurant=self.rest1, name="Dish 2", price=150)

        self.dish3 = Dish.objects.create(restaurant=self.rest2, name="Dish 3", price=200)
        self.dish4 = Dish.objects.create(restaurant=self.rest2, name="Dish 4", price=250)

    @pytest.mark.django_db
    def test_create_order_authorized(self):
        request_body = {
            "eta": order_day_calculate(),
            "delivery_provider": "uklon",
            "user": self.john.id,
            "items": [{"dish": self.dish1.id, "quantity": 2}, {"dish": self.dish2.id, "quantity": 1}],
        }
        print(order_day_calculate)
        response = self.client.post(reverse("food-orders"), data=request_body, format="json")
        resp = response.json()

        order = Order.objects.get(id=resp["id"])
        order_items = OrderItem.objects.filter(order_id=resp["id"])
        total_orders = Order.objects.count()

        assert response.status_code == status.HTTP_201_CREATED, response.json()
        assert total_orders == 1
        assert order.total == resp["total"]
        assert order.eta.strftime("%Y-%m-%d") == resp["eta"]
        assert order.status == resp["status"]
        assert order.delivery_provider == resp["delivery_provider"]
        assert order.user.id == resp["user"]

        assert len(order_items) == 2

    def test_create_order_not_authorized(self):
        request_body = {
            "eta": order_day_calculate(),
            "delivery_provider": "uklon",
            "items": [{"dish": self.dish1.id, "quantity": 2}, {"dish": self.dish2.id, "quantity": 1}],
        }

        response = self.anonymous.post(reverse("food-orders"), data=request_body, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.json()
