
import pytest
from fastapi.testclient import TestClient
from app import app, DB_NAME
import os
import sqlite3

# Użyj test_app.py do testowania app.py

client = TestClient(app)

@pytest.fixture(scope="function")
def cleanup_db():
    """Używany do czyszczenia bazy przed każdym testem."""
    # Upewnij się, że brama do testowania jest czysta
    if os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        conn.execute("DELETE FROM products")
        conn.commit()
        conn.close()
    yield
    # Po teście, sprzątaj, jeśli to konieczne
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

@pytest.fixture(scope="module")
def fresh_db():
    """Tworzy świeżą bazę danych z pełnym zestawem danych."""
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    
    # Ponowne zainicjowanie bazy z produkcjnego kodu (aby mieć stałe dane)
    # W realnym świecie, zaimportowalibyśmy funkcję inicjalizacji, ale tutaj zrobimy to ręcznie.
    
    # Tworzenie tabeli
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL)")
    conn.commit()

    # Dodawanie produktów
    products_data = [
        ("Laptop X1", 1200.00, 10),
        ("Mouse Pro", 25.50, 50),
        ("Keyboard Mech", 89.99, 20),
        ("Webcam 4K", 55.00, 5),
        ("Monitor Ultra", 350.00, 3)
    ]
    cursor.executemany("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", products_data)
    conn.commit()
    conn.close()

    return True

def test_01_get_all_products_success(fresh_db):
    """Sprawdza, czy wszystkie produkty są zwracane."""
    response = client.get("/products")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    # Sprawdź konkretny produkt
    assert any(item['name'] == 'Laptop X1' and item['price'] == 1200.00 for item in data)

def test_02_get_specific_product_success(fresh_db):
    """Sprawdza pobranie konkretnego produktu (ID=1)."""
    response = client.get("/products/1")
    assert response.status_code == 200
    data = response.json()
    assert data['name'] == 'Laptop X1'
    assert data['stock'] == 10

def test_02_get_specific_product_not_found(fresh_db):
    """Sprawdza błąd 404 dla nieistniejącego ID."""
    response = client.get("/products/999")
    assert response.status_code == 404
    assert response.json()['detail'] == "Produkt nie został znaleziony"

def test_03_add_new_product_success():
    """Sprawdza dodanie nowego produktu (POST /products)."""
    # Używamy cleanup_db, aby zapewnić, że zaczynamy z pustą tabelą
    response = client.post("/products", json={"name": "New Gadget", "price": 10.0, "stock": 100})
    assert response.status_code == 201
    data = response.json()
    assert data['name'] == "New Gadget"
    assert data['stock'] == 100
    # Dodatkowy test: sprawdzamy, czy faktycznie został dodany i czy ID jest > 0
    
    # Aby to sprawdzić, musimy pobrać wszystkie produkty po dodaniu
    response_all = client.get("/products")
    assert len(response_all.json()) == 6 # POPRAWIONO: powinieneś mieć 5 startowych + 1 dodany
    # Sprawdź, czy dodany produkt faktycznie się znalazł
    added_product = next((item for item in response_all.json() if item['name'] == 'New Gadget'), None)
    assert added_product is not None
    # W praktyce po dodaniu, bylibyśmy musieli znaleźć ten nowy produkt
    
def test_04_buy_product_success():
    """Sprawdza pomyślny zakup (zmniejszenie stock)."""
    # Używamy fresh_db, aby mieć produkt z zapasem (ID=2, Mouse Pro, Stock=50)
    response = client.post("/products/2/buy")
    assert response.status_code == 200
    assert "Pozostało 49 sztuk" in response.json()['message']
    
    # Dodatkowy test: sprawdzamy, czy stock faktycznie się zmienił
    response_check = client.get("/products/2")
    assert response_check.json()['stock'] == 49

def test_04_buy_product_not_found(fresh_db):
    """Sprawdza błąd 404 dla nieistniejącego produktu przy zakupie."""
    response = client.post("/products/999/buy")
    assert response.status_code == 404
    assert response.json()['detail'] == "Produkt nie został znaleziony"

def test_04_buy_product_stock_zero(fresh_db):
    """
    Symuluje sytuację, gdy produkt ma stock = 0.
    Musimy najpierw zmodyfikować produkt, żeby jego stock stał się 0.
    """
    # 1. Zmniejsz stock produktu 5 (Monitor Ultra, Stock=3) do 0
    for _ in range(3):
        client.post("/products/5/buy")
    
    # 2. Sprawdź, czy stock jest faktycznie 0
    response_check = client.get("/products/5")
    assert response_check.json()['stock'] == 0
    
    # 3. Spróbuj kupić raz jeszcze
    response = client.post("/products/5/buy")
    assert response.status_code == 409
    assert response.json()['detail'] == "Produkt jest niedostępny (stock równy 0)"
