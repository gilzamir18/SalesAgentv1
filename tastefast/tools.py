"""
Tool functions for the TasteFast snack bar management system.
Each function returns a plain dict suitable for use as an agent tool response.
"""

from .db import get_conn


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

def create_customer(
    name: str,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    birthdate: str | None = None,
    notes: str | None = None,
) -> dict:
    """Register a new customer."""
    if not name.strip():
        return {"error": "Nome do cliente é obrigatório."}
    with get_conn() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO customers (name, phone, email, address, birthdate, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name.strip(), phone, email, address, birthdate, notes),
            )
            return {"customer_id": cur.lastrowid, "message": f"Cliente '{name}' cadastrado com sucesso."}
        except Exception as e:
            if "UNIQUE" in str(e):
                return {"error": f"Telefone '{phone}' já cadastrado."}
            return {"error": str(e)}


def get_customer(customer_id: int) -> dict:
    """Get a customer by id."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not row:
            return {"error": f"Cliente {customer_id} não encontrado."}
        return {"customer": dict(row)}


def find_customer(query: str) -> dict:
    """Search customers by name or phone (partial match)."""
    with get_conn() as conn:
        pattern = f"%{query}%"
        rows = conn.execute(
            "SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY name",
            (pattern, pattern),
        ).fetchall()
        return {"customers": [dict(r) for r in rows]}


def list_customers(limit: int = 50) -> dict:
    """List all customers ordered by name."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM customers ORDER BY name LIMIT ?", (limit,)
        ).fetchall()
        return {"customers": [dict(r) for r in rows]}


def update_customer(
    customer_id: int,
    name: str,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    birthdate: str | None = None,
    notes: str | None = None,
) -> dict:
    """Update customer data (all fields)."""
    if not name.strip():
        return {"error": "Nome do cliente é obrigatório."}
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not row:
            return {"error": f"Cliente {customer_id} não encontrado."}
        try:
            conn.execute(
                """UPDATE customers SET name=?, phone=?, email=?, address=?,
                   birthdate=?, notes=?, updated_at=datetime('now','localtime')
                   WHERE id=?""",
                (name.strip(), phone, email, address, birthdate, notes, customer_id),
            )
        except Exception as e:
            if "UNIQUE" in str(e):
                return {"error": f"Telefone '{phone}' já cadastrado em outro cliente."}
            return {"error": str(e)}
    return {"customer_id": customer_id, "message": "Cliente atualizado com sucesso."}


def delete_customer(customer_id: int) -> dict:
    """Delete a customer. Orders are kept (customer_id set to NULL)."""
    with get_conn() as conn:
        row = conn.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not row:
            return {"error": f"Cliente {customer_id} não encontrado."}
        conn.execute("UPDATE orders SET customer_id = NULL WHERE customer_id = ?", (customer_id,))
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    return {"message": f"Cliente '{row['name']}' removido."}


