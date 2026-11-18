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

# 4. Demo data: 4 customers, 10 dishes, 4 orders (core/fixtures/demo_data.json)
python manage.py loaddata demo_data

# 5. Demo accounts for every role (choose any password, min. 8 characters)
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
| http://127.0.0.1:8000/staff/login/ | staff login | everyone |
| http://127.0.0.1:8000/staff/orders/ | orders, status change, menu availability | employee, owner, admin |
| http://127.0.0.1:8000/admin/ | Django admin (users, roles, data) | admin only |
| http://127.0.0.1:8000/api/ | REST API: accounts, restaurants (see below) | depends on the endpoint |
| http://127.0.0.1:8000/core/ | JSON API: cart, orders, payments, delivery (`core/urls.py`) | everyone (no login yet) |

## Users, roles and passwords

All users are stored in one table, `accounts_user` (custom model `accounts.User`).

| Role | Demo account | How the role is stored | Can do |
|---|---|---|---|
| Customer | `customer_demo` | `role = "customer"` (default) | profile API, menu; `/staff/` → 403 |
| Employee (restaurant staff) | `staff_demo` | group **"Restaurant staff"** | `/staff/` pages |
| Manager (restaurant owner) | `owner_demo` | `role = "owner"` | `/staff/` pages, create/edit own restaurants and dishes via API |
| Administrator | `admin_demo` | `role = "admin"` + superuser | everything, including `/admin/` |

- **Registration** (`POST /api/auth/register/`) always creates a **customer**. A `role` sent in the
  request is ignored, so nobody can make themselves an owner or admin. Employees and managers get
  their role from an administrator in `/admin/` (Users → user → *Role* / *Groups*).
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
| `core/` | Order models (Customer, FoodItem, FoodOrder, OrderItem, Payment, Delivery) + JSON API | Aksunkar, Darya |
| `accounts/`, `restaurants/` | Custom User, registration/JWT, restaurants and search REST API | Sayazhan |
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
