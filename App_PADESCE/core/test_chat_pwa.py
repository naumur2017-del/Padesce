from __future__ import annotations

import json
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from App_PADESCE.core.chat_views import CHAT_HISTORY_SESSION_KEY


class ChatRemoteApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="chat-user",
            password="test-pass-123",
        )
        self.client.force_login(self.user)

    @patch("App_PADESCE.core.chat_views.requests.post")
    def test_chat_proxy_returns_remote_response_and_persists_history(self, mock_post):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            "reponse": "Réponse distante depuis Hugging Face.",
            "fichier": "/app/exports/rapport.xlsx",
            "download_url": "https://koulou-chatnaumur.hf.space/files/rapport.xlsx",
        }
        mock_post.return_value = mock_response

        message = "Combien de prestataires ?"
        response = self.client.post(
            reverse("chat_query"),
            data=json.dumps({"message": message}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "remote-api")
        self.assertEqual(payload["response"], "Réponse distante depuis Hugging Face.")
        self.assertEqual(payload["filename"], "rapport.xlsx")
        self.assertEqual(
            payload["download_url"],
            "https://koulou-chatnaumur.hf.space/files/rapport.xlsx",
        )

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs["json"], {"prompt": message, "verbose": False})
        self.assertIn("timeout", call_kwargs)

        history = self.client.session[CHAT_HISTORY_SESSION_KEY]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], message)
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["content"], "Réponse distante depuis Hugging Face.")

    @patch("App_PADESCE.core.chat_views.requests.post", side_effect=requests.Timeout)
    def test_chat_remote_timeout_returns_error(self, _mock_post):
        response = self.client.post(
            reverse("chat_query"),
            data=json.dumps({"message": "Bonjour assistant"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 504)
        payload = response.json()
        self.assertEqual(payload["mode"], "remote-api-error")
        self.assertIn("service RAG distant", payload["error"])


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class PublicPwaRoutesTests(TestCase):
    def test_service_worker_is_public(self):
        response = self.client.get("/service-worker.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response["Content-Type"])
        self.assertIn("unregister()", response.content.decode())

    def test_manifest_is_public(self):
        response = self.client.get("/manifest.webmanifest")

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/manifest+json", response["Content-Type"])
        payload = json.loads(response.content.decode())
        self.assertEqual(payload["name"], "PADESCE")
        self.assertEqual(payload["theme_color"], "#7c3aed")