def get_customer_orders(customer_id: int) -> dict:
    """Get all orders linked to a customer."""
    with get_conn() as conn:
        row = conn.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not row:
            return {"error": f"Cliente {customer_id} não encontrado."}
        orders = conn.execute(
            "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        ).fetchall()
    return {"customer_name": row["name"], "orders": [dict(o) for o in orders]}


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def list_products(category: str | None = None, available_only: bool = True) -> dict:
    """List menu items, optionally filtered by category and availability."""
    with get_conn() as conn:
        query = "SELECT * FROM products WHERE 1=1"
        params: list = []
        if available_only:
            query += " AND available = 1"
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY category, name"
        rows = conn.execute(query, params).fetchall()
        return {"products": [dict(r) for r in rows]}


def get_product(product_id: int) -> dict:
    """Get details of a single product, including its images."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return {"error": f"Produto {product_id} não encontrado."}
        images = conn.execute(
            "SELECT * FROM product_images WHERE product_id = ? ORDER BY sort_order, id",
            (product_id,),
        ).fetchall()
        return {"product": dict(row), "images": [dict(i) for i in images]}


# ---------------------------------------------------------------------------
# Product CRUD
# ---------------------------------------------------------------------------

VALID_CATEGORIES = ("lanche", "bebida", "porcao", "sobremesa", "combo", "outro")


def add_product(
    name: str,
    description: str | None = None,
    category: str = "outro",
    price: float = 0.0,
    available: bool = True,
) -> dict:
    """Add a new product to the menu."""
    if category not in VALID_CATEGORIES:
        return {"error": f"Categoria inválida. Use: {', '.join(VALID_CATEGORIES)}."}
    if price < 0:
        return {"error": "Preço não pode ser negativo."}
    if not name.strip():
        return {"error": "Nome do produto é obrigatório."}
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO products (name, description, category, price, available) VALUES (?, ?, ?, ?, ?)",
            (name.strip(), description, category, price, int(available)),
        )
        product_id = cur.lastrowid
    return {"product_id": product_id, "message": f"Produto '{name}' adicionado com sucesso."}


def remove_product(product_id: int) -> dict:
    """Remove a product from the menu."""
    with get_conn() as conn:
        deleted = conn.execute("DELETE FROM products WHERE id = ?", (product_id,)).rowcount
    if not deleted:
        return {"error": f"Produto {product_id} não encontrado."}
    return {"message": f"Produto {product_id} removido com sucesso."}


def set_product_availability(product_id: int, available: bool) -> dict:
    """Enable or disable a product on the menu."""
    with get_conn() as conn:
        updated = conn.execute(
            "UPDATE products SET available = ? WHERE id = ?",
            (int(available), product_id),
        ).rowcount
    if not updated:
        return {"error": f"Produto {product_id} não encontrado."}
    state = "disponível" if available else "indisponível"
    return {"product_id": product_id, "available": available, "message": f"Produto {product_id} marcado como {state}."}


# ---------------------------------------------------------------------------
# Product images
# ---------------------------------------------------------------------------

def add_product_image(
    product_id: int,
    url: str,
    alt_text: str | None = None,
    sort_order: int = 0,
) -> dict:
    """Add an image to a product."""
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return {"error": f"Produto {product_id} não encontrado."}
        cur = conn.execute(
            "INSERT INTO product_images (product_id, url, alt_text, sort_order) VALUES (?, ?, ?, ?)",
            (product_id, url, alt_text, sort_order),
        )
        image_id = cur.lastrowid
    return {"image_id": image_id, "product_id": product_id, "message": "Imagem adicionada com sucesso."}


def remove_product_image(image_id: int) -> dict:
    """Remove an image from a product."""
    with get_conn() as conn:
        deleted = conn.execute(
            "DELETE FROM product_images WHERE id = ?", (image_id,)
        ).rowcount
    if not deleted:
        return {"error": f"Imagem {image_id} não encontrada."}
    return {"message": f"Imagem {image_id} removida com sucesso."}


def list_product_images(product_id: int) -> dict:
    """List all images of a product."""
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return {"error": f"Produto {product_id} não encontrado."}
        images = conn.execute(
            "SELECT * FROM product_images WHERE product_id = ? ORDER BY sort_order, id",
            (product_id,),
        ).fetchall()
    return {"product_id": product_id, "images": [dict(i) for i in images]}


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

def create_order(
    customer_name: str | None = None,
    customer_phone: str | None = None,
    customer_id: int | None = None,
    is_delivery: bool = False,
    delivery_address: str | None = None,
    delivery_fee: float = 0.0,
    payment_method: str | None = None,
    notes: str | None = None,
) -> dict:
    """Create a new empty order. Pass customer_id to link and auto-fill from registered customer."""
    with get_conn() as conn:
        if customer_id:
            row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if not row:
                return {"error": f"Cliente {customer_id} não encontrado."}
            customer_name = customer_name or row["name"]
            customer_phone = customer_phone or row["phone"]
            if is_delivery and not delivery_address:
                delivery_address = row["address"]
        if not customer_name or not customer_name.strip():
            return {"error": "Informe o nome do cliente ou um customer_id válido."}
        if is_delivery and not delivery_address:
            return {"error": "Endereço de entrega obrigatório para pedidos delivery."}
        payment_methods = ("dinheiro", "cartao_credito", "cartao_debito", "pix", None)
        if payment_method not in payment_methods:
            return {"error": "Forma de pagamento inválida. Use: dinheiro, cartao_credito, cartao_debito ou pix."}
        cur = conn.execute(
            """INSERT INTO orders
               (customer_name, customer_phone, customer_id, is_delivery,
                delivery_address, delivery_fee, payment_method, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (customer_name.strip(), customer_phone, customer_id, int(is_delivery),
             delivery_address, delivery_fee, payment_method, notes),
        )
        order_id = cur.lastrowid
    return {"order_id": order_id, "message": f"Pedido #{order_id} criado com sucesso."}


def get_order(order_id: int) -> dict:
    """Get full order details including items."""
    with get_conn() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            return {"error": f"Pedido #{order_id} não encontrado."}
        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
        ).fetchall()
        return {
            "order": dict(order),
            "items": [dict(i) for i in items],
        }


