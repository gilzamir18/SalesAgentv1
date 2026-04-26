"""TasteFast — painel de administração e simulação de pedidos."""

import os
os.environ.setdefault("TASTEFAST_DB", "tastefast.db")

import pandas as pd
import gradio as gr

from tastefast.db import init_db
from tastefast.tools import (
    create_customer,
    get_customer,
    find_customer,
    list_customers,
    update_customer,
    delete_customer,
    get_customer_orders,
    list_products,
    add_product,
    remove_product,
    set_product_availability,
    create_order,
    get_order,
    list_orders,
    add_item_to_order,
    remove_item_from_order,
    set_payment_method,
    set_delivery,
    confirm_order,
    cancel_order,
    mark_preparing,
    mark_ready,
    mark_delivered,
    VALID_CATEGORIES,
)

init_db()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CUSTOMER_COLS = ["id", "name", "phone", "email", "address", "birthdate", "notes", "created_at"]
_PRODUCT_COLS = ["id", "name", "description", "category", "price", "available", "created_at"]
_ORDER_COLS   = ["id", "customer_name", "customer_phone", "status", "payment_method",
                 "payment_status", "is_delivery", "subtotal", "total", "created_at"]


def _customers_df(search: str = "") -> pd.DataFrame:
    if search.strip():
        rows = find_customer(search.strip())["customers"]
    else:
        rows = list_customers(limit=100)["customers"]
    if not rows:
        return pd.DataFrame(columns=_CUSTOMER_COLS)
    df = pd.DataFrame(rows)
    return df[[c for c in _CUSTOMER_COLS if c in df.columns]]


def _fmt_customer(customer_id) -> str:
    if not customer_id:
        return "_Nenhum cliente selecionado._"
    r = get_customer(int(customer_id))
    if "error" in r:
        return f"**Erro:** {r['error']}"
    c = r["customer"]
    orders = get_customer_orders(int(customer_id)).get("orders", [])
    total_gasto = sum(o["total"] for o in orders if o["status"] == "delivered")
    lines = [
        f"### Cliente #{c['id']} — {c['name']}",
        f"**Tel:** {c.get('phone') or '—'}  |  **Email:** {c.get('email') or '—'}",
        f"**Endereço:** {c.get('address') or '—'}",
        f"**Aniversário:** {c.get('birthdate') or '—'}",
        f"**Obs:** {c.get('notes') or '—'}",
        f"**Pedidos:** {len(orders)}  |  **Total gasto (entregues):** R$ {total_gasto:.2f}",
    ]
    return "\n".join(lines)


def _products_df() -> pd.DataFrame:
    rows = list_products(available_only=False)["products"]
    if not rows:
        return pd.DataFrame(columns=_PRODUCT_COLS)
    df = pd.DataFrame(rows)[_PRODUCT_COLS]
    df["available"] = df["available"].map({1: "Sim", 0: "Não"})
    return df


def _product_choices():
    rows = list_products(available_only=True)["products"]
    return [(f"[{p['id']}] {p['name']}  R$ {p['price']:.2f}", p["id"]) for p in rows]


def _orders_df() -> pd.DataFrame:
    rows = list_orders(limit=50)["orders"]
    if not rows:
        return pd.DataFrame(columns=_ORDER_COLS)
    df = pd.DataFrame(rows)[_ORDER_COLS]
    df["is_delivery"] = df["is_delivery"].map({1: "Sim", 0: "Não"})
    return df


