from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.contrib.auth import get_user_model
from django.http import Http404, HttpResponse, JsonResponse
from django.test import TestCase, override_settings
from django.urls import path


def ok_view(request):
    return HttpResponse("ok")


def bad_request_view(request):
    raise SuspiciousOperation("bad request test")


def forbidden_view(request):
    raise PermissionDenied("forbidden test")


def not_found_view(request):
    raise Http404("not found test")


def server_error_view(request):
    raise RuntimeError("server error test")


def json_forbidden_view(request):
    return JsonResponse({"error": "keep-json"}, status=403)


urlpatterns = [
    path("ok/", ok_view),
    path("bad-request/", bad_request_view),
    path("forbidden/", forbidden_view),
    path("missing/", not_found_view),
    path("server-error/", server_error_view),
    path("json-forbidden/", json_forbidden_view),
]


@override_settings(DEBUG=True, ROOT_URLCONF="App_PADESCE.core.test_error_urls")
class ErrorPageStaticIndependenceTests(TestCase):
    def test_500_page_does_not_depend_on_a_static_manifest_entry(self):
        user = get_user_model().objects.create_user("error-page-static-user", password="test-pass")
        self.client.force_login(user)
        self.client.raise_request_exception = False

        response = self.client.get("/server-error/")

        self.assertEqual(response.status_code, 500)
        self.assertNotContains(response, "branding/logo.png", status_code=500)
