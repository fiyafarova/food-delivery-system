from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        OWNER = 'owner', 'Restaurant Owner'
        ADMIN = 'admin', 'Admin'

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    @property
    def is_restaurant_owner(self):
        return self.is_superuser or self.role in (self.Role.OWNER, self.Role.ADMIN)


class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class DeliveryAddress(models.Model):
    profile = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="delivery_addresses")
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255)

    class Meta:
        ordering = ["pk"]


class SavedCard(models.Model):
    """A card label for checkout selection, without payment credentials."""
    class Brand(models.TextChoices):
        VISA = "visa", "Visa"
        MASTERCARD = "mastercard", "Mastercard"
        OTHER = "other", _("Other")

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_cards")
    nickname = models.CharField(max_length=50)
    brand = models.CharField(max_length=20, choices=Brand.choices, default=Brand.OTHER)
    last4 = models.CharField(max_length=4)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.nickname} · •••• {self.last4}"
