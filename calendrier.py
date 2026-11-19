"""Fonctions calendaires."""


def est_bissextile(annee: int) -> bool:
    """Renvoie True si l'année est bissextile (calendrier grégorien)."""
    return annee % 4 == 0 and (annee % 100 != 0)
