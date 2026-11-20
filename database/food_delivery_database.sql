-- ============================================================
-- FOOD DELIVERY SYSTEM: SQL LAYER (trigger, view, roles, security)
-- PostgreSQL / Supabase
--
-- RUN AFTER:  python manage.py migrate
-- Tables customer, food_order, order_item, restaurants_* are created by
-- Django migrations. This file only adds things on top of them.
-- Safe to run again (idempotent).
--
-- NO PASSWORDS IN THIS FILE. Login roles are created without a password
-- and cannot log in until you set one (see the notes at the end).
-- ============================================================

SET search_path TO food_delivery, public;

-- ------------------------------------------------------------
-- 1. TRIGGER: keep food_order.total_amount = SUM(quantity * unit_price)
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION recalculate_order_total()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE food_order
        SET total_amount = COALESCE(
            (SELECT SUM(quantity * unit_price)
             FROM order_item WHERE order_id = OLD.order_id), 0)
        WHERE order_id = OLD.order_id;
        RETURN OLD;

    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.order_id <> NEW.order_id THEN
            UPDATE food_order
            SET total_amount = COALESCE(
                (SELECT SUM(quantity * unit_price)
                 FROM order_item WHERE order_id = OLD.order_id), 0)
            WHERE order_id = OLD.order_id;
        END IF;

        UPDATE food_order
        SET total_amount = COALESCE(
            (SELECT SUM(quantity * unit_price)
             FROM order_item WHERE order_id = NEW.order_id), 0)
        WHERE order_id = NEW.order_id;
        RETURN NEW;

    ELSE
        UPDATE food_order
        SET total_amount = COALESCE(
            (SELECT SUM(quantity * unit_price)
             FROM order_item WHERE order_id = NEW.order_id), 0)
        WHERE order_id = NEW.order_id;
        RETURN NEW;
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS trg_recalculate_order_total ON order_item;
CREATE TRIGGER trg_recalculate_order_total
AFTER INSERT OR UPDATE OR DELETE ON order_item
FOR EACH ROW
EXECUTE FUNCTION recalculate_order_total();

-- ------------------------------------------------------------
-- 2. VIEW: order list for managers
-- ------------------------------------------------------------
DROP VIEW IF EXISTS order_summary;
CREATE VIEW order_summary AS
SELECT
    fo.order_id,
    c.customer_id,
    c.name  AS customer_name,
    c.phone,
    c.address,
    r.id    AS restaurant_id,
    r.name  AS restaurant_name,
    fo.order_date,
    fo.status,
    fo.total_amount
FROM food_order AS fo
JOIN customer AS c ON c.customer_id = fo.customer_id
JOIN restaurants_restaurant AS r ON r.id = fo.restaurant_id;

-- ------------------------------------------------------------
-- 3. ROLES (no passwords here)
-- ------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'customer_role') THEN
        CREATE ROLE customer_role NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'staff_role') THEN
        CREATE ROLE staff_role NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'courier_role') THEN
        CREATE ROLE courier_role NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'manager_role') THEN
        CREATE ROLE manager_role NOLOGIN;
    END IF;
END
$$;

-- Login roles: LOGIN but NO password => cannot connect until a password is set.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'customer_user') THEN
        CREATE ROLE customer_user LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'restaurant_staff') THEN
        CREATE ROLE restaurant_staff LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'delivery_courier') THEN
        CREATE ROLE delivery_courier LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'restaurant_manager') THEN
        CREATE ROLE restaurant_manager LOGIN;
    END IF;
END
$$;

GRANT customer_role TO customer_user;
GRANT staff_role    TO restaurant_staff;
GRANT courier_role  TO delivery_courier;
GRANT manager_role  TO restaurant_manager;

GRANT USAGE ON SCHEMA food_delivery
TO customer_role, staff_role, courier_role, manager_role;

