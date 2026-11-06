
-- =====================================================
-- FOOD DELIVERY SERVICE
-- COMPLETE DATABASE SECURITY IMPLEMENTATION
-- PostgreSQL
-- =====================================================

SET search_path TO food_delivery, public;

-- =====================================================
-- 1. CREATE ROLES
-- =====================================================

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
END $$;

-- =====================================================
-- 2. CREATE LOGIN USERS
-- CHANGE EXAMPLE PASSWORDS BEFORE REAL USE
-- =====================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'customer_user') THEN
        CREATE ROLE customer_user LOGIN PASSWORD 'Customer123!';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'restaurant_staff') THEN
        CREATE ROLE restaurant_staff LOGIN PASSWORD 'Staff123!';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'delivery_courier') THEN
        CREATE ROLE delivery_courier LOGIN PASSWORD 'Courier123!';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'restaurant_manager') THEN
        CREATE ROLE restaurant_manager LOGIN PASSWORD 'Manager123!';
    END IF;
END $$;

GRANT customer_role TO customer_user;
GRANT staff_role TO restaurant_staff;
GRANT courier_role TO delivery_courier;
GRANT manager_role TO restaurant_manager;

-- =====================================================
-- 3. CREATE COURIER TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS courier (
    courier_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE
);

-- =====================================================
-- 4. CREATE ORDER ASSIGNMENT TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS order_assignment (
    order_id INTEGER PRIMARY KEY,
    courier_id INTEGER NOT NULL,

    FOREIGN KEY (order_id)
        REFERENCES food_order(order_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (courier_id)
        REFERENCES courier(courier_id)
        ON DELETE RESTRICT
);

-- =====================================================
-- 5. CONNECT LOGIN ACCOUNTS TO CUSTOMERS
-- =====================================================

CREATE TABLE IF NOT EXISTS customer_login_map (
    login_role NAME PRIMARY KEY,
    customer_id INTEGER NOT NULL UNIQUE
        REFERENCES customer(customer_id)
        ON DELETE RESTRICT
);

-- =====================================================
-- 6. CONNECT LOGIN ACCOUNTS TO COURIERS
-- =====================================================

CREATE TABLE IF NOT EXISTS courier_login_map (
    login_role NAME PRIMARY KEY,
    courier_id INTEGER NOT NULL UNIQUE
        REFERENCES courier(courier_id)
        ON DELETE RESTRICT
);

-- =====================================================
-- 7. REMOVE PUBLIC ACCESS TO LOGIN MAPPING TABLES
-- =====================================================

REVOKE ALL ON customer_login_map FROM PUBLIC;
REVOKE ALL ON courier_login_map FROM PUBLIC;

-- =====================================================
-- 8. CUSTOMER IDENTITY FUNCTION
-- =====================================================

CREATE OR REPLACE FUNCTION is_my_customer(
    p_customer_id INTEGER
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, food_delivery
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM customer_login_map
        WHERE login_role = session_user
          AND customer_id = p_customer_id
    );
$$;

-- =====================================================
-- 9. COURIER IDENTITY FUNCTIONS
-- =====================================================

CREATE OR REPLACE FUNCTION is_my_courier_order(
    p_order_id INTEGER
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, food_delivery
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM courier_login_map clm
        JOIN order_assignment oa
          ON oa.courier_id = clm.courier_id
        WHERE clm.login_role = session_user
          AND oa.order_id = p_order_id
    );
$$;

CREATE OR REPLACE FUNCTION is_my_courier_customer(
    p_customer_id INTEGER
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, food_delivery
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM courier_login_map clm
        JOIN order_assignment oa
          ON oa.courier_id = clm.courier_id
        JOIN food_order fo
          ON fo.order_id = oa.order_id
        WHERE clm.login_role = session_user
          AND fo.customer_id = p_customer_id
    );
$$;

-- Secure function execution
REVOKE ALL ON FUNCTION is_my_customer(INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION is_my_courier_order(INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION is_my_courier_customer(INTEGER) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION is_my_customer(INTEGER)
TO customer_role;

GRANT EXECUTE ON FUNCTION is_my_courier_order(INTEGER),
    is_my_courier_customer(INTEGER)
TO courier_role;

-- =====================================================
-- 10. SCHEMA PERMISSIONS
-- =====================================================

GRANT USAGE ON SCHEMA food_delivery
TO customer_role, staff_role, courier_role, manager_role;

-- =====================================================
-- 11. CUSTOMER PERMISSIONS
-- =====================================================

GRANT SELECT ON
    customer,
    food_order,
    order_item,
    food_item
TO customer_role;

-- =====================================================
-- 12. RESTAURANT STAFF PERMISSIONS
-- =====================================================

GRANT SELECT ON
    food_item,
    food_order,
    order_item,
    customer
TO staff_role;

GRANT UPDATE (status)
ON food_order
TO staff_role;

-- =====================================================
-- 13. COURIER PERMISSIONS
-- =====================================================

GRANT SELECT ON
    food_order,
    order_item,
    food_item
TO courier_role;

GRANT SELECT ON customer TO courier_role;

-- =====================================================
-- 14. MANAGER PERMISSIONS
-- =====================================================

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA food_delivery
TO manager_role;

GRANT USAGE, SELECT
ON ALL SEQUENCES IN SCHEMA food_delivery
TO manager_role;

-- =====================================================
-- 15. ENABLE ROW LEVEL SECURITY
-- =====================================================

ALTER TABLE customer ENABLE ROW LEVEL SECURITY;
ALTER TABLE food_order ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_item ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- 16. CUSTOMER POLICIES
-- =====================================================

DROP POLICY IF EXISTS customer_own_profile ON customer;
CREATE POLICY customer_own_profile
ON customer
FOR SELECT
TO customer_role
USING (is_my_customer(customer_id));

DROP POLICY IF EXISTS customer_own_orders ON food_order;
CREATE POLICY customer_own_orders
ON food_order
FOR SELECT
TO customer_role
USING (is_my_customer(customer_id));

DROP POLICY IF EXISTS customer_own_order_items ON order_item;
CREATE POLICY customer_own_order_items
ON order_item
FOR SELECT
TO customer_role
USING (
    EXISTS (
        SELECT 1
        FROM food_order fo
        WHERE fo.order_id = order_item.order_id
          AND is_my_customer(fo.customer_id)
    )
);

-- =====================================================
-- 17. COURIER POLICIES
-- =====================================================

DROP POLICY IF EXISTS courier_assigned_orders ON food_order;
CREATE POLICY courier_assigned_orders
ON food_order
FOR SELECT
TO courier_role
USING (is_my_courier_order(order_id));

DROP POLICY IF EXISTS courier_assigned_order_items ON order_item;
CREATE POLICY courier_assigned_order_items
ON order_item
FOR SELECT
TO courier_role
USING (is_my_courier_order(order_id));

DROP POLICY IF EXISTS courier_assigned_customers ON customer;
CREATE POLICY courier_assigned_customers
ON customer
FOR SELECT
TO courier_role
USING (is_my_courier_customer(customer_id));

-- =====================================================
-- 18. STAFF POLICIES
-- =====================================================

DROP POLICY IF EXISTS staff_view_orders ON food_order;
CREATE POLICY staff_view_orders
ON food_order
FOR SELECT
TO staff_role
USING (TRUE);

DROP POLICY IF EXISTS staff_update_orders ON food_order;
CREATE POLICY staff_update_orders
ON food_order
FOR UPDATE
TO staff_role
USING (TRUE)
WITH CHECK (TRUE);

DROP POLICY IF EXISTS staff_view_order_items ON order_item;
CREATE POLICY staff_view_order_items
ON order_item
FOR SELECT
TO staff_role
USING (TRUE);

DROP POLICY IF EXISTS staff_view_customers ON customer;
CREATE POLICY staff_view_customers
ON customer
FOR SELECT
TO staff_role
USING (TRUE);

-- =====================================================
-- 19. MANAGER POLICIES
-- =====================================================

DROP POLICY IF EXISTS manager_all_orders ON food_order;
CREATE POLICY manager_all_orders
ON food_order
FOR ALL
TO manager_role
USING (TRUE)
WITH CHECK (TRUE);

DROP POLICY IF EXISTS manager_all_customers ON customer;
CREATE POLICY manager_all_customers
ON customer
FOR ALL
TO manager_role
USING (TRUE)
WITH CHECK (TRUE);

DROP POLICY IF EXISTS manager_all_order_items ON order_item;
CREATE POLICY manager_all_order_items
ON order_item
FOR ALL
TO manager_role
USING (TRUE)
WITH CHECK (TRUE);

-- =====================================================
-- 20. RESTRICTED COURIER DELIVERY VIEW
-- =====================================================

CREATE OR REPLACE VIEW courier_delivery_info
WITH (security_barrier = true)
AS
SELECT
    customer_id,
    name,
    address
FROM customer
WHERE is_my_courier_customer(customer_id);

GRANT SELECT ON courier_delivery_info TO courier_role;

-- =====================================================
-- 21. RESTRICTED STAFF CUSTOMER VIEW
-- =====================================================

CREATE OR REPLACE VIEW customer_public
WITH (security_barrier = true)
AS
SELECT
    customer_id,
    name,
    address
FROM customer;

-- Revoke direct staff access to customer phone numbers
REVOKE SELECT ON customer FROM staff_role;

GRANT SELECT ON customer_public TO staff_role;

-- =====================================================
-- 22. PASSWORD ENCRYPTION SETTING
-- =====================================================

ALTER ROLE customer_user SET password_encryption = 'scram-sha-256';
ALTER ROLE restaurant_staff SET password_encryption = 'scram-sha-256';
ALTER ROLE delivery_courier SET password_encryption = 'scram-sha-256';
ALTER ROLE restaurant_manager SET password_encryption = 'scram-sha-256';

-- =====================================================
-- 23. VERIFY SECURITY ROLES
-- =====================================================

SELECT
    rolname AS role_name,
    rolcanlogin AS can_login
FROM pg_roles
WHERE rolname IN (
    'customer_role',
    'staff_role',
    'courier_role',
    'manager_role',
    'customer_user',
    'restaurant_staff',
    'delivery_courier',
    'restaurant_manager'
)
ORDER BY rolname;

-- =====================================================
-- END OF SECURITY SCRIPT
-- =====================================================
