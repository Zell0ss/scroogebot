from src.utils.text import normalize_basket_name

def test_accents():
    assert normalize_basket_name("Canción") == "cancion"

def test_uppercase():
    assert normalize_basket_name("Lab_AVANZADO") == "lab_avanzado"

def test_mixed():
    assert normalize_basket_name("Cesta Agresiva") == "cesta agresiva"

def test_strips_spaces():
    assert normalize_basket_name("  Eco  ") == "eco"

def test_already_normal():
    assert normalize_basket_name("cartera") == "cartera"

def test_enie():
    assert normalize_basket_name("España") == "espana"

def test_umlaut():
    assert normalize_basket_name("Über") == "uber"

def test_internal_whitespace():
    assert normalize_basket_name("Renta  Fija") == "renta fija"
