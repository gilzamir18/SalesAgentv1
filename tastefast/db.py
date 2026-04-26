import sqlite3
import os

DB_PATH = os.environ.get("TASTEFAST_DB", "tastefast.db")


def get_conn() -> sqlite3.Connection:
    path = DB_PATH
    use_uri = False
    # ":memory:" is per-connection; use shared-cache URI for testability
    if path == ":memory:":
        path = "file::memory:?cache=shared"
        use_uri = True
    conn = sqlite3.connect(path, uri=use_uri)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                phone      TEXT UNIQUE,
                email      TEXT,
                address    TEXT,
                birthdate  TEXT,
                notes      TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                description TEXT,
                category    TEXT NOT NULL
                                CHECK(category IN (
                                    'lanche', 'bebida', 'porcao',
                                    'sobremesa', 'combo', 'outro'
                                )),
                price       REAL NOT NULL CHECK(price >= 0),
                available   INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS orders (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name    TEXT NOT NULL,
                customer_phone   TEXT,
                status           TEXT NOT NULL DEFAULT 'pending'
                                    CHECK(status IN (
                                        'pending', 'confirmed', 'preparing',
                                        'ready', 'delivered', 'cancelled'
                                    )),
                is_delivery      INTEGER NOT NULL DEFAULT 0,
                delivery_address TEXT,
                delivery_fee     REAL NOT NULL DEFAULT 0.0,
                payment_method   TEXT
                                    CHECK(payment_method IS NULL OR payment_method IN (
                                        'dinheiro', 'cartao_credito',
                                        'cartao_debito', 'pix'
                                    )),
                payment_status   TEXT NOT NULL DEFAULT 'pending'
                                    CHECK(payment_status IN ('pending', 'paid')),
                notes            TEXT,
                subtotal         REAL NOT NULL DEFAULT 0.0,
                total            REAL NOT NULL DEFAULT 0.0,
                created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id   INTEGER NOT NULL REFERENCES products(id),
                product_name TEXT NOT NULL,
                quantity     INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
                unit_price   REAL NOT NULL CHECK(unit_price >= 0),
                subtotal     REAL NOT NULL DEFAULT 0.0,
                notes        TEXT
            );

            CREATE TRIGGER IF NOT EXISTS trg_order_items_subtotal
            AFTER INSERT ON order_items
            BEGIN
                UPDATE order_items SET subtotal = NEW.quantity * NEW.unit_price
                WHERE id = NEW.id;
                UPDATE orders SET
                    subtotal   = (SELECT COALESCE(SUM(subtotal), 0) FROM order_items WHERE order_id = NEW.order_id),
                    total      = (SELECT COALESCE(SUM(subtotal), 0) FROM order_items WHERE order_id = NEW.order_id) + delivery_fee,
                    updated_at = datetime('now', 'localtime')
                WHERE id = NEW.order_id;
            END;

            CREATE TRIGGER IF NOT EXISTS trg_order_items_subtotal_update
            AFTER UPDATE OF quantity ON order_items
            BEGIN
                UPDATE order_items SET subtotal = NEW.quantity * NEW.unit_price
                WHERE id = NEW.id;
                UPDATE orders SET
                    subtotal   = (SELECT COALESCE(SUM(subtotal), 0) FROM order_items WHERE order_id = NEW.order_id),
                    total      = (SELECT COALESCE(SUM(subtotal), 0) FROM order_items WHERE order_id = NEW.order_id) + delivery_fee,
                    updated_at = datetime('now', 'localtime')
                WHERE id = NEW.order_id;
            END;

            CREATE TRIGGER IF NOT EXISTS trg_order_items_delete
            AFTER DELETE ON order_items
            BEGIN
                UPDATE orders SET
                    subtotal   = (SELECT COALESCE(SUM(subtotal), 0) FROM order_items WHERE order_id = OLD.order_id),
                    total      = (SELECT COALESCE(SUM(subtotal), 0) FROM order_items WHERE order_id = OLD.order_id) + delivery_fee,
                    updated_at = datetime('now', 'localtime')
                WHERE id = OLD.order_id;
            END;

            CREATE TABLE IF NOT EXISTS product_images (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                url         TEXT NOT NULL,
                alt_text    TEXT,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TRIGGER IF NOT EXISTS trg_customer_updated_at
            AFTER UPDATE ON customers
            BEGIN
                UPDATE customers SET updated_at = datetime('now', 'localtime')
                WHERE id = NEW.id;
            END;

            CREATE TRIGGER IF NOT EXISTS trg_order_delivery_fee
            AFTER UPDATE OF delivery_fee ON orders
            BEGIN
                UPDATE orders SET
                    total      = subtotal + NEW.delivery_fee,
                    updated_at = datetime('now', 'localtime')
                WHERE id = NEW.id;
            END;
        """)
        # Migration: add customer_id to orders if not present
        cols = {row[1] for row in conn.execute("PRAGMA table_info(orders)")}
        if "customer_id" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN customer_id INTEGER")
