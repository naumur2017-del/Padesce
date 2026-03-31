from channels.routing import URLRouter

from App_PADESCE.messaging.routing import websocket_urlpatterns


websocket_router = URLRouter(websocket_urlpatterns)
