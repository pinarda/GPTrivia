# routing.py in your Django app

from django.urls import path
from .consumers import ScoresheetConsumer
from channels.routing import ProtocolTypeRouter, URLRouter

websocket_urlpatterns = [
    path('ws/scoresheet/', ScoresheetConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'websocket': URLRouter(websocket_urlpatterns),
})
