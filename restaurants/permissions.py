from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    """Anyone can read; only admins can write (used for categories)."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user.is_authenticated and
                    (request.user.role == 'admin' or request.user.is_superuser))


class IsOwnerOrReadOnly(BasePermission):
    """
    Anyone can read. Writing requires an owner/admin account, and for
    object-level actions the user must own the restaurant (or be admin).
    Works for both Restaurant and FoodItem objects.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user.is_authenticated and request.user.is_restaurant_owner)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.role == 'admin' or request.user.is_superuser:
            return True
        owner = obj.owner if hasattr(obj, 'owner') else obj.restaurant.owner
        return owner == request.user
