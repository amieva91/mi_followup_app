"""
Campos de formulario que aceptan coma decimal (es-ES) además de punto.

WTForms FloatField hace float(val) y solo acepta '.' como separador decimal.
"""
from __future__ import annotations

from wtforms import FloatField


def parse_float_eu(value) -> float:
    """
    Convierte texto con coma decimal o formato miles español (1.234,56) a float.
    También acepta punto como en Python (1.5).
    """
    if value is None:
        raise ValueError("empty")
    s = str(value).strip().replace(" ", "").replace("\u00a0", "")
    if not s or s in ("--", "—"):
        raise ValueError("empty")
    if "," in s and "." in s:
        if s.rindex(",") > s.rindex("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


class EuFloatField(FloatField):
    """FloatField que acepta '16,5' o '1.234,56' además de '16.5'."""

    def process_formdata(self, valuelist):
        if not valuelist:
            return
        try:
            self.data = parse_float_eu(valuelist[0])
        except (ValueError, TypeError) as exc:
            self.data = None
            raise ValueError(self.gettext("Not a valid float value.")) from exc