def _fmt_order(order_id) -> str:
    if not order_id:
        return "_Nenhum pedido em andamento._"
    result = get_order(int(order_id))
    if "error" in result:
        return f"**Erro:** {result['error']}"
    o, items = result["order"], result["items"]
    lines = [
        f"### Pedido #{o['id']}",
        f"**Status:** `{o['status']}`  |  **Pagamento:** `{o['payment_status']}`",
        f"**Cliente:** {o['customer_name']}  |  **Tel:** {o.get('customer_phone') or '—'}",
        f"**Entrega:** {'Sim → ' + str(o['delivery_address']) if o['is_delivery'] else 'Balcão'}  "
        f"| **Taxa:** R$ {o['delivery_fee']:.2f}",
        f"**Forma de pgto:** {o.get('payment_method') or '—'}",
        "",
        "**Itens:**",
    ]
    if items:
        for it in items:
            note = f" _{it['notes']}_" if it.get("notes") else ""
            lines.append(f"- {it['product_name']} × {it['quantity']} = **R$ {it['subtotal']:.2f}**{note}")
    else:
        lines.append("_(sem itens)_")
    lines += [
        "",
        f"Subtotal: R$ {o['subtotal']:.2f}  |  Taxa: R$ {o['delivery_fee']:.2f}",
        f"## Total: R$ {o['total']:.2f}",
    ]
    if o.get("notes"):
        lines.append(f"_Obs: {o['notes']}_")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gradio app
# ---------------------------------------------------------------------------

