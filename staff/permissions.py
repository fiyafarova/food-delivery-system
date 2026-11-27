"""Who may open the /staff/ pages.

Rule: the user must be logged in AND be one of:
- an employee: member of the group "Restaurant staff"
- a manager: User.role "owner" (restaurant owner) or "admin"
- a superuser

- not logged in      -> redirect to the staff login page
- logged in, no role -> 403 Forbidden

Couriers (group "Courier") have their own page /staff/courier/ (courier_required):
they see only deliveries assigned to them, not the restaurant pages.

Which restaurants a user works with (restaurants_for):
- superuser / role "admin": all restaurants
- role "owner": restaurants they own (+ where they are staff)
- employee: restaurants where they are in Restaurant.staff
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Q

STAFF_GROUP = "Restaurant staff"
COURIER_GROUP = "Courier"


def is_restaurant_staff(user):
    if not user.is_authenticated:
        return False
    if user.is_restaurant_owner:  # superuser, role "owner" or role "admin" (accounts.User)
        return True
    return user.groups.filter(name=STAFF_GROUP).exists()


def is_courier(user):
    return user.is_authenticated and user.groups.filter(name=COURIER_GROUP).exists()


def restaurants_for(user):
    """Restaurants whose orders and dishes this user may see and change."""
    from restaurants.models import Restaurant  # local import: avoids loading models at import time

    if user.is_superuser or user.role == user.Role.ADMIN:
        return Restaurant.objects.all()
    return Restaurant.objects.filter(Q(owner=user) | Q(staff=user)).distinct()


def must_change_password(user):
    from .models import TemporaryPassword

    return TemporaryPassword.objects.filter(user=user).exists()


def is_manager(user):
    """Manager = restaurant owner (role "owner"), admin (role "admin") or superuser."""
    return user.is_authenticated and user.is_restaurant_owner


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.role == user.Role.ADMIN)


def manager_required(view):
    """Like staff_required, but only for managers (owners) and admins."""

    @wraps(view)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not is_manager(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def courier_required(view):
    """Like staff_required, but for the courier pages."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="staff:login")
        if not is_courier(request.user):
            raise PermissionDenied
        if must_change_password(request.user):
            return redirect_to_login(request.get_full_path(), login_url="staff:password_change")
        return view(request, *args, **kwargs)

    return wrapper


def staff_required(view):
    """Decorator for staff views. Put it above @require_POST."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="staff:login")
        if not is_restaurant_staff(request.user):
            raise PermissionDenied
        if must_change_password(request.user):
            # temporary password from a manager/admin: set an own password first
            return redirect_to_login(request.get_full_path(), login_url="staff:password_change")
        return view(request, *args, **kwargs)

    return wrapper
