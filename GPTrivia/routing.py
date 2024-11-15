from django.urls import path
from .consumers import ScoresheetConsumer, ButtonPressConsumer

websocket_urlpatterns = [
    path('ws/scoresheet/', ScoresheetConsumer.as_asgi()),
    path('ws/button/', ButtonPressConsumer.as_asgi()),  # New WebSocket route
]
