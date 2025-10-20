from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from food.models import Dish, Order, OrderItem, OrderStatus, Restaurant

User = get_user_model()


def order_day_calculate():
    today = datetime.today().date()
    order_day = today + timedelta(days=2)
    order_day_str = order_day.strftime("%Y-%m-%d")

    return order_day_str


class OpenaiTestCase(TransactionTestCase):
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

        # Populate data
        self.rest1 = Restaurant.objects.create(name="Silpo", address="123 Main St")

        self.dish1 = Dish.objects.create(restaurant=self.rest1, name="Dish 1", price=100)
        self.dish2 = Dish.objects.create(restaurant=self.rest1, name="Dish 2", price=150)

        self.order1 = Order.objects.create(
            eta=order_day_calculate(),
            delivery_provider="uklon",
            user=self.john,
            status=OrderStatus.DELIVERED,
        )

        OrderItem.objects.create(order=self.order1, dish=self.dish1, quantity=2)
        OrderItem.objects.create(order=self.order1, dish=self.dish2, quantity=1)

    @patch("food.services.LLMService")
    def test_generate_recommendations_admin(self, MockLLMService):
        mock_llm_instance = MockLLMService.return_value
        mock_llm_instance.ask.return_value = f"{self.dish1.id},{self.dish2.id}"

        response = self.admin.post(path="/food/recommendations/generate/")
        assert response.status_code == status.HTTP_200_OK

        mock_llm_instance.ask.assert_called_once()

    def test_generate_recommendations_authorized(self):
        response = self.client.post(path="/food/recommendations/generate/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_generate_recommendations_not_authorized(self):
        response = self.anonymous.post(path="/food/recommendations/generate/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("food.services.LLMService")
    def test_recommendations_authorized(self, MockLLMService):
        mock_llm_instance = MockLLMService.return_value
        mock_llm_instance.ask.return_value = f"{self.dish1.id},{self.dish2.id}"

        admin_response = self.admin.post(path="/food/recommendations/generate/")
        assert admin_response.status_code == status.HTTP_200_OK

        client_response = self.client.get(path="/food/recommendations/")
        resp = client_response.json()

        assert client_response.status_code == status.HTTP_200_OK
        assert "recommendations" in resp
        assert len(resp["recommendations"]) == 2

        recommended_names = {dish["name"] for dish in resp["recommendations"]}
        assert self.dish1.name in recommended_names
        assert self.dish2.name in recommended_names

    def test_recommendations_not_authorized(self):
        response = self.anonymous.get(path="/food/recommendations/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
