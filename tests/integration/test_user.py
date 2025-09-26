import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class UserTestCase(TestCase):
    @pytest.mark.django_db
    def test_john_creation(self) -> None:
        self.client = APIClient()
        request_body = {
            "email": "john@email.com",
            "password": "@Dm1n#LKJ",
            "phone_number": "...",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = self.client.post(path="/users/", data=request_body)
        resp = response.json()

        total_users = User.objects.count()
        john = User.objects.get(id=resp["id"])

        assert response.status_code == status.HTTP_201_CREATED
        assert total_users == 1
        assert john.pk == resp["id"]
        assert john.first_name == resp["first_name"]
        assert john.last_name == resp["last_name"]
        assert john.role == resp["role"]
        assert not john.is_active

    @pytest.mark.django_db
    def test_sign_in(self) -> None:
        self.john = User.objects.create_user(email="john@email.com", password="@Dm1n#LKJ")
        self.john.is_active = True
        self.john.save()

        request_body = {"email": "john@email.com", "password": "@Dm1n#LKJ"}

        response = self.client.post(path="/auth/token/", data=request_body)
        resp = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert "access" and "refresh" in resp

    def test_get_user_authorized(self) -> None:
        self.client = APIClient()

        self.john = User.objects.create_user(email="john@email.com", password="@Dm1n#LKJ")
        self.john.is_active = True
        self.john.save()

        # JWT Token claim
        response = self.client.post(
            reverse("obtain_token"),
            {
                "email": "john@email.com",
                "password": "@Dm1n#LKJ",
            },
        )

        assert response.status_code == status.HTTP_200_OK, response.json()
        token = response.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get(path="/users/")
        resp = response.json()

        total_users = User.objects.count()
        user = User.objects.get(id=resp["id"])

        assert response.status_code == status.HTTP_200_OK, response.json()
        assert total_users == 1
        assert user.email == resp["email"]
        assert user.phone_number == resp["phone_number"]
        assert user.pk == resp["id"]
        assert user.first_name == resp["first_name"]
        assert user.last_name == resp["last_name"]
        assert user.role == resp["role"]

    def test_get_user_unauthorized(self) -> None:
        self.anonymous = APIClient()
        response = self.client.get(path="/users/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
