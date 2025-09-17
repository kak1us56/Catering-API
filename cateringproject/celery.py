import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cateringproject.settings")

app = Celery('cateringproject')
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.update(task_serializer="pickle")
app.autodiscover_tasks()