
import sqlite3
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import os

# --- Konfiguracja ---
DB_NAME = "shop.db"
app = FastAPI(title="Internet Shop API")

# --- Modele Danych ---
class ProductBase(BaseModel):
    name: str
    price: float
    stock: int

class ProductCreate(ProductBase):
    pass

class ProductInDB(ProductBase):
    id: int

    # Metoda konwersji z surowych danych SQLite
    @staticmethod
    def from_sqlite(p: sqlite3.Row) -> 'ProductInDB':
        return ProductInDB(id=p['id'], name=p['name'], price=p['price'], stock=p['stock'])

    # Metoda do szybkiego ucieczki z Pydantic w celu serializacji
    def model_dump(self):
        return super().model_dump()

# --- Funkcje Bazy Danych ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    # Ustawienie row_factory pozwala na dostęp do kolumn po nazwie (np. row['name'])
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    """Tworzy tabelę i dodaje dane początkowe, jeśli baza jest pusta."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Tworzenie tabeli products
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    """)
    conn.commit()

    # 2. Sprawdzenie, czy tabela jest pusta
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print(">>> Baza danych jest pusta. Dodawanie produktów początkowych...")
        
        # 3. Dodanie 5 produktów początkowych
        initial_products = [
            ("Laptop X1", 1200.00, 10),
            ("Mouse Pro", 25.50, 50),
            ("Keyboard Mech", 89.99, 20),
            ("Webcam 4K", 55.00, 5),
            ("Monitor Ultra", 350.00, 3)
        ]
        
        try:
            cursor.executemany(
                "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
                initial_products
            )
            conn.commit()
            print(">>> Produkty początkowe zostały dodane.")
        except sqlite3.Error as e:
            print(f"Błąd podczas wstawiania danych: {e}")
    else:
        print(f">>> Baza danych zawiera {count} produktów. Brak konieczności inicjalizacji.")
        
    conn.close()

# Wywołanie inicjalizacji podczas załadowania aplikacji
initialize_db()


# --- Endpoints API ---

@app.get("/products", response_model=list[ProductInDB])
def list_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Wybieramy wszystkie wymagane kolumny
    cursor.execute("SELECT id, name, price, stock FROM products")
    products = cursor.fetchall()
    conn.close()
    
    # Mapowanie wyników
    return [ProductInDB.from_sqlite(p) for p in products]


@app.get("/products/{product_id}", response_model=ProductInDB)
def get_product(product_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, price, stock FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    
    if product is None:
        raise HTTPException(status_code=404, detail="Produkt nie został znaleziony")
    
    return ProductInDB.from_sqlite(product)


@app.post("/products", response_model=ProductInDB, status_code=status.HTTP_201_CREATED)
def add_product(product_data: ProductCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
        (product_data.name, product_data.price, product_data.stock)
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Odczyt i zwrócenie pełnego obiektu
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products WHERE id = ?", (new_id,))
    new_product = cursor.fetchone()
    conn.close()

    return ProductInDB.from_sqlite(new_product)


@app.post("/products/{product_id}/buy", status_code=None)
def buy_product(product_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Odczyt stocku
    cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()

    if product is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Produkt nie został znaleziony")

    current_stock = product[0]

    # 2. Sprawdzenie dostępności
    if current_stock <= 0:
        conn.close()
        raise HTTPException(status_code=409, detail="Produkt jest niedostępny (stock równy 0)")
    
    # 3. Zmniejszenie stock
    new_stock = current_stock - 1
    cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
    
    if cursor.rowcount == 0:
         # To jest bardzo mało prawdopodobne, ale zabezpieczenie
        conn.close()
        raise HTTPException(status_code=500, detail="Błąd aktualizacji produktu")

    conn.commit()
    conn.close()

    # Opis sukcesu
    return {"message": f"Kupno zakończone pomyślnie. Pozostało {new_stock} sztuk."}

# Warto dodać kod do uruchamiania w tle, choć w testach to nie jest potrzebne.
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
