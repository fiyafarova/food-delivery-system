from django.conf import settings
from django.db import models


class TemporaryPassword(models.Model):
    """The user got a temporary password from their manager / an admin.

    While this row exists, the staff pages send the user to "Change password" first.
    The row is deleted when the user sets their own password.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="temporary_password")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Temporary password: {self.user}"
