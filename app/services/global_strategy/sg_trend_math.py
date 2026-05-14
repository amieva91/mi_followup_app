"""Tendencia de SG vs media móvil corta (sin dependencias de app)."""


def mean5_sg_falling(
    current_sg: float,
    last_five_sg_newest_first: list[float],
    *,
    threshold: float = 0.3,
) -> bool:
    """
    Score bajando (§5.2): la media de los últimos 5 SG supera al actual en más de ``threshold``.
    ``last_five_sg_newest_first`` incluye el valor más reciente en [0].
    """
    if len(last_five_sg_newest_first) < 5:
        return False
    m = sum(last_five_sg_newest_first[:5]) / 5.0
    return (m - float(current_sg)) > float(threshold)
