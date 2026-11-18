"""Create one demo account for every role (local development / class demo only).

    python manage.py create_demo_users --password <password>

| username       | who                         | how the role is stored               |
|----------------|-----------------------------|--------------------------------------|
| customer_demo  | customer (normal user)      | role = "customer"; orders of Aigerim |
| customer2_demo | second customer             | role = "customer"; orders of Dias    |
| staff_demo     | employee (restaurant staff) | group "Restaurant staff" + staff of  |
|                |                             | owner_demo's restaurants (seed_demo) |
| owner_demo     | manager (restaurant owner)  | role = "owner"                       |
| admin_demo     | administrator               | role = "admin", superuser, /admin/   |

Running it again resets the passwords and roles of these four users only.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from restaurants.models import Restaurant
from staff.permissions import STAFF_GROUP

DEMO_USERS = [
    # username,       role,       in staff group, superuser
    ("customer_demo", "customer", False, False),
    ("customer2_demo", "customer", False, False),
    ("staff_demo",    "customer", True,  False),
    ("owner_demo",    "owner",    False, False),
    ("admin_demo",    "admin",    False, True),
]


# Demo customer accounts -> Customer rows from core seed_demo (matched by phone)
DEMO_CUSTOMER_PHONES = {"customer_demo": "+77010000001", "customer2_demo": "+77010000002"}


def link_demo_customer(user):
    """Give a demo customer account its demo orders (works in any order with seed_demo)."""
    from core.models import Customer

    phone = DEMO_CUSTOMER_PHONES.get(user.username)
    if phone:
        Customer.objects.filter(phone=phone, user__isnull=True).update(user=user)


class Command(BaseCommand):
    help = "Create demo users for every role: customer, employee, owner (manager), admin."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Password for all demo users")

    def handle(self, *args, **options):
        User = get_user_model()
        group, _ = Group.objects.get_or_create(name=STAFF_GROUP)

        for username, role, in_staff_group, superuser in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"})
            user.role = role
            user.is_superuser = superuser
            user.is_staff = superuser  # is_staff = may log in to /admin/
            user.set_password(options["password"])  # stored as a PBKDF2 hash, never as plain text
            user.save()
            if in_staff_group:
                user.groups.add(group)
            else:
                user.groups.remove(group)
            if in_staff_group:
                # works in the demo restaurants (see core seed_demo)
                user.staff_restaurants.add(*Restaurant.objects.filter(owner__username="owner_demo"))
            link_demo_customer(user)
            action = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"{username:<14} {action}"))
