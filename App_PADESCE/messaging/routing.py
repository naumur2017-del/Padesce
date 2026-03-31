from django.urls import path

from App_PADESCE.messaging.consumers import SupportConsumer


websocket_urlpatterns = [
    path("ws/support/", SupportConsumer.as_asgi(), name="ws_support"),
]