def list_orders(status: str | None = None, limit: int = 20) -> dict:
    """List orders, optionally filtered by status."""
    valid_statuses = ("pending", "confirmed", "preparing", "ready", "delivered", "cancelled", None)
    if status not in valid_statuses:
        return {"error": "Status inválido. Use: pending, confirmed, preparing, ready, delivered ou cancelled."}
    with get_conn() as conn:
        query = "SELECT * FROM orders WHERE 1=1"
        params: list = []
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return {"orders": [dict(r) for r in rows]}


def add_item_to_order(
    order_id: int,
    product_id: int,
    quantity: int = 1,
    notes: str | None = None,
) -> dict:
    """Add a product to an existing order."""
    if quantity <= 0:
        return {"error": "Quantidade deve ser maior que zero."}
    with get_conn() as conn:
        order = conn.execute(
            "SELECT status FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if not order:
            return {"error": f"Pedido #{order_id} não encontrado."}
        if order["status"] not in ("pending", "confirmed"):
            return {"error": f"Não é possível alterar pedido com status '{order['status']}'."}

        product = conn.execute(
            "SELECT * FROM products WHERE id = ? AND available = 1", (product_id,)
        ).fetchone()
        if not product:
            return {"error": f"Produto {product_id} não encontrado ou indisponível."}

        existing = conn.execute(
            "SELECT id, quantity FROM order_items WHERE order_id = ? AND product_id = ?",
            (order_id, product_id),
        ).fetchone()

        if existing:
            new_qty = existing["quantity"] + quantity
            conn.execute(
                "UPDATE order_items SET quantity = ? WHERE id = ?",
                (new_qty, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (order_id, product_id, product["name"], quantity, product["price"], notes),
            )

    return get_order(order_id)


def remove_item_from_order(order_id: int, product_id: int) -> dict:
    """Remove a product from an order."""
    with get_conn() as conn:
        order = conn.execute(
            "SELECT status FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if not order:
            return {"error": f"Pedido #{order_id} não encontrado."}
        if order["status"] not in ("pending", "confirmed"):
            return {"error": f"Não é possível alterar pedido com status '{order['status']}'."}

        deleted = conn.execute(
            "DELETE FROM order_items WHERE order_id = ? AND product_id = ?",
            (order_id, product_id),
        ).rowcount

        if not deleted:
            return {"error": "Item não encontrado no pedido."}

    return get_order(order_id)


# ---------------------------------------------------------------------------
# Order state transitions
# ---------------------------------------------------------------------------

def _update_order_status(order_id: int, new_status: str, allowed_from: tuple) -> dict:
    with get_conn() as conn:
        order = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            return {"error": f"Pedido #{order_id} não encontrado."}
        if order["status"] not in allowed_from:
            return {"error": f"Não é possível ir para '{new_status}' a partir de '{order['status']}'."}
        conn.execute(
            "UPDATE orders SET status = ?, updated_at = datetime('now','localtime') WHERE id = ?",
            (new_status, order_id),
        )
    return {"order_id": order_id, "status": new_status, "message": f"Pedido #{order_id} atualizado para '{new_status}'."}


def confirm_order(order_id: int) -> dict:
    """Confirm a pending order."""
    with get_conn() as conn:
        items = conn.execute(
            "SELECT COUNT(*) as cnt FROM order_items WHERE order_id = ?", (order_id,)
        ).fetchone()
        if not items or items["cnt"] == 0:
            return {"error": "Não é possível confirmar um pedido sem itens."}
    return _update_order_status(order_id, "confirmed", ("pending",))


def cancel_order(order_id: int, reason: str | None = None) -> dict:
    """Cancel an order that has not yet been delivered."""
    with get_conn() as conn:
        order = conn.execute("SELECT status, notes FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            return {"error": f"Pedido #{order_id} não encontrado."}
        if order["status"] in ("delivered", "cancelled"):
            return {"error": f"Pedido já está '{order['status']}' e não pode ser cancelado."}
        new_notes = order["notes"] or ""
        if reason:
            new_notes = f"{new_notes} [Cancelado: {reason}]".strip()
        conn.execute(
            "UPDATE orders SET status = 'cancelled', notes = ?, updated_at = datetime('now','localtime') WHERE id = ?",
            (new_notes, order_id),
        )
    return {"order_id": order_id, "status": "cancelled", "message": f"Pedido #{order_id} cancelado."}


def mark_preparing(order_id: int) -> dict:
    """Move order to 'preparing' status."""
    return _update_order_status(order_id, "preparing", ("confirmed",))


def mark_ready(order_id: int) -> dict:
    """Mark order as ready for pickup or delivery."""
    return _update_order_status(order_id, "ready", ("preparing",))


def mark_delivered(order_id: int) -> dict:
    """Mark order as delivered and payment as paid."""
    result = _update_order_status(order_id, "delivered", ("ready",))
    if "error" not in result:
        with get_conn() as conn:
            conn.execute(
                "UPDATE orders SET payment_status = 'paid', updated_at = datetime('now','localtime') WHERE id = ?",
                (order_id,),
            )
    return result


# ---------------------------------------------------------------------------
# Order settings
# ---------------------------------------------------------------------------

def set_payment_method(order_id: int, payment_method: str) -> dict:
    """Set or change the payment method of an order."""
    valid = ("dinheiro", "cartao_credito", "cartao_debito", "pix")
    if payment_method not in valid:
        return {"error": f"Forma de pagamento inválida. Use: {', '.join(valid)}."}
    with get_conn() as conn:
        order = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            return {"error": f"Pedido #{order_id} não encontrado."}
        if order["status"] in ("delivered", "cancelled"):
            return {"error": f"Não é possível alterar pagamento de pedido '{order['status']}'."}
        conn.execute(
            "UPDATE orders SET payment_method = ?, updated_at = datetime('now','localtime') WHERE id = ?",
            (payment_method, order_id),
        )
    return {"order_id": order_id, "payment_method": payment_method, "message": "Forma de pagamento atualizada."}


def set_delivery(
    order_id: int,
    is_delivery: bool,
    delivery_address: str | None = None,
    delivery_fee: float = 0.0,
) -> dict:
    """Set or change delivery mode and address."""
    if is_delivery and not delivery_address:
        return {"error": "Endereço de entrega obrigatório para pedidos delivery."}
    with get_conn() as conn:
        order = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            return {"error": f"Pedido #{order_id} não encontrado."}
        if order["status"] not in ("pending", "confirmed"):
            return {"error": f"Não é possível alterar modo de entrega com status '{order['status']}'."}
        conn.execute(
            """UPDATE orders SET is_delivery = ?, delivery_address = ?, delivery_fee = ?,
               updated_at = datetime('now','localtime') WHERE id = ?""",
            (int(is_delivery), delivery_address, delivery_fee, order_id),
        )
    return {
        "order_id": order_id,
        "is_delivery": is_delivery,
        "delivery_address": delivery_address,
        "delivery_fee": delivery_fee,
        "message": "Modo de entrega atualizado.",
    }
