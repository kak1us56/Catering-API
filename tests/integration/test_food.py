from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from food.models import Dish, Restaurant

User = get_user_model()


class FoodTestCase(TestCase):
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

    def test_get_dishes_NOT_authorized(self):
        response = self.anonymous.get(reverse("food-dishes-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert type(response.json()) is not list

    def test_get_dishes_authorized(self):
        response = self.client.get(reverse("food-dishes-list"))
        restaurants = response.json()

        total_restaurants = len(restaurants)
        total_dishes = 0
        for rest in restaurants:
            total_dishes += len(rest["dishes"])

        assert response.status_code == status.HTTP_200_OK, restaurants.json()
        assert total_restaurants == 2
        assert total_dishes == 4

    def test_create_dish_admin(self):
        request_body = {"name": "McTasty", "price": 11, "restaurant": 1}

        response = self.admin.post(reverse("food-dishes-list"), data=request_body)
        resp = response.json()

        dish = Dish.objects.get(id=resp["id"])

        assert response.status_code == status.HTTP_201_CREATED, response.json()
        assert dish.name == request_body["name"]
        assert dish.price == request_body["price"]
        assert dish.restaurant.id == request_body["restaurant"]

    def test_create_dish_not_admin(self):
        request_body = {"name": "McTasty", "price": 11, "restaurant": 1}

        response_client = self.client.post(reverse("food-dishes-list"), data=request_body)
        response_anom = self.anonymous.post(reverse("food-dishes-list"), data=request_body)

        assert response_client.status_code == status.HTTP_403_FORBIDDEN, response_client.json()
        assert response_anom.status_code == status.HTTP_401_UNAUTHORIZED, response_anom.json()
