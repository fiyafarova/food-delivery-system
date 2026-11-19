"""Create one demo account for every role (local development / class demo only).

    python manage.py create_demo_users                      # password: BiteBox-demo-2026
    python manage.py create_demo_users --password <other>   # your own password

| username       | who                        | works with                                  |
|----------------|----------------------------|---------------------------------------------|
| customer_demo  | customer Aigerim           | own orders: #1 Casa Pizza, #4 Dastarkhan    |
| customer2_demo | customer Dias              | own order: #2 Dastarkhan                    |
| staff_demo     | employee                   | Casa Pizza                                  |
| staff2_demo    | employee                   | Urban Burger, Dastarkhan                    |
| owner_demo     | manager (restaurant owner) | owns all 3 demo restaurants, page "Team"    |
| admin_demo     | administrator (superuser)  | everything, page "Managers", /admin/        |

Restaurants and orders come from `python manage.py seed_demo`; the two commands
can run in any order. Running this again resets only these six accounts
(password, role, restaurants).

The default password is written in the README on purpose: these accounts are
for a local demo. The command refuses to run when DEBUG is off.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from restaurants.models import Restaurant
from staff.permissions import STAFF_GROUP

DEMO_PASSWORD = "BiteBox-demo-2026"

DEMO_USERS = [
    # username,        role,       in staff group, superuser
    ("customer_demo",  "customer", False, False),
    ("customer2_demo", "customer", False, False),
    ("staff_demo",     "customer", True,  False),
    ("staff2_demo",    "customer", True,  False),
    ("owner_demo",     "owner",    False, False),
    ("admin_demo",     "admin",    False, True),
]

# Each demo employee works only in these restaurants (owned by owner_demo, see core seed_demo)
DEMO_STAFF_RESTAURANTS = {
    "staff_demo": ["Casa Pizza"],
    "staff2_demo": ["Urban Burger", "Dastarkhan"],
}

# Demo customer accounts -> Customer rows from core seed_demo (matched by phone)
DEMO_CUSTOMER_PHONES = {"customer_demo": "+77010000001", "customer2_demo": "+77010000002"}


def link_demo_customer(user):
    """Give a demo customer account its demo orders (works in any order with seed_demo)."""
    from core.models import Customer

    phone = DEMO_CUSTOMER_PHONES.get(user.username)
    if phone:
        Customer.objects.filter(phone=phone, user__isnull=True).update(user=user)


def link_demo_staff(user):
    """Put a demo employee into exactly their demo restaurants."""
    names = DEMO_STAFF_RESTAURANTS.get(user.username)
    if names is not None:
        user.staff_restaurants.set(Restaurant.objects.filter(owner__username="owner_demo", name__in=names))


class Command(BaseCommand):
    help = "Create demo users for every role: customers, employees, owner (manager), admin."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=DEMO_PASSWORD,
                            help=f"Password for all demo users (default: {DEMO_PASSWORD})")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo users are only for local development (DEBUG is off).")

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
                link_demo_staff(user)
            else:
                user.groups.remove(group)
            link_demo_customer(user)
            action = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"{username:<15} {action}"))

        if options["password"] == DEMO_PASSWORD:
            self.stdout.write(f"Password for all demo users: {DEMO_PASSWORD}")
