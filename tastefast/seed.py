"""Populate the database with sample menu items."""

from .db import get_conn, init_db

PRODUCTS = [
    # Lanches
    ("X-Burguer",        "Hambúrguer, queijo, alface e tomate",                          "lanche",    18.90),
    ("X-Bacon",          "Hambúrguer, queijo, bacon crocante, alface e tomate",           "lanche",    24.90),
    ("X-Tudo",           "Hambúrguer duplo, queijo, bacon, ovo, alface e tomate",         "lanche",    32.90),
    ("Frango Crispy",    "Filé de frango empanado, queijo, alface e maionese",            "lanche",    22.90),
    ("Misto Quente",     "Pão de forma, presunto e queijo grelhado",                      "lanche",    10.90),
    ("Bauru",            "Pão francês, rosbife, queijo derretido e tomate",               "lanche",    19.90),

    # Bebidas
    ("Coca-Cola 350ml",  "Lata gelada",                                                   "bebida",     6.00),
    ("Suco Natural",     "Laranja, limão ou maracujá — 400ml",                            "bebida",    10.00),
    ("Vitamina",         "Vitamina de banana, morango ou abacate — 400ml",                "bebida",    12.00),
    ("Água Mineral",     "500ml com ou sem gás",                                          "bebida",     4.00),
    ("Milk-shake",       "Chocolate, morango ou baunilha — 400ml",                        "bebida",    16.00),

    # Porções
    ("Batata Frita P",   "Porção pequena de batata frita crocante",                       "porcao",    14.00),
    ("Batata Frita G",   "Porção grande de batata frita crocante",                        "porcao",    22.00),
    ("Onion Rings",      "Anéis de cebola empanados — 10 unidades",                       "porcao",    18.00),
    ("Nuggets",          "12 unidades de frango empanado",                                "porcao",    20.00),
    ("Calabresa Acebolada", "Porção de calabresa grelhada com cebola — 300g",             "porcao",    28.00),

    # Sobremesas
    ("Brownie",          "Brownie de chocolate com sorvete de creme",                     "sobremesa", 15.00),
    ("Açaí 300ml",       "Açaí cremoso com granola e banana",                             "sobremesa", 18.00),
    ("Sorvete",          "2 bolas — chocolate, morango ou creme",                         "sobremesa",  9.00),

    # Combos
    ("Combo Clássico",   "X-Burguer + Batata Frita P + Coca-Cola 350ml",                  "combo",    34.90),
    ("Combo Premium",    "X-Bacon + Batata Frita G + Suco Natural",                       "combo",    44.90),
    ("Combo Frango",     "Frango Crispy + Batata Frita P + Água Mineral",                 "combo",    32.90),
]


def seed():
    init_db()
    with get_conn() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if existing:
            print(f"Cardápio já possui {existing} item(s). Seed ignorado.")
            return
        conn.executemany(
            "INSERT INTO products (name, description, category, price) VALUES (?, ?, ?, ?)",
            PRODUCTS,
        )
        print(f"{len(PRODUCTS)} produtos inseridos com sucesso.")


if __name__ == "__main__":
    seed()
