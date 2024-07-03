from django.urls import path
from .consumers import ScoresheetConsumer

websocket_urlpatterns = [
    path('ws/scoresheet/', ScoresheetConsumer.as_asgi()),
]
