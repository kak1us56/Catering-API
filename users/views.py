from django.shortcuts import render
from .models import User
from typing import Any

from django.contrib.auth.hashers import make_password
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework import routers, serializers, viewsets, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import action

from .services import ActivationService


# Create your views here.
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone_number",
            "first_name",
            "last_name",
            "password",
            "role",
        ]
    
    def validate(self, attrs: dict[str, Any]):
        """Change the password for its hash to make Token-based authentication available."""

        attrs["password"] = make_password(attrs["password"])
        attrs["is_active"] = False

        return super().validate(attrs=attrs)

class UserActivationSerializer(serializers.Serializer):
    key = serializers.UUIDField()

class ResendActivationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class UsersAPIViewSet(viewsets.GenericViewSet):
    authentication_classes = [JWTAuthentication]

    def get_permissions(self):
        if self.action == "create" or self.action == "activate" or self.action == "resend":
            return [permissions.AllowAny()]
        else:
            return [permissions.IsAuthenticated()]

    def list(self, request: Request):
        return Response(UserSerializer(request.user).data, status=200)

    def create(self, request: Request):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        activation_service = ActivationService(
            email = getattr(serializer.instance, "email"),
        )

        activation_key = activation_service.create_activation_key()
        activation_service.save_activation_information(activation_key=activation_key, user_id=getattr(serializer.instance, "id"))
        # activation_service.send_user_activation_email(activation_key=activation_key)
        activation_service.send_user_activation_email(activation_key=activation_key)
        return Response(UserSerializer(serializer.instance).data, status=201)

    @action(methods=["post"], detail=False)
    def activate(self, request: Request):
        serializer = UserActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        activation_service = ActivationService()
        try:
            activation_service.activate_user(activation_key=serializer.validated_data["key"])
        except ValueError as e:
            raise ValidationError("Activation link is expired") from e
        except TypeError as e:
            raise ValidationError("User is already activated") from e

        return Response(data=None, status=204)

    @action(methods=["post"], detail=False)
    def resend(self, request: Request):
        serializer = ResendActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        activation_service = ActivationService()
        activation_service.resend_user_activation_link(user_id=serializer.validated_data["user_id"])

        return Response(data=None, status=200)



router = routers.DefaultRouter()
router.register(r"", UsersAPIViewSet, basename="user")