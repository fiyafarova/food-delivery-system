# Food Delivery System (Team 3)

Course project for Basics of Information Systems (KBTU).
Stack: Python 3.12+, Django, PostgreSQL 16 (Docker), Django templates + Bootstrap 5.
**Requires Python 3.12 or newer** (check with `python3 --version`).

## Run locally

Needs: Python 3.12+, Docker Desktop (running).

```bash
# 1. Start PostgreSQL 16 in Docker
docker compose up -d

# 2. Virtual environment + packages (only the first time)
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Create the tables (schema "food_delivery") and the group "Restaurant staff"
python manage.py migrate

# 4. Demo data: 3 restaurants, 11 dishes, 4 customers, 4 orders (safe to run again)
python manage.py seed_demo

# 5. Demo accounts for every role (choose any password, min. 8 characters)
#    staff_demo becomes staff of the demo restaurants, owner_demo owns them
python manage.py create_demo_users --password <choose-a-password>

# 6. Start the server
python manage.py runserver
```

Optional, Darya's SQL on top of the same tables (total trigger, `order_summary` view, PostgreSQL roles):

```bash
for f in food_delivery_database role_creation adding_security; do
  docker exec -i fooddelivery-db psql -U fooddelivery -d fooddelivery < database/$f.sql
done
```

Run the tests: `python manage.py test`

> If `migrate` fails with `InconsistentMigrationHistory ... accounts.0001_initial`, your local
> database was created before the custom `accounts.User` model. Reset the local Docker database
> (this deletes its data): `docker compose down -v && docker compose up -d && python manage.py migrate`.

## Pages

| Address | What | Who can open it |
|---|---|---|
| http://127.0.0.1:8000/ | customer menu | everyone |
| http://127.0.0.1:8000/register/ | customer sign-up | everyone |
| http://127.0.0.1:8000/login/ | customer login | everyone |
| http://127.0.0.1:8000/profile/?tab=orders | my order history → order page `/order/<id>/` | the customer who placed the order |
| http://127.0.0.1:8000/staff/login/ | staff login | everyone |
| http://127.0.0.1:8000/staff/team/ | register / remove employees | managers (owners), admins |
| http://127.0.0.1:8000/staff/managers/ | register managers with a restaurant | admins |
| http://127.0.0.1:8000/staff/password/ | change password | every logged-in user |
| http://127.0.0.1:8000/staff/orders/ | orders, status change, menu availability | employee, owner, admin |
| http://127.0.0.1:8000/admin/ | Django admin (users, roles, data) | admin only |
| http://127.0.0.1:8000/api/ | REST API: accounts, restaurants (see below) | depends on the endpoint |
| http://127.0.0.1:8000/core/ | JSON API: cart, orders, payments, delivery (`core/urls.py`) | see "Who sees which order" |

## Restaurants, dishes and orders

- Dishes live in **`restaurants.FoodItem`** (one table for the customer menu, cart, orders and staff pages).
- **One order = one restaurant.** The cart only accepts dishes from one restaurant: adding a dish from
  another restaurant asks to replace the cart (HTTP 409 in the API, `"replace": true` to confirm).
  `FoodOrder.restaurant` stores the restaurant; an order line with a dish from another restaurant is rejected.
- There is one cart for the site (`customer/cart.py`); the `/core/cart/...` API uses the same cart.
- **Staff see only their restaurants:** employees see restaurants where they are in *Restaurant → staff*
  (set in `/admin/`), owners see their own restaurants, admins see all.

## Who sees which order

