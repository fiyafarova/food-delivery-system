
-- ============================================
-- FOOD DELIVERY SYSTEM: DATABASE SECURITY
-- PostgreSQL
-- ============================================

-- 1. CREATE USER ROLES

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

-- 2. CREATE LOGIN USERS
-- Change these example passwords before real use.

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
END
$$;

-- 3. CONNECT USERS TO THEIR ROLES

GRANT customer_role TO customer_user;
GRANT staff_role TO restaurant_staff;
GRANT courier_role TO delivery_courier;
GRANT manager_role TO restaurant_manager;

-- 4. SCHEMA ACCESS

GRANT USAGE ON SCHEMA food_delivery
TO customer_role, staff_role, courier_role, manager_role;

-- 5. CUSTOMER PERMISSIONS
-- Customers use the application to access their own data.
-- Direct table access is not granted.

-- 6. RESTAURANT STAFF PERMISSIONS

GRANT SELECT ON
    food_delivery.food_item,
    food_delivery.food_order,
    food_delivery.order_item
TO staff_role;

GRANT UPDATE (status)
ON food_delivery.food_order
TO staff_role;

-- Staff can see customer details needed for order preparation.
-- They cannot directly access phone numbers.

-- 7. COURIER PERMISSIONS

GRANT SELECT ON
    food_delivery.food_order,
    food_delivery.customer
TO courier_role;

-- NOTE: Assignment-based access requires a courier assignment table.

-- 8. MANAGER PERMISSIONS

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA food_delivery
TO manager_role;

GRANT USAGE, SELECT
ON ALL SEQUENCES IN SCHEMA food_delivery
TO manager_role;

-- 9. CREATE A RESTRICTED CUSTOMER VIEW

CREATE OR REPLACE VIEW food_delivery.customer_public AS
SELECT
    customer_id,
    name,
    address
FROM food_delivery.customer;

GRANT SELECT ON food_delivery.customer_public
TO staff_role;

-- 10. PASSWORD ENCRYPTION CONFIGURATION

ALTER ROLE customer_user SET password_encryption = 'scram-sha-256';
ALTER ROLE restaurant_staff SET password_encryption = 'scram-sha-256';
ALTER ROLE delivery_courier SET password_encryption = 'scram-sha-256';
ALTER ROLE restaurant_manager SET password_encryption = 'scram-sha-256';

-- 11. VERIFY CREATED ROLES

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

-- ============================================
-- END OF SECURITY SCRIPT
-- ============================================
