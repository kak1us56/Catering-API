import uuid
from shared.cache import CacheService
from django.conf import settings
from rest_framework.exceptions import ValidationError

from django.core.mail import send_mail
from .models import User
from .tasks import send_user_activation_email_task

class ActivationService:
    UUID_NAMESPACE = uuid.uuid4()

    def __init__(self, email: str | None = None):
        self.email: str | None = email
        self.cache: CacheService = CacheService()

    @staticmethod
    def create_activation_key():
        return uuid.uuid4()

    def save_activation_information(self, activation_key: str, user_id: int):
        self.cache.set(
            namespace="activation",
            key=activation_key,
            value={"user_id": user_id},
            ttl=settings.CACHES["default"].get("TIMEOUT"),
        )
        return None

    def send_user_activation_email(self, activation_key: str):
        if self.email is None:
            raise ValueError("Email cannot be None")

        send_user_activation_email_task.delay(self.email, activation_key)

    def activate_user(self, activation_key: str) -> None:
        user_cache_payload: dict | None = self.cache.get(
            namespace="activation",
            key=activation_key,
        )

        if user_cache_payload is None:
            raise ValueError("No payload in cache")

        user = User.objects.get(id=user_cache_payload["user_id"])
        user.is_active = True
        user.save()

        self.cache.delete(namespace="activation", key=activation_key)

    def resend_user_activation_link(self, user_id: int):
        user = User.objects.get(id=user_id)

        if user.is_active:
            raise ValidationError("User is already active")

        repeated_activation_key: str = self.create_activation_key()

        activation_link: str = f"https://frontend.catering.com/activation/{repeated_activation_key}"
        self.save_activation_information(activation_key=repeated_activation_key, user_id=user.id)
        send_mail(
            subject="User Activation",
            message=f"Please, activate your account: {activation_link}",
            from_email="admin@catering.com",
            recipient_list=[user.email],
            )