import unicodedata


def normalize_basket_name(name: str) -> str:
    """Accent-strip + lowercase + collapse whitespace for basket lookups.

    Examples:
        'Canción' → 'cancion'
        'Lab_AVANZADO' → 'lab_avanzado'
        '  Eco  ' → 'eco'
        'Renta  Fija' → 'renta fija'
    """
    nfkd = unicodedata.normalize('NFKD', name.strip())
    stripped = ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()
    return ' '.join(stripped.split())
