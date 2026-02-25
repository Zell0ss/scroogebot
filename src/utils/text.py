import unicodedata


def normalize_basket_name(name: str) -> str:
    """Accent-strip + lowercase for case/accent-insensitive basket lookups.

    Examples:
        'Canción' → 'cancion'
        'Lab_AVANZADO' → 'lab_avanzado'
        '  Eco  ' → 'eco'
    """
    nfkd = unicodedata.normalize('NFKD', name.strip())
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()
