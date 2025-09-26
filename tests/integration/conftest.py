import pytest

from users.models import User


@pytest.fixture
def john(django_user_model) -> User:
    user = django_user_model.objects.create_user(
        email="john@email.com",
        password="password",
        phone_number="+3809611",
        first_name="John",
        last_name="Doe",
        is_active=True,
    )

    return user
