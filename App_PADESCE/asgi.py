"""
ASGI config for App_PADESCE project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")

from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

try:
    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter
except ImportError:
    application = django_asgi_app
else:
    application = ProtocolTypeRouter(
        {
            "http": django_asgi_app,
            "websocket": AuthMiddlewareStack(
                __import__("App_PADESCE.routing", fromlist=["websocket_router"]).websocket_router
            ),
        }
    )
