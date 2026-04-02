from __future__ import annotations

import json
from unittest.mock import patch

import pandas as pd
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from App_PADESCE.core.chat_views import CHAT_HISTORY_SESSION_KEY


class ChatFallbackTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="chat-user",
            password="test-pass-123",
        )
        self.client.force_login(self.user)

    @patch("App_PADESCE.core.chat_views._load_chat_workbook_frames")
    def test_chat_fallback_returns_status_distribution_and_persists_history(self, mock_frames):
        mock_frames.return_value = {
            "consolide": pd.DataFrame(
                {
                    "Statut de la prestation": ["TERMINÉ", "EN COURS", "TERMINÉ"],
                    "Prestataire": ["Alpha", "Beta", "Alpha"],
                    "Bénéficiaires": ["Ben A", "Ben B", "Ben A"],
                    "Région": ["Nord", "Sud", "Nord"],
                    "cohorte": ["C1", "C2", "C1"],
                    "Classe": ["CLA1", "CLA2", "CLA1"],
                    "Ville de la formation": ["Garoua", "Maroua", "Garoua"],
                }
            ),
            "classes": pd.DataFrame(),
            "apprenants": pd.DataFrame(),
        }

        response = self.client.post(
            reverse("chat_query"),
            data=json.dumps({"message": "Quelle est la répartition par statut dans le décompte ?"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "fallback")
        self.assertIn("Répartition par statut de la prestation", payload["response"])
        self.assertIn("TERMINÉ", payload["response"])

        history = self.client.session[CHAT_HISTORY_SESSION_KEY]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")


class PublicPwaRoutesTests(TestCase):
    def test_service_worker_is_public(self):
        response = self.client.get("/service-worker.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response["Content-Type"])
        self.assertIn("CACHE_VERSION", response.content.decode())

    def test_manifest_is_public(self):
        response = self.client.get("/manifest.webmanifest")

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/manifest+json", response["Content-Type"])
        payload = json.loads(response.content.decode())
        self.assertEqual(payload["name"], "PADESCE")
        self.assertEqual(payload["theme_color"], "#7c3aed")
