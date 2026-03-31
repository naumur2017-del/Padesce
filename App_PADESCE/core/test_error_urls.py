from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpResponse, JsonResponse
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
