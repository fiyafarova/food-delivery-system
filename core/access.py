"""Who may see and change an order (used by the customer pages and the /core/ API).

- a customer sees only the orders of their own Customer (Customer.user)
- staff / owners / admins see and manage orders of their restaurants
  (staff.permissions.restaurants_for)
"""

from staff.permissions import is_restaurant_staff, restaurants_for

from .models import Customer


def customer_of(user):
    """The Customer linked to this account, or None."""
    if not user.is_authenticated:
        return None
    return Customer.objects.filter(user=user).first()


def can_manage_order(user, order):
    """Restaurant side: change status, payment, delivery."""
    return is_restaurant_staff(user) and restaurants_for(user).filter(pk=order.restaurant_id).exists()


def can_view_order(user, order):
    if not user.is_authenticated:
        return False
    if order.customer.user_id == user.pk:
        return True
    return can_manage_order(user, order)


class CustomerDataError(ValueError):
    """Phone/address missing or the phone belongs to someone else."""


def get_or_create_customer(user, name="", phone="", address=""):
    """Customer of this account; created on the first order.

    Missing values are taken from the account profile (accounts.CustomerProfile).
    A phone that already belongs to another customer is NOT linked to this account:
    otherwise anyone could see someone else's orders just by typing their phone.
    """
    customer = customer_of(user)
    if customer:
        return customer

    profile = getattr(user, "profile", None)
    name = (name or user.get_full_name() or user.get_username()).strip()
    phone = (phone or getattr(profile, "phone", "")).strip()
    address = (address or getattr(profile, "address", "")).strip()
    if not phone or not address:
        raise CustomerDataError("Phone and address are required for the first order.")
    if Customer.objects.filter(phone=phone).exists():
        raise CustomerDataError("This phone number is already used by another customer.")
    return Customer.objects.create(user=user, name=name[:100], phone=phone, address=address)