-- ------------------------------------------------------------
-- 4. EXTRA TABLES (not Django models): couriers and login mapping
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS courier (
    courier_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  VARCHAR(100) NOT NULL,
    phone VARCHAR(20)  NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS order_assignment (
    order_id   INTEGER PRIMARY KEY
        REFERENCES food_order(order_id) ON DELETE RESTRICT,
    courier_id INTEGER NOT NULL
        REFERENCES courier(courier_id)  ON DELETE RESTRICT
);

-- Which PostgreSQL login belongs to which customer / courier.
CREATE TABLE IF NOT EXISTS customer_login_map (
    login_role  NAME PRIMARY KEY,
    customer_id INTEGER NOT NULL UNIQUE
        REFERENCES customer(customer_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS courier_login_map (
    login_role NAME PRIMARY KEY,
    courier_id INTEGER NOT NULL UNIQUE
        REFERENCES courier(courier_id) ON DELETE RESTRICT
);

REVOKE ALL ON customer_login_map FROM PUBLIC;
REVOKE ALL ON courier_login_map   FROM PUBLIC;

-- ------------------------------------------------------------
-- 5. IDENTITY FUNCTIONS (SECURITY DEFINER, used by row-level security)
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION is_my_customer(p_customer_id INTEGER)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, food_delivery
AS $$
    SELECT EXISTS (
        SELECT 1 FROM customer_login_map
        WHERE login_role = session_user
          AND customer_id = p_customer_id
    );
$$;

CREATE OR REPLACE FUNCTION is_my_courier_order(p_order_id INTEGER)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, food_delivery
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM courier_login_map clm
        JOIN order_assignment oa ON oa.courier_id = clm.courier_id
        WHERE clm.login_role = session_user
          AND oa.order_id = p_order_id
    );
$$;

CREATE OR REPLACE FUNCTION is_my_courier_customer(p_customer_id INTEGER)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, food_delivery
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM courier_login_map clm
        JOIN order_assignment oa ON oa.courier_id = clm.courier_id
        JOIN food_order fo       ON fo.order_id   = oa.order_id
        WHERE clm.login_role = session_user
          AND fo.customer_id = p_customer_id
    );
$$;

REVOKE ALL ON FUNCTION is_my_customer(INTEGER)         FROM PUBLIC;
REVOKE ALL ON FUNCTION is_my_courier_order(INTEGER)    FROM PUBLIC;
REVOKE ALL ON FUNCTION is_my_courier_customer(INTEGER) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION is_my_customer(INTEGER) TO customer_role;
GRANT EXECUTE ON FUNCTION is_my_courier_order(INTEGER),
                          is_my_courier_customer(INTEGER) TO courier_role;

-- ------------------------------------------------------------
-- 6. RESTRICTED VIEWS
-- ------------------------------------------------------------
-- Staff see customer name/address, never the phone number.
DROP VIEW IF EXISTS customer_public;
CREATE VIEW customer_public
WITH (security_barrier = true) AS
SELECT customer_id, name, address
FROM customer;

-- A courier sees only customers of orders assigned to them.
DROP VIEW IF EXISTS courier_delivery_info;
CREATE VIEW courier_delivery_info
WITH (security_barrier = true) AS
SELECT customer_id, name, address
FROM customer
WHERE is_my_courier_customer(customer_id);

-- ------------------------------------------------------------
-- 7. TABLE PERMISSIONS
-- ------------------------------------------------------------
-- Customers: read-only on tables; rows limited by RLS below.
GRANT SELECT ON
    customer, food_order, order_item,
    restaurants_restaurant, restaurants_category, restaurants_fooditem
TO customer_role;

-- Restaurant staff: read orders and menu, change order status only.
GRANT SELECT ON
    food_order, order_item,
    restaurants_restaurant, restaurants_category, restaurants_fooditem
TO staff_role;
GRANT UPDATE (status) ON food_order TO staff_role;
REVOKE SELECT ON customer FROM staff_role;           -- no direct phone access
GRANT SELECT ON customer_public TO staff_role;

-- Couriers: assigned orders only (RLS below).
GRANT SELECT ON
    customer, food_order, order_item, restaurants_fooditem
TO courier_role;
GRANT SELECT ON courier_delivery_info TO courier_role;

-- Managers: full access to the schema.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA food_delivery TO manager_role;
GRANT USAGE, SELECT                  ON ALL SEQUENCES IN SCHEMA food_delivery TO manager_role;

-- Tables created by later migrations also go to managers.
ALTER DEFAULT PRIVILEGES IN SCHEMA food_delivery
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO manager_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA food_delivery
    GRANT USAGE, SELECT ON SEQUENCES TO manager_role;

-- ------------------------------------------------------------
-- 8. ROW LEVEL SECURITY
-- The Django connection (table owner) is NOT affected by these policies.
-- ------------------------------------------------------------
ALTER TABLE customer   ENABLE ROW LEVEL SECURITY;
ALTER TABLE food_order ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_item ENABLE ROW LEVEL SECURITY;

-- Customers: only their own data
DROP POLICY IF EXISTS customer_own_profile ON customer;
CREATE POLICY customer_own_profile ON customer
    FOR SELECT TO customer_role
    USING (is_my_customer(customer_id));

DROP POLICY IF EXISTS customer_own_orders ON food_order;
CREATE POLICY customer_own_orders ON food_order
    FOR SELECT TO customer_role
    USING (is_my_customer(customer_id));

DROP POLICY IF EXISTS customer_own_order_items ON order_item;
CREATE POLICY customer_own_order_items ON order_item
    FOR SELECT TO customer_role
    USING (EXISTS (
        SELECT 1 FROM food_order fo
        WHERE fo.order_id = order_item.order_id
          AND is_my_customer(fo.customer_id)
    ));

-- Couriers: only assigned orders
DROP POLICY IF EXISTS courier_assigned_orders ON food_order;
CREATE POLICY courier_assigned_orders ON food_order
    FOR SELECT TO courier_role
    USING (is_my_courier_order(order_id));

DROP POLICY IF EXISTS courier_assigned_order_items ON order_item;
CREATE POLICY courier_assigned_order_items ON order_item
    FOR SELECT TO courier_role
    USING (is_my_courier_order(order_id));

DROP POLICY IF EXISTS courier_assigned_customers ON customer;
CREATE POLICY courier_assigned_customers ON customer
    FOR SELECT TO courier_role
    USING (is_my_courier_customer(customer_id));

-- Staff: all orders (filtering by restaurant is done by the application)
DROP POLICY IF EXISTS staff_view_orders ON food_order;
CREATE POLICY staff_view_orders ON food_order
    FOR SELECT TO staff_role USING (TRUE);

DROP POLICY IF EXISTS staff_update_orders ON food_order;
CREATE POLICY staff_update_orders ON food_order
    FOR UPDATE TO staff_role USING (TRUE) WITH CHECK (TRUE);

DROP POLICY IF EXISTS staff_view_order_items ON order_item;
CREATE POLICY staff_view_order_items ON order_item
    FOR SELECT TO staff_role USING (TRUE);

-- Managers: everything
DROP POLICY IF EXISTS manager_all_orders ON food_order;
CREATE POLICY manager_all_orders ON food_order
    FOR ALL TO manager_role USING (TRUE) WITH CHECK (TRUE);

DROP POLICY IF EXISTS manager_all_customers ON customer;
CREATE POLICY manager_all_customers ON customer
    FOR ALL TO manager_role USING (TRUE) WITH CHECK (TRUE);

DROP POLICY IF EXISTS manager_all_order_items ON order_item;
CREATE POLICY manager_all_order_items ON order_item
    FOR ALL TO manager_role USING (TRUE) WITH CHECK (TRUE);

-- ------------------------------------------------------------
-- 9. VERIFY: login roles exist; has_password must be false until you set one
-- ------------------------------------------------------------
SELECT r.rolname AS role_name,
       r.rolcanlogin AS can_login,
       (s.passwd IS NOT NULL) AS has_password
FROM pg_roles r
LEFT JOIN pg_authid s ON s.oid = r.oid
WHERE r.rolname IN ('customer_role','staff_role','courier_role','manager_role',
                    'customer_user','restaurant_staff','delivery_courier','restaurant_manager')
ORDER BY r.rolname;