- `Customer.user` links the customer (orders) to the site account. The `Customer` is created on the
  first order from the phone/address sent with the order or saved in the profile. A phone that already
  belongs to another customer is **not** linked (otherwise anyone could read someone else's orders).
- A customer sees only their own orders: profile → *Order history*, `/order/<id>/`, `GET /core/orders/mine/`.
  Someone else's order → 404; not logged in → login page (website) or 401 (API).
- Placing an order (`POST /core/orders/create/`) needs a logged-in customer.
- Changing order status, payment status and delivery: only staff / owner / admin of the order's restaurant.

## Users, roles and passwords

All users are stored in one table, `accounts_user` (custom model `accounts.User`).

| Role | Demo account | How the role is stored | Can do |
|---|---|---|---|
| Customer | `customer_demo`, `customer2_demo` | `role = "customer"` (default) + linked `Customer` | own orders only; `/staff/` → 403 |
| Employee (restaurant staff) | `staff_demo` | group **"Restaurant staff"** | `/staff/` pages |
| Manager (restaurant owner) | `owner_demo` | `role = "owner"` | `/staff/` pages, create/edit own restaurants and dishes via API |
| Administrator | `admin_demo` | `role = "admin"` + superuser | everything, including `/admin/` |

- **Registration** — who registers whom:

  | Role | Registered by | Page |
  |---|---|---|
  | Customer | themself | http://127.0.0.1:8000/register/ (or `POST /api/auth/register/`) |
  | Employee | a manager, for one of their restaurants | http://127.0.0.1:8000/staff/team/ |
  | Manager (restaurant owner) | an administrator, together with the restaurant | http://127.0.0.1:8000/staff/managers/ |

  Nobody can choose their own role: extra fields like `role` or `is_superuser` in a sign-up are ignored.
  Employees and managers get a **temporary password** and must change it at first login
  (staff pages open "Change password" until they do). Everyone can change the password at
  http://127.0.0.1:8000/staff/password/ (link in the profile and on the orders page).
- **Passwords** are never stored as text: Django saves a salted **PBKDF2-SHA256** hash
  (1 500 000 iterations), e.g. `pbkdf2_sha256$1500000$<salt>$<hash>`. Registration rejects short,
  common and numeric-only passwords.
- **Login**: web pages use a session (`/staff/login/`); the API uses JWT tokens
  (access token 60 min, refresh token 7 days).

### REST API quick check

```bash
# register (always a customer)
curl -X POST http://127.0.0.1:8000/api/auth/register/ -H "Content-Type: application/json" \
     -d '{"username":"anna","email":"anna@example.com","password":"<password>"}'
# login -> {"access": "...", "refresh": "..."}
curl -X POST http://127.0.0.1:8000/api/auth/login/ -H "Content-Type: application/json" \
     -d '{"username":"anna","password":"<password>"}'
# profile (put the access token after Bearer)
curl http://127.0.0.1:8000/api/profile/ -H "Authorization: Bearer <access>"
```

Other endpoints: `/api/auth/token/refresh/`, `/api/auth/change-password/`, `/api/restaurants/`,
`/api/categories/`, `/api/foods/`, `/api/search/?q=pizza`.

## Project structure

| Folder | What it contains | Owner   |
|---|---|---------|
| `core/` | Order models (Customer, FoodOrder, OrderItem, Payment, Delivery) + JSON API, `seed_demo` | Aksunkar, Darya |
| `accounts/`, `restaurants/` | Custom User, registration/JWT; Restaurant, Category, **FoodItem (the only dish table)**, search API | Sayazhan |
| `database/` | SQL: schema, total trigger, `order_summary` view, PostgreSQL roles | Darya |
| `customer/` | Client pages: menu, cart, checkout, order status | Dilnaz  |
| `staff/` | Staff pages: orders, order details, menu availability | Sofiya  |
| `templates/` | `base.html` (shared layout and language switcher) + page templates | shared  |
| `static/vendor/bootstrap/` | Bootstrap stored locally, so the demo works offline | shared  |
| `locale/` | Translation files (English + Russian) | shared  |

## Team rules

- One branch per feature (`customer-ui`, `staff-ui`, `backend-models`, ...). Do not push directly to `main`.
- Every change goes through a pull request reviewed by one other member.
- Shared files (`templates/base.html`, `config/settings.py`) are changed only after agreement in the team chat.
- Code you submit must be code you can explain. In the pull request, write what AI generated and what you changed.
