# Comparar métricas entre entornos (local vs producción)

Cuando los **mismos CSV** subidos en local y en producción dan **Valor Real Cuenta**, **P&L No Realizado**, **Dividendos** o **Apalancamiento** distintos, las causas típicas son:

## 1. **P&L No Realizado y Valor Real Cuenta**

- **Origen:** `P&L No Realizado = valor actual de holdings - coste de holdings`.  
  El valor actual usa `current_price` de cada activo (Yahoo Finance).
- **Por qué cambia:** En cada entorno los precios se actualizan en momentos distintos (o no se ha corrido “Actualizar precios” en uno de ellos). Pequeñas diferencias de precio en muchos activos generan la diferencia que ves (ej. 21.694 vs 19.793 EUR).
- **Comprobación:** En el informe del script, revisa `holdings.detail[].current_price` y `holdings.detail[].value_eur` entre entornos.

## 2. **Dividendos**

- **Origen:** Suma de transacciones tipo `DIVIDEND` convertidas a EUR con `convert_to_eur(amount, currency)`.
- **Por qué puede cambiar:**
  - **Import/parser:** Que en un entorno se importen más o menos líneas como dividendo (duplicados, filas que en un sitio se clasifican como dividendo y en otro no).
  - **Conversión a EUR:** Diferente tasa de cambio (API de tasas vs fallback, o cache distinto).
- **Comprobación:** Comparar `transactions.dividends.count`, `transactions.dividends.total_eur` y `transactions.dividends_detail` (mismo número de filas y mismos `amount`/`currency`/`amount_eur` por fila).

## 3. **Apalancamiento**

- **Fórmula:** `Apalancamiento = total_cost_eur - (Depósitos - Retiradas + P&L Realizado + Dividendos - Comisiones)`.  
  Depende de coste de posiciones, depósitos, retiradas, P&L realizado, dividendos y comisiones.
- **Por qué puede cambiar:** Cualquier diferencia en dividendos o comisiones (o en costes si el import difiere) cambia el “dinero del usuario” y por tanto el apalancamiento.

## 4. **Depósitos, Retiradas, P&L Realizado, Comisiones**

- Si estos **coinciden** entre entornos y solo cambian P&L No Realizado, Dividendos o Apalancamiento, la causa está en:
  - precios actuales (P&L no realizado), y/o
  - dividendos (suma o conversión), y/o
  - derivado de lo anterior (Valor Real Cuenta y Apalancamiento).

---

## Uso del script `compare_metrics_envs.py`

**Requisito:** Desplegar el script en producción (incluido en el repo y desplegado con el resto del código).

### En local (desde la raíz del proyecto)

```bash
# Resumen rápido (solo métricas clave)
FLASK_APP=run.py python docs/scripts/compare_metrics_envs.py amieva91 --summary

# Informe completo (para diff detallado)
FLASK_APP=run.py python docs/scripts/compare_metrics_envs.py amieva91 > local.json
```

### En producción (por SSH)

```bash
./scripts/connect-gcp.sh 'cd /var/www/followup && sudo -u followup bash -c "source venv/bin/activate && FLASK_APP=run.py python docs/scripts/compare_metrics_envs.py amieva91 --summary"'
# o informe completo y guardar en servidor:
# ... python docs/scripts/compare_metrics_envs.py amieva91 > /tmp/prod.json
# y luego descargar /tmp/prod.json con scp o gcloud scp
```

### Comparar

- **Resumen:** Comparar a mano los números de `--summary` entre local y producción.
- **Completo:** `diff local.json prod.json` (o un comparador de JSON) para ver diferencias en transacciones (dividendos, fees) y en cada holding (`current_price`, `value_eur`, `pl_unrealized_eur`).

Con eso puedes ver si la diferencia viene de:
- **Precios:** distinto `current_price` (o `value_eur` / `pl_unrealized_eur`) en los mismos activos.
- **Dividendos:** distinto `count` o `total_eur` o filas en `dividends_detail`.
- **Tasas:** distinto `exchange_rates` en el JSON (entorno usando API vs fallback).

---

## Prueba limpiando caches (Dietz / valor a 31/12)

Si la divergencia aparece en **Rentabilidades año a año** o en el **valor del portfolio a 31/12/2023** (u otra fecha), puede deberse a que cada entorno tiene en memoria tasas de cambio distintas (cache de 24 h). Para probar:

1. **Ejecutar el script que limpia caches y recalcula** (en local y en producción, si puede ser a la vez):
   ```bash
   FLASK_APP=run.py python docs/scripts/clear_caches_and_diagnose.py amieva91
   ```
   Ese script: vacía el cache de tasas en *este* proceso, fuerza una llamada a la API de tasas, invalida el cache de métricas del usuario y ejecuta el diagnóstico Dietz por año. Compara el JSON (sobre todo `yearly_returns[].start_value`, `end_value`, `absolute_gain`) entre ambos entornos.

2. **Si quieres que el dashboard web use tasas recién cargadas** (mismo proceso que sirve las peticiones):
   - **Reiniciar el servicio:** `sudo systemctl restart followup.service` (o equivalente).
   - **O** desde `flask shell` en ese mismo servidor:  
     `from app.services.currency_service import clear_rates_cache; clear_rates_cache()`  
     La siguiente petición que use `convert_to_eur` cargará tasas desde la API.

Si tras limpiar caches y recalcular **local y producción siguen dando valores distintos**, la causa no es solo “cache viejo vs nuevo” (p. ej. la API puede devolver tasas ligeramente distintas en cada llamada). Si **pasan a coincidir**, confirma que el cache (y el momento de las tasas) influye en la diferencia.

---

## Comparar currency de activos (mismo símbolo, distinta moneda)

Si **Recalcular** (holdings + cache) no elimina la diferencia, puede que algún activo tenga `Asset.currency` distinta en un entorno que en el otro (ej. SLYG en BGN en local y EUR en prod).

### 1. Exportar en cada entorno

**Local:**
```bash
FLASK_APP=run.py python docs/scripts/export_assets_currency.py amieva91 > docs/scripts/local_assets.json
```

**Producción** (por SSH; guardar salida como `docs/scripts/prod_assets.json`):
```bash
cd /var/www/followup && sudo -u followup bash -c 'source venv/bin/activate && FLASK_APP=run.py python docs/scripts/export_assets_currency.py amieva91'
```

### 2. Comparar

```bash
python docs/scripts/compare_assets_currency.py docs/scripts/local_assets.json docs/scripts/prod_assets.json
```

Lista símbolos con **distinta currency entre entornos**. Corrige el activo en el entorno incorrecto, pulsa **Recalcular** ahí y recarga.
