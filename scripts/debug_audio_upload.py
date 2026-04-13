from django.test.client import RequestFactory
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from App_PADESCE.appels.views import finalize_appel
from App_PADESCE.appels.models import Appel
from django.contrib.messages.storage.fallback import FallbackStorage

User = get_user_model()
user = User.objects.filter(is_active=True).first()
if not user:
    print("No user found")
    raise SystemExit(1)
appel = Appel.objects.filter(is_active=True).first()
if not appel:
    print("No appel found")
    raise SystemExit(1)
factory = RequestFactory()
file = SimpleUploadedFile("test.mp3", b"dummy audio", content_type="audio/mpeg")
request = factory.post(
    f"/appels/{appel.pk}/finalize/",
    {
        "action": "terminer",
        "q1": "3",
        "q2": "3",
        "q3": "3",
        "q4": "3",
        "q5": "3",
        "q6": "3",
        "q7": "3",
        "q8": "3",
        "q9": "3",
        "commentaire": "test",
        "recommandations": "test",
    },
    FILES={"audio": file},
)
request.user = user
setattr(request, "session", {})
setattr(request, "_messages", FallbackStorage(request))
response = finalize_appel(request, appel.pk)
print("response.status_code", response.status_code)
print("response.content", response.content)
appel.refresh_from_db()
print("audio file name", appel.audio_file.name)
print("audio exists", appel.audio_file.storage.exists(appel.audio_file.name))