with gr.Blocks(title="TasteFast Admin") as demo:
    order_id_state = gr.State(None)

    gr.Markdown("# 🍔 TasteFast — Painel de Gestão")

    # ── Tab 1: Clientes ──────────────────────────────────────────────────────
    with gr.Tab("Clientes"):
        with gr.Row():
            inp_search_cust  = gr.Textbox(label="Buscar por nome ou telefone", scale=4)
            btn_search_cust  = gr.Button("Buscar", scale=1)
            btn_refresh_cust = gr.Button("Listar todos", variant="secondary", scale=1)

        tbl_customers = gr.Dataframe(value=_customers_df(), label="Clientes", interactive=False)

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Cadastrar cliente")
                with gr.Group():
                    inp_cn_name      = gr.Textbox(label="Nome *")
                    inp_cn_phone     = gr.Textbox(label="Telefone", placeholder="(11) 99999-0000")
                    inp_cn_email     = gr.Textbox(label="E-mail")
                    inp_cn_address   = gr.Textbox(label="Endereço padrão")
                    inp_cn_birthdate = gr.Textbox(label="Aniversário", placeholder="YYYY-MM-DD")
                    inp_cn_notes     = gr.Textbox(label="Observações", lines=2)
                    btn_create_cust  = gr.Button("Cadastrar", variant="primary")
                msg_cust = gr.Textbox(label="Resultado", interactive=False)

            with gr.Column():
                gr.Markdown("### Detalhe / editar")
                inp_cust_id     = gr.Number(label="ID do cliente", precision=0)
                btn_load_cust   = gr.Button("Carregar")
                cust_display    = gr.Markdown("_Nenhum cliente selecionado._")

                gr.Markdown("#### Editar campos")
                with gr.Group():
                    inp_ed_name      = gr.Textbox(label="Nome *")
                    inp_ed_phone     = gr.Textbox(label="Telefone")
                    inp_ed_email     = gr.Textbox(label="E-mail")
                    inp_ed_address   = gr.Textbox(label="Endereço padrão")
                    inp_ed_birthdate = gr.Textbox(label="Aniversário", placeholder="YYYY-MM-DD")
                    inp_ed_notes     = gr.Textbox(label="Observações", lines=2)
                with gr.Row():
                    btn_update_cust = gr.Button("Salvar alterações", variant="primary")
                    btn_delete_cust = gr.Button("Excluir cliente", variant="stop")

        # --- events ---
        def on_search_cust(q):
            return _customers_df(q)

        def on_create_cust(name, phone, email, address, birthdate, notes):
            r = create_customer(
                name=name, phone=phone or None, email=email or None,
                address=address or None, birthdate=birthdate or None, notes=notes or None,
            )
            msg = r.get("message") or r.get("error", "")
            return _customers_df(), msg

        def on_load_cust(cid):
            if not cid:
                return "_Informe o ID do cliente._", "", "", "", "", "", ""
            r = get_customer(int(cid))
            if "error" in r:
                return f"**Erro:** {r['error']}", "", "", "", "", "", ""
            c = r["customer"]
            return (
                _fmt_customer(int(cid)),
                c["name"],
                c.get("phone") or "",
                c.get("email") or "",
                c.get("address") or "",
                c.get("birthdate") or "",
                c.get("notes") or "",
            )

        def on_update_cust(cid, name, phone, email, address, birthdate, notes):
            if not cid:
                return _customers_df(), "_Informe o ID do cliente._", "Informe o ID."
            r = update_customer(
                int(cid), name=name, phone=phone or None, email=email or None,
                address=address or None, birthdate=birthdate or None, notes=notes or None,
            )
            msg = r.get("message") or r.get("error", "")
            return _customers_df(), _fmt_customer(int(cid)), msg

        def on_delete_cust(cid):
            if not cid:
                return _customers_df(), "_Informe o ID do cliente._", "Informe o ID."
            r = delete_customer(int(cid))
            msg = r.get("message") or r.get("error", "")
            return _customers_df(), "_Cliente removido._", msg

        btn_search_cust.click(fn=on_search_cust, inputs=inp_search_cust, outputs=tbl_customers)
        inp_search_cust.submit(fn=on_search_cust, inputs=inp_search_cust, outputs=tbl_customers)
        btn_refresh_cust.click(fn=_customers_df, outputs=tbl_customers)
        btn_create_cust.click(
            fn=on_create_cust,
            inputs=[inp_cn_name, inp_cn_phone, inp_cn_email, inp_cn_address, inp_cn_birthdate, inp_cn_notes],
            outputs=[tbl_customers, msg_cust],
        )
        btn_load_cust.click(
            fn=on_load_cust,
            inputs=inp_cust_id,
            outputs=[cust_display, inp_ed_name, inp_ed_phone, inp_ed_email, inp_ed_address, inp_ed_birthdate, inp_ed_notes],
        )
        btn_update_cust.click(
            fn=on_update_cust,
            inputs=[inp_cust_id, inp_ed_name, inp_ed_phone, inp_ed_email, inp_ed_address, inp_ed_birthdate, inp_ed_notes],
            outputs=[tbl_customers, cust_display, msg_cust],
        )
        btn_delete_cust.click(
            fn=on_delete_cust,
            inputs=inp_cust_id,
            outputs=[tbl_customers, cust_display, msg_cust],
        )

    # ── Tab 2: Cardápio ──────────────────────────────────────────────────────
    with gr.Tab("Cardápio"):
        with gr.Row():
            btn_refresh_prod = gr.Button("Atualizar lista", variant="secondary")

        tbl_products = gr.Dataframe(
            value=_products_df(),
            label="Produtos cadastrados",
            interactive=False,
        )

        gr.Markdown("### Adicionar produto")
        with gr.Row():
            inp_name     = gr.Textbox(label="Nome", placeholder="Ex: X-Bacon")
            inp_desc     = gr.Textbox(label="Descrição", placeholder="Ingredientes…")
            inp_cat      = gr.Dropdown(choices=list(VALID_CATEGORIES), value="lanche", label="Categoria")
            inp_price    = gr.Number(label="Preço (R$)", value=0.0, minimum=0)
            inp_avail    = gr.Checkbox(label="Disponível", value=True)
        btn_add_prod = gr.Button("Adicionar produto", variant="primary")
        msg_prod     = gr.Textbox(label="Resultado", interactive=False)

        gr.Markdown("### Remover / ativar produto")
        with gr.Row():
            inp_rem_id   = gr.Number(label="ID do produto", precision=0)
            btn_remove   = gr.Button("Remover produto", variant="stop")
            inp_tog_id   = gr.Number(label="ID do produto", precision=0)
            inp_tog_avail = gr.Checkbox(label="Disponível", value=True)
            btn_toggle   = gr.Button("Salvar disponibilidade")

        # --- events ---
        def on_add_product(name, desc, cat, price, avail):
            r = add_product(name, desc, cat, float(price), bool(avail))
            msg = r.get("message") or r.get("error", "")
            return _products_df(), msg

        def on_remove_product(pid):
            if not pid:
                return _products_df(), "Informe o ID do produto."
            r = remove_product(int(pid))
            return _products_df(), r.get("message") or r.get("error", "")

        def on_toggle(pid, avail):
            if not pid:
                return _products_df(), "Informe o ID do produto."
            r = set_product_availability(int(pid), bool(avail))
            return _products_df(), r.get("message") or r.get("error", "")

        btn_refresh_prod.click(fn=_products_df, outputs=tbl_products)
        btn_add_prod.click(fn=on_add_product,
                           inputs=[inp_name, inp_desc, inp_cat, inp_price, inp_avail],
                           outputs=[tbl_products, msg_prod])
        btn_remove.click(fn=on_remove_product,
                         inputs=inp_rem_id,
                         outputs=[tbl_products, msg_prod])
        btn_toggle.click(fn=on_toggle,
                         inputs=[inp_tog_id, inp_tog_avail],
                         outputs=[tbl_products, msg_prod])

    # ── Tab 2: Pedidos ───────────────────────────────────────────────────────
    with gr.Tab("Pedidos"):
        with gr.Row():
            # Coluna esquerda: formulários
            with gr.Column(scale=1):

                gr.Markdown("### 1. Criar pedido")
                with gr.Group():
                    inp_cname   = gr.Textbox(label="Nome do cliente")
                    inp_cphone  = gr.Textbox(label="Telefone", placeholder="(11) 99999-0000")
                    inp_pay     = gr.Dropdown(
                        choices=["dinheiro", "cartao_credito", "cartao_debito", "pix"],
                        label="Forma de pagamento", value="pix",
                    )
                    inp_notes   = gr.Textbox(label="Observações", lines=2)
                    btn_create  = gr.Button("Criar pedido", variant="primary")

                gr.Markdown("### 2. Adicionar item")
                with gr.Group():
                    dd_product  = gr.Dropdown(label="Produto", choices=_product_choices())
                    inp_qty     = gr.Number(label="Quantidade", value=1, minimum=1, precision=0)
                    inp_item_note = gr.Textbox(label="Obs do item")
                    btn_add_item = gr.Button("Adicionar item")

                gr.Markdown("### 3. Remover item")
                with gr.Group():
                    inp_rem_prod = gr.Dropdown(label="Produto a remover", choices=_product_choices())
                    btn_rem_item = gr.Button("Remover item", variant="stop")

                gr.Markdown("### 4. Entrega")
                with gr.Group():
                    chk_delivery = gr.Checkbox(label="Delivery")
                    inp_address  = gr.Textbox(label="Endereço")
                    inp_fee      = gr.Number(label="Taxa de entrega (R$)", value=0.0, minimum=0)
                    btn_set_del  = gr.Button("Salvar entrega")

                gr.Markdown("### 5. Pagamento")
                with gr.Group():
                    dd_pay2     = gr.Dropdown(
                        choices=["dinheiro", "cartao_credito", "cartao_debito", "pix"],
                        label="Forma de pagamento",
                    )
                    btn_set_pay = gr.Button("Salvar pagamento")

            # Coluna direita: exibição do pedido e controle de status
            with gr.Column(scale=1):
                gr.Markdown("### Pedido atual")
                order_display = gr.Markdown("_Nenhum pedido em andamento._")

                gr.Markdown("### Controle de status")
                with gr.Row():
                    btn_confirm  = gr.Button("Confirmar",  variant="primary")
                    btn_prep     = gr.Button("Em preparo")
                    btn_ready    = gr.Button("Pronto")
                    btn_deliver  = gr.Button("Entregue",   variant="primary")
                    btn_cancel   = gr.Button("Cancelar",   variant="stop")

                msg_order = gr.Textbox(label="Resultado", interactive=False)

                gr.Markdown("### Histórico de pedidos")
                btn_refresh_orders = gr.Button("Atualizar histórico", variant="secondary")
                tbl_orders = gr.Dataframe(value=_orders_df(), label="Pedidos", interactive=False)

        # --- criar pedido ---
        def on_create(cname, cphone, pay, notes, _oid):
            if not cname.strip():
                return _oid, _fmt_order(_oid), "Informe o nome do cliente."
            r = create_order(
                customer_name=cname,
                customer_phone=cphone or None,
                payment_method=pay or None,
                notes=notes or None,
            )
            if "error" in r:
                return _oid, _fmt_order(_oid), r["error"]
            new_id = r["order_id"]
            choices = _product_choices()
            return new_id, _fmt_order(new_id), r["message"]

        btn_create.click(
            fn=on_create,
            inputs=[inp_cname, inp_cphone, inp_pay, inp_notes, order_id_state],
            outputs=[order_id_state, order_display, msg_order],
        )

        # --- adicionar item ---
        def on_add_item(product_id, qty, note, oid):
            if not oid:
                return _fmt_order(None), "Crie um pedido primeiro."
            if not product_id:
                return _fmt_order(oid), "Selecione um produto."
            r = add_item_to_order(int(oid), int(product_id), int(qty), note or None)
            if "error" in r:
                return _fmt_order(oid), r["error"]
            return _fmt_order(oid), "Item adicionado."

        btn_add_item.click(
            fn=on_add_item,
            inputs=[dd_product, inp_qty, inp_item_note, order_id_state],
            outputs=[order_display, msg_order],
        )

        # --- remover item ---
        def on_rem_item(product_id, oid):
            if not oid:
                return _fmt_order(None), "Crie um pedido primeiro."
            if not product_id:
                return _fmt_order(oid), "Selecione um produto."
            r = remove_item_from_order(int(oid), int(product_id))
            if "error" in r:
                return _fmt_order(oid), r["error"]
            return _fmt_order(oid), "Item removido."

        btn_rem_item.click(
            fn=on_rem_item,
            inputs=[inp_rem_prod, order_id_state],
            outputs=[order_display, msg_order],
        )

        # --- entrega ---
        def on_set_del(is_del, addr, fee, oid):
            if not oid:
                return _fmt_order(None), "Crie um pedido primeiro."
            r = set_delivery(int(oid), bool(is_del), addr or None, float(fee))
            if "error" in r:
                return _fmt_order(oid), r["error"]
            return _fmt_order(oid), "Modo de entrega atualizado."

        btn_set_del.click(
            fn=on_set_del,
            inputs=[chk_delivery, inp_address, inp_fee, order_id_state],
            outputs=[order_display, msg_order],
        )

        # --- pagamento ---
        def on_set_pay(pay, oid):
            if not oid:
                return _fmt_order(None), "Crie um pedido primeiro."
            r = set_payment_method(int(oid), pay)
            if "error" in r:
                return _fmt_order(oid), r["error"]
            return _fmt_order(oid), "Forma de pagamento atualizada."

        btn_set_pay.click(
            fn=on_set_pay,
            inputs=[dd_pay2, order_id_state],
            outputs=[order_display, msg_order],
        )

        # --- transições de status ---
        def _make_status_fn(action_fn):
            def handler(oid):
                if not oid:
                    return _fmt_order(None), "Nenhum pedido ativo."
                r = action_fn(int(oid))
                if "error" in r:
                    return _fmt_order(oid), r["error"]
                return _fmt_order(oid), r.get("message", "")
            return handler

        btn_confirm.click(_make_status_fn(confirm_order),  [order_id_state], [order_display, msg_order])
        btn_prep.click(   _make_status_fn(mark_preparing), [order_id_state], [order_display, msg_order])
        btn_ready.click(  _make_status_fn(mark_ready),     [order_id_state], [order_display, msg_order])
        btn_deliver.click(_make_status_fn(mark_delivered), [order_id_state], [order_display, msg_order])

        def on_cancel(oid):
            if not oid:
                return _fmt_order(None), "Nenhum pedido ativo."
            r = cancel_order(int(oid))
            if "error" in r:
                return _fmt_order(oid), r["error"]
            return _fmt_order(oid), r.get("message", "")

        btn_cancel.click(on_cancel, [order_id_state], [order_display, msg_order])

        # --- histórico ---
        btn_refresh_orders.click(fn=_orders_df, outputs=tbl_orders)



if __name__ == "__main__":
    demo.queue()
    demo.launch(theme=gr.themes.Soft())
