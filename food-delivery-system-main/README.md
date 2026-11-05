# Food Delivery System (Team 3)

Course project for Basics of Information Systems (KBTU).
Stack: Python 3.12+, Django, PostgreSQL 16 (Docker), Django templates + Bootstrap 5.
**Requires Python 3.12 or newer** (check with `python3 --version`).

## Run locally

```bash
# 1. Start PostgreSQL (needs Docker Desktop)
docker compose up -d

# 2. Create a virtual environment and install packages
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Create tables and start the server
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/ (menu) or http://127.0.0.1:8000/staff/orders/ (staff).

## Project structure

| Folder | What it contains | Owner   |
|---|---|---------|
| `core/` | Data models (Customer, Food_Item, Food_Order, Order_Item) | backend |
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
