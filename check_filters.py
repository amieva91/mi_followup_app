#!/usr/bin/env python3
from app import create_app

app = create_app('development')

print("Verificando filtros Jinja...")
print("\nFiltros personalizados buscados:")
print("- number_eu:", 'number_eu' in app.jinja_env.filters)
print("- decimal_eu:", 'decimal_eu' in app.jinja_env.filters)

if 'number_eu' in app.jinja_env.filters:
    print("\nTest number_eu:")
    print("  200.0000 ->", app.jinja_env.filters['number_eu'](200.0000))
    print("  4000.0 ->", app.jinja_env.filters['number_eu'](4000.0))
else:
    print("\n❌ PROBLEMA: number_eu NO está registrado")

if 'decimal_eu' in app.jinja_env.filters:
    print("\nTest decimal_eu:")
    print("  8.66 ->", app.jinja_env.filters['decimal_eu'](8.66, 2))
    print("  1732.00 ->", app.jinja_env.filters['decimal_eu'](1732.00, 2))
else:
    print("\n❌ PROBLEMA: decimal_eu NO está registrado")

