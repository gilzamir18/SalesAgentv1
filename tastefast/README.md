Arquivo	Responsabilidade
db.py	Conexão SQLite, schema e triggers
tools.py	Todas as funções/tools do sistema
seed.py	Cardápio de exemplo com 22 itens
init.py	Exporta tudo pelo pacote
Tabelas:

products — cardápio (categorias: lanche, bebida, porcao, sobremesa, combo, outro)
orders — pedidos com status, delivery, forma de pagamento, taxa, notas
order_items — itens com preço histórico (imune a mudanças no cardápio)
Tools disponíveis:

Cardápio: list_products, get_product
Pedidos: create_order, get_order, list_orders, add_item_to_order, remove_item_from_order
Configuração: set_payment_method, set_delivery
Fluxo: confirm_order → mark_preparing → mark_ready → mark_delivered
cancel_order (funciona em qualquer status antes de delivered)
