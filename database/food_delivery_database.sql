-- Food Delivery Service Information System
-- PostgreSQL database setup
-- Run this file in pgAdmin Query Tool or with psql.
--
-- This script creates a schema named food_delivery.
-- It does not delete or overwrite existing schemas/tables.

CREATE SCHEMA IF NOT EXISTS food_delivery;
SET search_path TO food_delivery, public;

-- 1. CUSTOMER
CREATE TABLE IF NOT EXISTS customer (
    customer_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    phone       VARCHAR(20)  NOT NULL UNIQUE,
    address     VARCHAR(255) NOT NULL
);

-- 2. FOOD ITEM
CREATE TABLE IF NOT EXISTS food_item (
    food_item_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    price        NUMERIC(10, 2) NOT NULL CHECK (price > 0),
    category     VARCHAR(50) NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE
);

-- 3. FOOD ORDER
CREATE TABLE IF NOT EXISTS food_order (
    order_id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id  INTEGER NOT NULL,
    order_date   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status       VARCHAR(20) NOT NULL DEFAULT 'Placed'
                 CHECK (status IN ('Placed', 'Preparing', 'Delivered', 'Cancelled')),
    total_amount NUMERIC(10, 2) NOT NULL DEFAULT 0
                 CHECK (total_amount >= 0),

    CONSTRAINT fk_order_customer
        FOREIGN KEY (customer_id)
        REFERENCES customer(customer_id)
        ON DELETE RESTRICT
);

-- 4. ORDER ITEM (bridge table)
CREATE TABLE IF NOT EXISTS order_item (
    order_item_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id      INTEGER NOT NULL,
    food_item_id  INTEGER NOT NULL,
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),

    CONSTRAINT uq_order_food UNIQUE (order_id, food_item_id),

    CONSTRAINT fk_item_order
        FOREIGN KEY (order_id)
        REFERENCES food_order(order_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_item_food
        FOREIGN KEY (food_item_id)
        REFERENCES food_item(food_item_id)
        ON DELETE RESTRICT
);

-- Helpful indexes for common joins/lookups.
CREATE INDEX IF NOT EXISTS idx_food_order_customer_id
    ON food_order(customer_id);

CREATE INDEX IF NOT EXISTS idx_order_item_food_item_id
    ON order_item(food_item_id);

CREATE INDEX IF NOT EXISTS idx_food_order_order_date
    ON food_order(order_date);

-- Keep Food_Order.total_amount equal to SUM(quantity * unit_price).
-- The trigger handles inserts, updates and deletes in order_item.
CREATE OR REPLACE FUNCTION recalculate_order_total()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE food_order
        SET total_amount = COALESCE(
            (SELECT SUM(quantity * unit_price)
             FROM order_item
             WHERE order_id = OLD.order_id),
            0
        )
        WHERE order_id = OLD.order_id;

        RETURN OLD;

    ELSIF TG_OP = 'UPDATE' THEN
        -- Recalculate the old order if the line was moved to another order.
        IF OLD.order_id <> NEW.order_id THEN
            UPDATE food_order
            SET total_amount = COALESCE(
                (SELECT SUM(quantity * unit_price)
                 FROM order_item
                 WHERE order_id = OLD.order_id),
                0
            )
            WHERE order_id = OLD.order_id;
        END IF;

        UPDATE food_order
        SET total_amount = COALESCE(
            (SELECT SUM(quantity * unit_price)
             FROM order_item
             WHERE order_id = NEW.order_id),
            0
        )
        WHERE order_id = NEW.order_id;

        RETURN NEW;

    ELSE
        UPDATE food_order
        SET total_amount = COALESCE(
            (SELECT SUM(quantity * unit_price)
             FROM order_item
             WHERE order_id = NEW.order_id),
            0
        )
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

-- A useful read-only view for the manager's order list.
CREATE OR REPLACE VIEW order_summary AS
SELECT
    fo.order_id,
    c.customer_id,
    c.name AS customer_name,
    c.phone,
    c.address,
    fo.order_date,
    fo.status,
    fo.total_amount
FROM food_order AS fo
JOIN customer AS c
    ON c.customer_id = fo.customer_id;

-- ------------------------------------------------------------
-- OPTIONAL DEMO DATA
-- Uncomment this section if you want a small example to test.
-- Run it only once, or change the phone number before rerunning.
-- ------------------------------------------------------------
--
-- INSERT INTO customer (name, phone, address)
-- VALUES ('Aigerim', '+77000000001', 'Almaty, Kazakhstan')
-- RETURNING customer_id;
--
-- INSERT INTO food_item (name, price, category, is_available)
-- VALUES
--     ('Pizza', 2500.00, 'Main course', TRUE),
--     ('Burger', 1800.00, 'Main course', TRUE)
-- RETURNING food_item_id, name;
--
-- Then use the returned IDs in a transaction:
--
-- BEGIN;
-- INSERT INTO food_order (customer_id, status)
-- VALUES (1, 'Placed')
-- RETURNING order_id;
--
-- INSERT INTO order_item (order_id, food_item_id, quantity, unit_price)
-- VALUES
--     (1, 1, 2, 2500.00),
--     (1, 2, 1, 1800.00);
-- -- Trigger calculates total_amount = 6800.00.
-- COMMIT;
--
-- Check the result:
-- SELECT * FROM order_summary ORDER BY order_date DESC;
-- SELECT * FROM order_item ORDER BY order_item_id;

-- Useful queries:
-- All orders with customer names:
-- SELECT * FROM order_summary ORDER BY order_date DESC;
--
-- Detailed order lines:
-- SELECT
--     oi.order_id, fi.name AS food_name,
--     oi.quantity, oi.unit_price,
--     oi.quantity * oi.unit_price AS line_total
-- FROM order_item oi
-- JOIN food_item fi ON fi.food_item_id = oi.food_item_id
-- ORDER BY oi.order_id, oi.order_item_id;
--
-- Current available menu:
-- SELECT * FROM food_item WHERE is_available = TRUE ORDER BY category, name;
