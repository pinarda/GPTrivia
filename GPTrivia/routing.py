from django.urls import path
from .consumers import ScoresheetConsumer
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GPTrivia.settings')

websocket_urlpatterns = [
    path('ws/scoresheet/', ScoresheetConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # Handles HTTP requests
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
