"""Quick smoke test for the tastefast module."""

import os
os.environ["TASTEFAST_DB"] = ":memory:"

from tastefast.db import init_db
from tastefast.seed import seed
import tastefast as tf

init_db()
seed()

# List all products
result = tf.list_products()
assert len(result["products"]) > 0, "No products"
print(f"[OK] {len(result['products'])} produtos no cardápio")

# Filter by category
lanches = tf.list_products(category="lanche")
assert all(p["category"] == "lanche" for p in lanches["products"])
print(f"[OK] {len(lanches['products'])} lanches")

# Create order (balcão)
order = tf.create_order(customer_name="João Silva", customer_phone="11999990000")
oid = order["order_id"]
print(f"[OK] Pedido criado: #{oid}")

# Add items
r = tf.add_item_to_order(oid, product_id=1, quantity=2)
assert len(r["items"]) == 1
r = tf.add_item_to_order(oid, product_id=7, quantity=2)
assert len(r["items"]) == 2
print(f"[OK] 2 itens adicionados | subtotal: R$ {r['order']['subtotal']:.2f}")

# Add same item again (should accumulate)
r = tf.add_item_to_order(oid, product_id=1, quantity=1)
assert r["items"][0]["quantity"] == 3
print(f"[OK] Quantidade acumulada corretamente")

# Set payment
r = tf.set_payment_method(oid, "pix")
assert r["payment_method"] == "pix"
print("[OK] Forma de pagamento: pix")

# Set delivery
r = tf.set_delivery(oid, is_delivery=True, delivery_address="Rua das Flores, 123", delivery_fee=5.0)
assert r["is_delivery"] is True
print("[OK] Modo delivery ativado com taxa R$ 5,00")

# Confirm
r = tf.confirm_order(oid)
assert r["status"] == "confirmed"
print("[OK] Pedido confirmado")

# Status flow
tf.mark_preparing(oid)
tf.mark_ready(oid)
r = tf.mark_delivered(oid)
assert r["status"] == "delivered"
full = tf.get_order(oid)
assert full["order"]["payment_status"] == "paid"
print(f"[OK] Fluxo completo: pending→confirmed→preparing→ready→delivered | total: R$ {full['order']['total']:.2f}")

# Cancel a new order
o2 = tf.create_order(customer_name="Maria", payment_method="dinheiro")
tf.add_item_to_order(o2["order_id"], product_id=2, quantity=1)
r = tf.cancel_order(o2["order_id"], reason="Cliente desistiu")
assert r["status"] == "cancelled"
print(f"[OK] Pedido #{o2['order_id']} cancelado")

# List orders
all_orders = tf.list_orders()
assert len(all_orders["orders"]) == 2
print(f"[OK] {len(all_orders['orders'])} pedidos listados")

print("\nTodos os testes passaram.")
