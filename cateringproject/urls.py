from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
)

from food.views import import_dishes, kfc_webhook
from food.views import router as food_router
from users.views import router as users_router

urlpatterns = [
    path("admin/food/dish/import-dishes/", import_dishes, name="import_dishes"),
    path("admin/", admin.site.urls),
    path("auth/token/", TokenObtainPairView.as_view(), name="obtain_token"),
    path("users/", include(users_router.urls)),
    path("food/", include(food_router.urls)),
    path(
        "webhooks/kfc/5834eb6c-63b9-4018-b6d3-04e170278ec2/",
        kfc_webhook,
    ),
]
