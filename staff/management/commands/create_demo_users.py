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
| admin_demo     | administrator (superuser)  | everything, pages "Managers", "Couriers"    |
| courier_demo   | courier Arman              | delivery of order #2 (Dastarkhan, Preparing)|
| courier2_demo  | courier Dana               | no deliveries yet: a manager assigns one    |

Restaurants and orders come from `python manage.py seed_demo`; the two commands
can run in any order. Running this again resets only these eight accounts
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
    # username,        role,       group,         superuser
    ("customer_demo",  "customer", None,          False),
    ("customer2_demo", "customer", None,          False),
    ("staff_demo",     "customer", STAFF_GROUP,   False),
    ("staff2_demo",    "customer", STAFF_GROUP,   False),
    ("owner_demo",     "owner",    None,          False),
    ("admin_demo",     "admin",    None,          True),
    ("courier_demo",   "courier",  None,          False),
    ("courier2_demo",  "courier",  None,          False),
]

DEMO_NAMES = {"courier_demo": ("Arman", "Courier"), "courier2_demo": ("Dana", "Courier")}

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


def link_demo_courier(user):
    """courier_demo gets the delivery of the demo order that is being prepared (#2, Dastarkhan)."""
    from core.delivery import assign_courier
    from core.models import Delivery, FoodOrder

    if user.username != "courier_demo":
        return
    order = (FoodOrder.objects.filter(restaurant__owner__username="owner_demo", restaurant__name="Dastarkhan",
                                      status=FoodOrder.Status.PREPARING, delivery__isnull=True)
             .select_related("customer").order_by("order_id").first())
    if order:
        assign_courier(order, user)
    else:  # already assigned earlier: keep it, only refresh the courier's name
        Delivery.objects.filter(courier=user).update(courier_name=user.get_full_name() or user.username)


class Command(BaseCommand):
    help = "Create demo users for every role: customers, employees, owner (manager), admin, couriers."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=DEMO_PASSWORD,
                            help=f"Password for all demo users (default: {DEMO_PASSWORD})")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo users are only for local development (DEBUG is off).")

        User = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name=STAFF_GROUP)

        for username, role, group_name, superuser in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"})
            user.role = role
            user.is_superuser = superuser
            user.is_staff = superuser  # is_staff = may log in to /admin/
            user.first_name, user.last_name = DEMO_NAMES.get(username, (user.first_name, user.last_name))
            user.set_password(options["password"])  # stored as a PBKDF2 hash, never as plain text
            user.save()
            if group_name == STAFF_GROUP:
                user.groups.add(staff_group)
                link_demo_staff(user)
            else:
                user.groups.remove(staff_group)
            link_demo_customer(user)
            link_demo_courier(user)
            action = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"{username:<15} {action}"))

        if options["password"] == DEMO_PASSWORD:
            self.stdout.write(f"Password for all demo users: {DEMO_PASSWORD}")
