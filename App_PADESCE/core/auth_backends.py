from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import check_password


class SQLiteSafeModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if username is None or password is None:
            return None

        UserModel = get_user_model()
        try:
            user = UserModel._default_manager.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            UserModel().set_password(password)
            return None

        if check_password(password, user.password) and self.user_can_authenticate(user):
            return user
        return None
