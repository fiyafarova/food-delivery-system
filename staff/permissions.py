"""Who may open the /staff/ pages.

Rule: the user must be logged in AND be one of:
- an employee: member of the group "Restaurant staff"
- a manager: User.role "owner" (restaurant owner) or "admin"
- a superuser

- not logged in      -> redirect to the staff login page
- logged in, no role -> 403 Forbidden
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

STAFF_GROUP = "Restaurant staff"


def is_restaurant_staff(user):
    if not user.is_authenticated:
        return False
    if user.is_restaurant_owner:  # superuser, role "owner" or role "admin" (accounts.User)
        return True
    return user.groups.filter(name=STAFF_GROUP).exists()


def staff_required(view):
    """Decorator for staff views. Put it above @require_POST."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="staff:login")
        if not is_restaurant_staff(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
