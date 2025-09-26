import importlib

from django.test import TestCase, override_settings
from django.urls import clear_url_caches
from rest_framework import status
from rest_framework.test import APIClient


class OpenAPITestCase(TestCase):
    @override_settings(DEBUG=True)
    def test_schema_api_debug(self):
        self.client = APIClient()
        clear_url_caches()
        importlib.reload(importlib.import_module("cateringproject.urls"))
        response = self.client.get(path="/api/schema/")
        assert response.status_code == status.HTTP_200_OK

    @override_settings(DEBUG=False)
    def test_schema_api_prod(self):
        clear_url_caches()
        importlib.reload(importlib.import_module("cateringproject.urls"))
        response = self.client.get(path="/api/schema/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @override_settings(DEBUG=True)
    def test_swagger_api_debug(self):
        clear_url_caches()
        importlib.reload(importlib.import_module("cateringproject.urls"))
        response = self.client.get(path="/api/schema/docs/")
        assert response.status_code == status.HTTP_200_OK

    @override_settings(DEBUG=False)
    def test_swagger_api_prod(self):
        clear_url_caches()
        importlib.reload(importlib.import_module("cateringproject.urls"))
        response = self.client.get(path="/api/schema/docs/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @override_settings(DEBUG=True)
    def test_redoc_api_debug(self):
        clear_url_caches()
        importlib.reload(importlib.import_module("cateringproject.urls"))
        response = self.client.get(path="/api/schema/redoc/")
        assert response.status_code == status.HTTP_200_OK

    @override_settings(DEBUG=False)
    def test_redoc_api_prod(self):
        clear_url_caches()
        importlib.reload(importlib.import_module("cateringproject.urls"))
        response = self.client.get(path="/api/schema/redoc/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
