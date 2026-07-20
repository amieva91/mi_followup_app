# Plan de ejecución — migración en VM prod (detalle micro-pasos)

**Fecha:** 17 julio 2026 (F0 cerrado 19 jul 2026)  
**Estado:** **F0–F1 HECHO** · **F2 en curso** (F2.01 `[x]`; siguiente **F2.02**) · IP **`34.170.20.250`** · Flask congelado · app Auðr en IP  
**Playbook padre:** [MIGRATE_ON_PROD_VM.md](MIGRATE_ON_PROD_VM.md)  
**Producto:** [BRIEF_FOLLOWUP_DEVELOPER.md](BRIEF_FOLLOWUP_DEVELOPER.md)  
**Transform:** [TRANSFORM_FOLLOWUP_TO_AUDR.md](TRANSFORM_FOLLOWUP_TO_AUDR.md)  
**Bootstrap / forma de trabajo:** [BOOTSTRAP_STATUS.md](BOOTSTRAP_STATUS.md), [EDITOR_GUIDE_CURSOR.md](EDITOR_GUIDE_CURSOR.md), [ARQUITECTURA_PROPUESTA.md](ARQUITECTURA_PROPUESTA.md)

---

## Protocolo de ejecución (acordado con el usuario)

1. **Checklist viva:** cada micro-paso tiene `- [ ]` / `- [x]`. Al completar un paso, el agente lo marca `[x]` en este doc (y re-sincroniza la copia en FollowUp `docs/audr_migration/` si aplica).
2. **Antes de iniciar cada paso** (y **antes de pedir OK para ejecutarlo**), el agente explica en chat:
   - **De qué se trata** — objetivo del paso en una frase.
   - **Qué se modifica** — ficheros, VM, DNS, servicios, nada (si es solo verificación).
   - **Qué funcionalidad se añade** — o “ninguna (blindaje / infra / prep)” si no hay feature de producto.
   - **Ventaja** — por qué importa / qué riesgo evita.
   - **Qué notarás en la web** — cambio visible o “ninguno”.
3. **No ejecutar** el paso hasta que el usuario lo autorice (salvo que diga “sigue con el bloque F0.xx–yy”).
4. Tras ejecutar: marcar checklist + resultado breve (OK / fallo / diferido).

**Override producto (19 jul):** ver [BRIEF_FOLLOWUP_DEVELOPER.md](BRIEF_FOLLOWUP_DEVELOPER.md) § Overrides activos — (A) import CSV **con OpenFIGI** como FollowUp; (B) corporate actions/delistings **como FollowUp** (`asset_delistings` + reconciliación), no modelo Auðr redesigned.

---

## 0. Decisiones cerradas (usuario)

| Tema | Decisión | Fuente |
|------|----------|--------|
| Destino de código | Solo repo **Auðr** (Opción A) | 17 jul |
| FollowUp Flask | Congelado; sin features; downtime indefinido OK | 17 jul |
| Dónde se trabaja | **Misma VM GCP** (`followup`); `/var/www/audr` vs `/var/www/followup` | playbook |
| Fundación | **No reinventar** — respetar T3–T4b ya en repo Auðr | 17 jul |
| Siguiente dominio producto | **T5** tras sembrar + validar T4/T4b en VM | brief + bootstrap |
| DNS `auðr.com` | **Más tarde** (T5/T6+ o cutover); hasta entonces IP + nginx mantenimiento; GoDaddy placeholder | 17 jul |
| Apagar FollowUp | **Sí, al cerrar F0** (tras backup + restore probado) | 17 jul |
| Machine type | **`e2-medium` antes de Compose** | 17 jul |
| Disco VM | Ampliar a **~40 GB** al pasar a e2-medium | 17 jul |
| Backups off-VM | **Mac + GCS** `gs://audr-backups-amieva91` (artefactos prod: tarball, db, uploads) | 17 jul |
| Repo GitHub Auðr | **`amieva91/audr` privado** + commits lógicos + push; luego clone en VM | 17 jul |
| Primer push Auðr | Varios commits: docs+cursor → contracts → backend → frontend → docker | 17 jul |
| CI (Actions) | **Después** del seed/smoke en VM; no en el primer push | 17 jul |
| Usuario VM / pruebas | **No crear demo ahora.** Usar usuarios heredados de FollowUp tras espejo/migración; usuarios nuevos solo si hace falta más adelante | 17 jul |
| Cifrado backups `.env` | **`age` opcional de higiene** (no afecta runtime). Identity **solo en Mac** (Keychain/1Password). No identity en GCS junto a `.env.age`. Si se pierde Mac → regenerar secretos. **No bloquea F0/F1** | 17 jul |
| Bucket GCS región | **`us-central1`** (misma que la VM) | 17 jul |
| Espejo Mac contenido | Todo lo **no regenerable** (ver §3e); **sin** `venv/`, `__pycache__` | 17 jul |
| Nginx al apagar Flask | Página **mantenimiento en la IP** | 17 jul |
| Gemini / informes | DROP en Auðr; no portar | brief |
| Commits | **Solo si el usuario lo pide** | bootstrap / EDITOR_GUIDE |
| IP pública tras reboot | **Efímera** (sin IP estática de pago). Tras stop/start/reboot: actualizar **GoDaddy A** + §9 | 17 jul |
| Cifrado `.env` | **`age`** (preferido) o `gpg`; en git solo `.env.example`; secreto `.env.age` en Mac/GCS | 17 jul |
| Espejo Mac | Código + BD + uploads (+ configs); **sin** `venv/` de prod | 17 jul |
| Página mantenimiento IP | Texto AUÐR / migración (ver §3c) | 17 jul |
| Bucket GCS | Mismo proyecto VM; `gs://audr-backups-amieva91` | 17 jul |
| Multi-root Cursor | `audr.code-workspace` en repo Auðr (Auðr RW + FollowUp RO) | 17 jul |

---

## 0b. Objetivo de cierre de proyecto — “bootstrap vivo”

Al **finalizar** la migración (cutover estable), el workspace Auðr debe cumplir el bootstrap como **sistema operativo del equipo**, no solo docs:

### Árbol (objetivo [ARQUITECTURA_PROPUESTA](ARQUITECTURA_PROPUESTA.md))

```
Auðr/
├── contracts/          # OpenAPI + schemas SSE
├── backend/apps/       # core, wealth, cashflow, banking, liabilities,
│                       # investments, alternatives, property, strategy,
│                       # catalog, alerts, reports, live, admin_ops
├── backend/config/
├── frontend/src/       # app, components, styles (+ Storybook)
├── docker/             # compose local + prod
├── docs/
└── .cursor/rules/
```

Stack: Django 5.2 + DRF + Next 16 + PG 17 + Redis + Celery; SSE desde día 1; monolito modular.

### Documentación mínima siempre navegable

| Pieza | Ruta |
|-------|------|
| Índice arquitectura | `docs/ARQUITECTURA_PROPUESTA.md` |
| Stack | `docs/TECH_STACK.md` |
| Planning | `docs/PLANNING_MASTER.md` |
| Transform | `docs/TRANSFORM_*.md` + ADR-016 |
| Estado bootstrap | `docs/BOOTSTRAP_STATUS.md` |
| Guía Cursor | `docs/EDITOR_GUIDE_CURSOR.md` |
| ADRs | `docs/adr/` |
| Prompts proceso | `docs/prompts/audr-*.md` |
| Este plan VM | `docs/PLAN_EXECUTE_PROD_VM.md` |

### Cursor rules (8)

| Rule | Rol |
|------|-----|
| `audr-master.mdc` | Siempre (identidad, stack, fases T*, reglas duras) |
| `audr-frontend.mdc` | Frontend |
| `audr-backend.mdc` | Backend |
| `audr-database.mdc` | Models/migrations |
| `audr-testing.mdc` | Tests |
| `audr-design-system.mdc` | UI / dual-surface |
| `audr-documentation.mdc` | Docs |
| `audr-security.mdc` | Seguridad |

### Forma de trabajar (día a día)

1. Abrir **workspace Auðr** (no FollowUp para features).
2. Indicar **fase T\*** (o vertical T5.x).
3. Agente usa `audr-master` + rule de dominio.
4. Features nuevas: prompt `audr-new-feature.md`.
5. Fin de sesión: `audr-session-end.md`.
6. **Commits solo si el usuario lo pide.**
7. Review opcional: `audr-change-review.md`.

### Criterio “bootstrap cumplido” (checklist de fin de proyecto)

- [ ] Árbol de carpetas = objetivo (todas las `backend/apps/*` del monolito existen o están documentadas como deferred post-MVP con ADR).
- [ ] `contracts/` al día con OpenAPI + SSE schemas usados por frontend.
- [ ] 8 rules `audr-*.mdc` presentes y alineadas con ADRs.
- [ ] Docs índice + TRANSFORM + BOOTSTRAP_STATUS actualizados (sin FollowUp como destino de features).
- [ ] Sin Flask/Jinja en código activo; `/var/www/followup` archivado o borrado tras 2º backup.
- [ ] DNS `auðr.com` → VM; HTTPS; SSE sin buffering.
- [ ] Un desarrollador nuevo clona Auðr y entiende el sistema solo con `docs/` + rules.

---

## 0c. Gap bootstrap vs árbol actual (Mac, 17 jul)

| App / pieza objetivo | ¿Existe hoy? | Notas |
|----------------------|--------------|--------|
| `core` | Sí | |
| `wealth` | Sí | |
| `investments` | Sí | T4 |
| `catalog` | Sí | T4 |
| `live` | Sí | T3 |
| `admin_ops` | Sí | |
| `cashflow` | **No** | T5 |
| `banking` | **No** | T5 |
| `liabilities` | **No** | T5 |
| `alternatives` | **No** | T7 |
| `property` | **No** | T7 |
| `strategy` | **No** | T7 |
| `alerts` | **No** | T8 |
| `reports` | **No** | T8 |
| `contracts/` | Sí | openapi + schemas |
| `.cursor/rules/` (8) | Sí | |
| `docs/prompts/` | Sí | |
| `docker/` | Sí | |
| Git commits + remote | **No** | Bloqueante P1 |

---

## 1. Infra actual (snapshot 19 jul — post F1.02)

| Recurso | Valor |
|---------|--------|
| VM | `followup` / `us-central1-b` |
| Estado | **RUNNING** |
| Tipo máquina **ahora** | **`e2-medium`** |
| Disco | **40 GB** (filesystem `/` ~38G, libres ~**28G**) |
| IP pública (puede cambiar) | **`34.170.20.250`** (20 jul; antes F1.19: `34.61.176.75`; F1.02: `35.226.138.80`) |
| App Flask | `/var/www/followup` (parado) |
| Uploads Flask | ~ vacío (`.gitkeep`) |
| Dominio definitivo | `auðr.com` / `xn--aur-4ma.com` (GoDaddy; cutover tarde) |

---

## 2. Estado backup vs “Backup completo”

| Paso playbook | Estado | Notas |
|---------------|--------|-------|
| BD SQLite + integrity | **HECHO** | Mac + VM; SHA `4c4b1463…` |
| Snapshot disco GCP | **HECHO** | `followup-finaloldversion-20260717-102444` |
| Tag código FollowUp | **HECHO** | `finaloldversion` @ `e20b415` |
| Uploads | **DE FACTO OK** | Vacío; cubierto por snapshot |
| Tarball código | **HECHO** | `/var/www/followup-backups/…110247.tgz` SHA `1b8ba07f…` |
| `.env` cifrado off-VM | **HECHO** | `env_finaloldversion_20260719.age` (Mac+VM); identity solo Mac |
| Copia Mac | **HECHO** (parcial→completo F0.07) | BD + tarball + `.age` + espejo F0.04d |
| Copia **GCS** | **HECHO** | `gs://audr-backups-amieva91/finaloldversion/20260719/` (~306 MiB) |
| `RESTORE.md` | **HECHO** | `~/backups/followup_finaloldversion/RESTORE.md` (F0.10 → VM+GCS) |
| Restore smoke | **HECHO** | F0.11 Mac/GCS/VM integrity ok |
| Apagar FollowUp | **HECHO** | F0.13 inactive + F0.14 mantenimiento |

---

## 3. Valoración del modo de trabajo en VM

**Aprobado:** misma VM, dos árboles, downtime OK, pasos pequeños, probar Auðr en IP real, Flask congelado.

**Condiciones cerradas:** e2-medium + disco ~40 GB; GCS + Mac; apagar FollowUp al cerrar F0; DNS tarde; `amieva91/audr`; CI post-seed; **sin usuario demo** (usuarios heredados más adelante); age opcional.

---

## 3b. Workspace Mac + orden operativo (antes de desarrollar Auðr)

### Objetivo espejo FollowUp en Mac

Además del backup de blindaje (VM/Mac/GCS), tener una **copia idéntica** de prod en el Mac para portar en solo lectura:

| Pieza | Destino Mac |
|-------|-------------|
| Código | `~/Applications/mi_followup_app` (sync desde prod / tag `finaloldversion` + untracked si aplica) |
| BD | `instance/followup.db` (mismo contenido que prod en el momento del sync) |
| Uploads / datos usuario | espejo de `/var/www/followup/uploads` (+ otros paths de datos si existen) |

Luego: **backup local restaurable** de ese espejo (tarball o carpeta fechada + `RESTORE_LOCAL.md` corto).

### Roles Cursor (multi-root)

| Root | Rol |
|------|-----|
| `~/Projects/Auðr` | **Escritura** — único sitio de reforma |
| `~/Applications/mi_followup_app` | **Solo lectura** — referencia para portar; **cero features Flask** |

### Orden operativo resumido (ejecución)

```
1. Sync prod → Mac FollowUp (código + BD + uploads) = espejo del momento
2. Backup local de ese espejo (restore fácil en Mac)
3. Cerrar F0: tarball prod + RESTORE.md + Mac + GCS gs://audr-backups-amieva91
4. Apagar FollowUp systemd; nginx mantenimiento en IP
5. GitHub amieva91/audr + commits lógicos + push + tag
6. VM: e2-medium + disco ~40 GB (anotar IP; si cambió → GoDaddy A)
7. git clone → /var/www/audr → Compose → smoke health/SSE (auth con user heredado cuando exista)
8. Desarrollar en Auðr; FollowUp Mac RO para port
```

### Regla IP / GoDaddy (obligatoria en cada ciclo de máquina)

Cada vez que se **apague, encienda o reinicie** la VM GCP y cambie la IP pública NAT:

1. `gcloud compute instances describe followup --zone=us-central1-b --format='get(networkInterfaces[0].accessConfigs[0].natIP)'`
2. Actualizar registro **A** en GoDaddy (cuando el dominio ya apunte a la VM; durante placeholder Website Builder, anotar IP en este doc §9 y usar IP directa).
3. Actualizar §9 de este plan + cualquier `RESTORE.md` / notas de acceso.
4. Si hay certbot/HTTPS ligado a IP/host, renovar/revalidar tras el cambio.

**No asumir IP estable** — **no** reservar IP estática (evitar coste). Checklist obligatoria tras cada ciclo de máquina:

```
[ ] gcloud … describe → anotar NAT_IP
[ ] Si auðr.com ya apunta a la VM: GoDaddy DNS → registro A @ = NAT_IP (TTL bajo si se puede)
[ ] Actualizar §9 de PLAN_EXECUTE_PROD_VM.md
[ ] Actualizar RESTORE.md / notas de acceso
[ ] Probar http://NAT_IP/ (mantenimiento o Auðr)
[ ] Si HTTPS/certbot activo: revalidar
```

Mientras auðr.com esté en **placeholder GoDaddy**: no hace falta tocar DNS del dominio; usar **IP directa** y mantener §9 al día.

---

## 3c. Página de mantenimiento (nginx en la IP)

Contenido acordado:

```
AUÐR
Estamos migrando el servicio. Vuelve pronto.
(mantenimiento / transformación en curso)
```

Estilo: minimal, oscuro alineado a portada storm si es barato; sin CTAs ni login. Sustituir por proxy a Auðr en F1.19.

---

## 3d. `audr.code-workspace` (objetivo en repo Auðr)

Crear en raíz Auðr (cuando se autorice P1 / prep Mac):

```json
{
  "folders": [
    { "path": ".", "name": "Auðr" },
    { "path": "../Applications/mi_followup_app", "name": "FollowUp (RO)" }
  ],
  "settings": {
    "files.readonlyInclude": {
      "**/mi_followup_app/**": true
    }
  }
}
```

Ajustar paths relativos según dónde se abra el workspace (Mac: `~/Projects/Auðr` + `~/Applications/mi_followup_app`). FollowUp = referencia; **cero features Flask**.

---

## 3e. Checklist espejo Mac — “todo lo no-git de usuario/prod”

**Incluir (no regenerable):**

| Path / tipo | Notas |
|-------------|--------|
| `instance/followup.db` | + `.db-wal` / `.db-shm` si existen en el momento del sync |
| `uploads/` | Aunque esté casi vacío |
| JSON / baselines en `instance/` (p. ej. `watchlist_baseline_*.json`) | Inventariar con `ls instance/` |
| `backups/` recientes de la app en la VM | Si existen bajo `/var/www/followup/backups/` |
| Exports / media de informes | Si existen paths bajo instance, media, static user |
| Logs | **Solo** si hacen falta para depurar (opcionales; suelen ser regenerables) |
| `.env` | Separado: cifrar con `age` → `.env.age` en backup; **no** commitear |

**Excluir:**

| Path | Motivo |
|------|--------|
| `venv/` | Recrear con `requirements.txt` si hace falta arrancar |
| `__pycache__/`, `*.pyc` | Regenerables |
| `.git/` | Opcional según tamaño; el código ya está en GitHub + tag `finaloldversion` |
| Caches de import/progress locks | Regenerables |

Documento del espejo: `RESTORE_LOCAL.md` en `~/backups/followup_mirror_YYYYMMDD/` con esta checklist marcada.

**Nota `age`:** Django/Next **no** usan `age` en runtime. El `.env` en la VM sigue en claro con permisos de fichero. `age` solo protege copias off-site.

---

## 4. Micro-pasos — Fase 0 Blindaje (+ espejo Mac)

- [x] **F0.00** BD SQLite + integrity + snapshot GCP + tag `finaloldversion` *(hecho 17 jul; pre-checklist)*
- [x] **F0.01** Actualizar IP/tipo en §1 si cambian — *Tabla al día* *(19 jul: e2-medium, IP 35.226.138.80, disco 20 GB)*
- [x] **F0.02** Verificar tag `finaloldversion` en remoto FollowUp — *Tag visible* *(19 jul: `e20b415` @ `amieva91/mi_followup_app`)*
- [x] **F0.03** Verificar snapshot GCP READY — *Status READY* *(19 jul: `followup-finaloldversion-20260717-102444` READY)*
- [x] **F0.04** SHA BD backup Mac == VM `…_LATEST.db` — *Igual* *(19 jul: `4c4b1463…` Mac == VM LATEST)*
- [x] **F0.04a** **Sync espejo:** código prod → Mac (tag `finaloldversion`; **sin** copiar `venv/`) — *Tree alineado* *(19 jul: tarball excl. venv/.env/db/uploads; HEAD=e20b415; working tree=prod)*
- [x] **F0.04b** Sync BD prod → Mac `instance/followup.db` — *SHA == prod* *(19 jul: sqlite `.backup` live → Mac; SHA `36298a4d…`; integrity ok; freeze LATEST sigue `4c4b1463…` en ~/backups)*
- [x] **F0.04c** Sync uploads (+ configs útiles, sin secretos en claro en git) — *Espejo* *(19 jul: uploads/.gitkeep; watchlist_baseline JSON; .flaskenv; sin .env; locks omitidos)*
- [x] **F0.04d** Backup local espejo + `RESTORE_LOCAL.md` — *Restore smoke Mac* *(19 jul: `~/backups/followup_mirror_20260719/`; smoke integrity ok)*
- [x] **F0.04e** Si se necesita consultar Flask en Mac: `python -m venv` + `pip install -r requirements.txt` — *venv local nuevo* *(19 jul: Python 3.12; 3.14 falló con pandas)*
- [x] **F0.05** Tarball `/var/www/followup` (excl. `venv`, `__pycache__`, caches) → `/var/www/followup-backups/` — *Fichero existe* *(19 jul: `…_20260719_110247.tgz` ~191 MB; SHA `1b8ba07f…`; LATEST symlink)*
- [x] **F0.06** (Opcional higiene) Cifrar `.env` con **`age`** → `env_finaloldversion.age`; identity solo Mac — *`.age` en backups; o diferir y no subir `.env` a GCS* *(19 jul: Mac + VM backups; decrypt smoke OK; identity `~/.config/age/audr-followup-backup.identity`)*
- [x] **F0.07** `scp` tarball (+ `.age` si existe) → Mac backups — *En Mac* *(19 jul: `~/backups/followup_finaloldversion/…110247.tgz` SHA OK; `.age` ya presente)*
- [x] **F0.08** Bucket **`gs://audr-backups-amieva91`** (proyecto VM) + upload tarball/db/uploads/`.age` — *`gsutil ls` OK* *(19 jul: creado us-central1; prefix `finaloldversion/20260719/`)*
- [x] **F0.09** `RESTORE.md` (+ checklist IP/GoDaddy §3b) — *En backups* *(19 jul: `~/backups/followup_finaloldversion/RESTORE.md`)*
- [x] **F0.10** Copiar `RESTORE.md` a Mac + GCS — *3 sitios* *(19 jul: Mac + VM `/var/www/followup-backups/` + GCS)*
- [x] **F0.11** Restore smoke BD — *`ok`* *(19 jul: Mac freeze+live ok; GCS download ok; VM LATEST ok vía copia /tmp)*
- [x] **F0.12** (Opcional) Unpack tree `/tmp` — *OK* *(19 jul: 6605 ficheros; sin venv; smoke OK; temp borrado)*
- [x] **F0.13** Parar `followup` + `followup-jobs` — *inactive* *(19 jul 12:20 UTC: ambos inactive)*
- [x] **F0.14** Nginx mantenimiento con texto §3c en la IP — *HTTP muestra AUÐR…* *(19 jul: `/var/www/audr-maintenance/`; IP + audr.com + followup.fit → static)*
- [x] **F0.15** Marcar Fase 0 HECHO en este doc — *Checklist* *(19 jul: F0.00–F0.15 cerrados)*

### Fase 0 — cierre (19 jul 2026)

| Resultado | Valor |
|-----------|--------|
| Blindaje | Tag + snapshot + tarball + Mac + GCS + RESTORE + smoke |
| Flask | `followup` + `followup-jobs` **inactive** |
| Web IP | App Auðr · `http://34.170.20.250/` (IP actual 20 jul; efímera) |
| P1 | **HECHO** — repo `amieva91/audr` + tag `audr-pre-vm-seed-20260719` |
| F1 | **HECHO** — F1.01–F1.21 · seed VM + CI |

Continúa abajo: **§5 P1** (línea ~358) · **§6 F1** (línea ~378).

---

## 5. Micro-pasos — Pre-Fase 1 (GitHub + primer commit) — **bloqueante clone VM**

Commits **solo con OK explícito del usuario**. Repo: **`amieva91/audr`** (privado).

- [x] **P1.01** Inventario untracked + tamaño; exclusiones — *Lista* *(19 jul: sin commits; ~818 MB tree; excl. node_modules/.next/.venv/.env/celerybeat; informe en backups)*
- [x] **P1.02** Auditar `.gitignore` (venv, node_modules, .next, .env, celerybeat, *.db, storybook-static) — *Review* *(19 jul: añadidos celerybeat, *.db, .env.*, !.env.example)*
- [x] **P1.03** Crear repo vacío **`amieva91/audr`** (sin README conflictivo) — *URL `github.com/amieva91/audr`* *(19 jul: PRIVATE, isEmpty)*
- [x] **P1.04** Commit — `docs/` + `.cursor/rules/` + `docs/prompts/` + `docs/adr/` — *En HEAD* *(19 jul: `9763e56`, 81 files)*
- [x] **P1.05** Commit — `contracts/` — *En HEAD* *(19 jul: `640d40e`)*
- [x] **P1.06** Commit — `backend/` (T3–T4b; sin `.venv`) — *En HEAD* *(19 jul: `f6ded1b`, 92 files)*
- [x] **P1.07** Commit — `frontend/` (sin `node_modules`/`.next`) — *En HEAD* *(19 jul: `087dd19`, 105 files)*
- [x] **P1.08** Commit — `docker/` + root (`.gitignore`, `README`, `.env.example`, **`audr.code-workspace`**) — *En HEAD* *(19 jul: `db94c15`)*
- [x] **P1.09** `git remote add` + push `main` — *Remoto al día* *(19 jul: `origin/main` @ `db94c15`)*
- [x] **P1.10** Tag `audr-pre-vm-seed-YYYYMMDD` + push tag — *Tag remoto* *(19 jul: `audr-pre-vm-seed-20260719`)*
- [x] **P1.11** Verificar clone fresco en `/tmp` — *Rules/docs OK* *(19 jul: tag → `db94c15`; 8 rules; sin venv/node_modules/.env)*
- [x] **P1.12** (Opcional) smoke compose en Mac — *Health local* *(19 jul: Colima + docker-compose; postgres/redis healthy; swagger 200; teardown OK)*
- [x] **P1.13** CI: **no** en este paso — diferir a post F1.20 — *Acuerdo* *(marcado diferido; activar en F1.21)*

---

## 6. Micro-pasos — Fase 1 Sembrar Auðr en la VM

- [x] **F1.01** `free -h` / `df -h` en VM — *Anotado* *(19 jul: RAM avail 3.2 GiB; disco `/` 19G, libres **8.1G** — insuficientes; hace falta F1.02)*
- [x] **F1.02** Stop VM → `e2-medium` + disco **~40 GB** → start — *machineType + size OK* *(19 jul: disco 20→40 GB; FS ~38G/28G libres; IP nueva `34.61.176.75`)*
- [x] **F1.03** Anotar IP nueva; si cambió y DNS ya apunta a VM → **GoDaddy A**; si no, actualizar §9 — *Acceso Internet OK* *(19 jul: IP `34.61.176.75`; GoDaddy no tocado — placeholder; §9+RESTORE actualizados)*
- [x] **F1.04** Confirmar ≥15–20 GB libres tras ampliación — *`df -h`* *(19 jul: `/` 38G, libres **28G** — PASS)*
- [x] **F1.05** Instalar Docker Engine + Compose plugin — *`docker compose version`* *(19 jul: Docker 29.6.2 + Compose v5.3.1; hello-world OK)*
- [x] **F1.06** `mkdir -p /var/www/audr` (+ backups) — *Dirs* *(19 jul: `/var/www/audr` + followup-backups)*
- [x] **F1.07** `git clone` → `/var/www/audr` — *`.git`* *(19 jul: HEAD `db94c15`; remote sin token)*
- [x] **F1.08** Checkout tag P1 — *`git describe`* *(19 jul: `audr-pre-vm-seed-20260719`)*
- [x] **F1.09** Verificar 8 rules + docs bootstrap — *Presentes* *(19 jul: 8 rules; 16 ADRs; BOOTSTRAP+plan+prompts OK)*
- [x] **F1.10** Gap apps: confirmar solo T3–T4b apps (igual §0c) — *Doc* *(19 jul: presentes admin_ops/catalog/core/investments/live/wealth; faltan T5–T8)*
- [x] **F1.11** `.env` prod desde `.env.example` (secretos **nuevos**) — *No en git* *(19 jul: `/var/www/audr/.env` mode 600; IP `34.61.176.75`; secretos no logueados)*
- [x] **F1.12** `docker compose -f … config` — *OK* *(19 jul: `docker-compose.vm.yml` exit 0; prod incompleto en tag — override VM sin nginx)*
- [x] **F1.13** Up postgres + redis — *Healthy* *(19 jul: postgres 17 + redis 7.4 healthy)*
- [x] **F1.14** Migraciones Django — *Exit 0* *(19 jul: 28 migraciones aplicadas)*
- [x] **F1.15** Up backend + celery + beat — *Healthy* *(19 jul: health 200; celery+beat up; 127.0.0.1:8000)*
- [x] **F1.16** Up frontend — *200 interno* *(19 jul: `127.0.0.1:3000` → 200; Next dev en compose)*
- [x] **F1.17** Smoke auth con **usuario heredado** FollowUp cuando exista en PG; **no** crear demo ahora — *200 cuando aplique* *(19 jul: endpoints OK — login 401/400, me 401, refresh 401, health 200; **0 users** en PG; sesión 200 **diferida** hasta migración usuarios)*
- [x] **F1.18** Smoke SSE — *Evento* *(19 jul: sin auth 401; con JWT efímero → `connection.heartbeat`; user borrado; 0 users)*
- [x] **F1.19** Nginx → Auðr por IP (mantenimiento sustituido / server_name IP) — *URL pública IP* *(19 jul: `http://34.61.176.75/` → Next; `/api/health/` 200; audr.com/followup.fit siguen mantenimiento)*
- [x] **F1.20** Doc `docs/PHASE_VM_SEED.md` (hash, IP, machine type) — *En repo (commit cuando usuario pida)* *(20 jul: doc escrito; IP `34.170.20.250`; tag `audr-pre-vm-seed-20260719` @ `db94c15`)*
- [x] **F1.21** (Post-smoke) Activar CI GitHub Actions mínimo — *Workflow verde* *(20 jul: `.github/workflows/ci.yml` verde en `main` @ `1c8aafc`; backend migrate/check/test + frontend npm ci/tsc)*

---

## 7. Micro-pasos — Fase 2 Congelar + inventario

- [x] **F2.01** No más `deploy-experimental` / features Flask — *Acuerdo operativo* *(20 jul: rule Cursor + guard en script; BRIEF; Flask permanece inactive)*
- [ ] **F2.02** Actualizar gaps [TRANSFORM_INVENTORY.md](TRANSFORM_INVENTORY.md) — *Tabla*
- [ ] **F2.03** Export registry/delistings/mappings desde backup SQLite — *JSON en backups + opcional repo `fixtures/`*
- [ ] **F2.04** Checklist datos usuario a migrar — *Lista*
- [ ] **F2.05** Diff parsers/FIFO Auðr vs FollowUp PORT/DIFF/DROP — *Tabla*

---

## 8. Fase 3 — Port por verticales (tras seed)

Orden:

1. Validar T4/T4b **en VM** (import CSV real, Yahoo, P/L)
2. **T5** — crear apps faltantes + port (ver desglose)
3. T6 wealth+live+empty+flash (endurecer)
4. T7 alternatives + property + strategy
5. T8 alerts + settings + reports (sin IA)
6. **T9** — Admin ops (detalle §8b) + migrate datos + **DNS auðr.com** + checklist bootstrap §0b

### Plantilla por vertical

| Sub | Acción |
|-----|--------|
| V.a | Formula review doc |
| V.b | Models + migración |
| V.c | Servicios &lt; 400 LOC (leer FollowUp congelado) |
| V.d | DRF + OpenAPI |
| V.e | Tests |
| V.f | UI móvil |
| V.g | UI escritorio |
| V.h | SSE/caché si aplica |
| V.i | Empty states |
| V.j | `PHASE_*.md` |
| V.k | Commit **solo si usuario pide**; grep anti-Flask |
| V.l | Smoke en IP VM |

### T5 desglose

- [ ] **T5.0** Scaffold apps Django `cashflow`, `banking`, `liabilities` (vacías + registered)
- [ ] **T5.1** Cashflow gastos + categorías
- [ ] **T5.2** Cashflow ingresos
- [ ] **T5.3** Banking
- [ ] **T5.4** Liabilities planes/cuotas
- [ ] **T5.5** Simulador amortización
- [ ] **T5.6** Wire nav móvil/escritorio Finanzas

---

## 8b. Admin — vistas y plan de ejecución (T9)

**Fuente de producto:** [ADMIN_OBSERVABILITY.md](ADMIN_OBSERVABILITY.md) · [ADR-013](adr/ADR-013-admin-ops-only.md)  
**Principio:** el admin **no** reutiliza vistas de usuario (sin portfolio/gastos en `/admin`). Es un **centro de operaciones** con SSE. Solo **escritorio** (sin bottom nav usuario).

### Acceso

| Regla | Detalle |
|-------|---------|
| Rol | `is_staff` / `is_admin` únicamente |
| UI | Layout Next `/admin/*` separado del shell usuario |
| API | Usuario normal → **403** en `/api/admin/*` |
| Eliminado vs Flask admin | Redirect a asset-registry / vistas de producto como “admin” |

### Inventario de vistas (UI exclusiva)

| # | Vista | Ruta UI (objetivo) | Contenido |
|---|--------|-------------------|-----------|
| A1 | **Ops dashboard** | `/admin` | Resumen estado global (servicios, colas, APIs, alertas ops abiertas) |
| A2 | **Architecture diagram** | `/admin/architecture` | Diagrama interactivo live (React Flow) |
| A3 | **Services** | `/admin/services` | Gunicorn, Celery workers, **Celery Beat**, Redis, Postgres, nginx (+ Docker si socket) |
| A4 | **Celery Beat** | `/admin/celery-beat` | Schedule, último tick, próximas ejecuciones, jobs perdidos, log Beat |
| A5 | **Jobs** | `/admin/jobs` | Tareas Celery activas, profundidad de cola, historial |
| A6 | **SSE connections** | `/admin/sse` | Usuarios conectados al live; streams admin |
| A7 | **Cache rebuild** | `/admin/cache` | Cola full/incremental por usuario |
| A8 | **External APIs** | `/admin/apis` | Yahoo, FX — latencia, errores, rate |
| A9 | **Logs** | `/admin/logs` o panel lateral | Tail por servicio (también desde click en nodo del diagrama) |
| A10 | **Alerts ops** | `/admin/alerts-ops` | Umbrales: fallo API, worker down, Beat silent, disk, PG connections |
| A11 | **Catalog queue** | `/admin/catalog` | Instrumentos `pending_admin`; validar Yahoo/ticker; corporate actions |
| A12 | **Users** | `/admin/users` | Mínimo: activar/desactivar; **sin** UI portfolio |

### SSE admin — `/api/admin/ops/stream`

| Evento | Uso en UI |
|--------|-----------|
| `ops.heartbeat` | Reloj / liveness del stream |
| `ops.service_status` | Color nodos diagrama + tabla Services |
| `ops.celery_worker` | Nodos workers efímeros (started/stopped) |
| `ops.celery_beat` | Nodo Beat + indicador tick |
| `ops.celery_beat_schedule` | Tabla schedule Beat |
| `ops.celery_task` | Jobs activos / historial |
| `ops.docker_container` | Estado contenedores (si Docker socket RO) |
| `ops.db_stats` | Postgres en Services / dashboard |
| `ops.redis_stats` | Redis en Services / dashboard |
| `ops.api_call` | External APIs + nodo Yahoo |
| `ops.cache_rebuild` | Vista Cache rebuild |
| `ops.user_sse` | Vista SSE connections |
| `ops.alert_ops` | Banner / lista Alerts ops |

### Celery Beat (obligatorio, vista dedicada)

Beat ≠ workers: programa, no ejecuta. Monitorizar aparte.

| Métrica | Umbral alerta ejemplo |
|---------|----------------------|
| `ops.celery_beat.is_alive` | down |
| `ops.celery_beat.last_scheduler_tick_age_sec` | > 120 |
| `ops.celery_beat.missed_schedules_count` | > 0 en 15 min |

Health: `GET /api/admin/health/celery-beat` · heartbeat Redis `audr:ops:celery_beat:heartbeat`.

### Diagrama arquitectura live (A2)

Nodos: Browser SSE, nginx, Gunicorn, Next, Celery Worker(s), Celery Beat, Redis, PostgreSQL, Yahoo.  
Colores por heartbeat; click Beat → schedule/logs; click Worker → tareas/logs; arista Beat→Redis al encolar.

### Instrumentación requerida (backend)

- `structlog` JSON por servicio
- `ApiCallLog` (Yahoo, FX) — portar idea FollowUp
- Health: `/api/health`, `/api/admin/health/deep`, `/api/admin/health/celery-beat`
- Celery signals → Redis pub/sub `audr:ops`
- Beat heartbeat publisher
- Opcional: Docker socket read-only

### Estado código hoy (gap)

| Pieza | Estado 17–19 jul |
|-------|------------------|
| App `admin_ops` | Existe (catalog instruments + corporate actions API) |
| SSE `/api/admin/ops/stream` | **Pendiente** |
| UI `/admin/*` ops | **Pendiente** |
| Diagrama React Flow | **Pendiente** |
| Vista Beat / Jobs / Services… | **Pendiente** |

### Micro-pasos T9 (admin) — orden pequeño

**T9a — MVP ops (tablas + health; sin diagrama full)** — alineado “Fase 9 MVP / 9b diagrama” del doc observabilidad:

- [ ] **T9a.01** Layout Next `/admin` (solo desktop; 403/redirect si no staff) — *Shell admin sin bottom nav user*
- [ ] **T9a.02** Health deep + celery-beat endpoint — *JSON staff-only*
- [ ] **T9a.03** Instrumentación Redis `audr:ops` + signals Celery básicos — *Eventos en Redis*
- [ ] **T9a.04** SSE `/api/admin/ops/stream` (heartbeat + service_status mínimo) — *Stream abre para staff*
- [ ] **T9a.05** Vista **Ops dashboard** (A1) con datos health — *Página usable*
- [ ] **T9a.06** Vista **Services** (A3) tabla — *Estados visibles*
- [ ] **T9a.07** Vista **Celery Beat** (A4) schedule + tick age — *Tabla schedule*
- [ ] **T9a.08** Vista **Jobs** (A5) cola/activas — *Lista*
- [ ] **T9a.09** Vista **Catalog queue** (A11) — reusar/mejorar API actual — *Validar pending*
- [ ] **T9a.10** Vista **Users** (A12) activar/desactivar — *Sin portfolio*
- [ ] **T9a.11** Doc `PHASE_T9A_ADMIN_OPS_MVP.md` + matriz UI (desktop only) — *Doc*

**T9b — Live rico + diagrama + alertas ops:**

- [ ] **T9b.01** Eventos SSE restantes (api_call, cache_rebuild, user_sse, docker…) — *Contratos al día*
- [ ] **T9b.02** Vista **External APIs** (A8) + `ApiCallLog` — *Latencia/errores*
- [ ] **T9b.03** Vista **Cache rebuild** (A7) — *Cola por user*
- [ ] **T9b.04** Vista **SSE connections** (A6) — *Counts live*
- [ ] **T9b.05** Vista **Logs** (A9) tail por servicio — *Click → log*
- [ ] **T9b.06** **Architecture diagram** (A2) React Flow + colores live — *Nodos clickables*
- [ ] **T9b.07** Click nodo Beat/Worker → paneles laterales — *Navegación diagrama↔vistas*
- [ ] **T9b.08** Vista **Alerts ops** (A10) + reglas `scope=ops` — *Umbrales configurables*
- [ ] **T9b.09** Alertas Beat (tick age, missed schedules) cableadas — *Disparan `ops.alert_ops`*
- [ ] **T9b.10** Smoke en VM IP `/admin` con usuario staff — *Checklist*
- [ ] **T9b.11** Doc `PHASE_T9B_ADMIN_DIAGRAM.md` — *Doc*

**T9c — Cutover datos/DNS** (bloque aparte del panel, mismo “T9” del plan alto nivel):

- [ ] **T9c.01** Migración datos usuario SQLite→PG (script versionado)
- [ ] **T9c.02** Validar totales vs backup FollowUp
- [ ] **T9c.03** DNS `auðr.com` → IP VM + HTTPS
- [ ] **T9c.04** Checklist bootstrap §0b

### Relación con el resto del plan

- **No** implementar admin ops en Flask.
- Catalog queue (A11) puede adelantarse en parte durante **T4/validación VM** (ya hay API); el resto de ops espera **después de Compose estable (F1)** y preferiblemente tras T5–T6 si hay carga real de jobs — pero **T9a puede empezar en cuanto F1+Celery Beat existan en la VM**.
- Alertas **usuario** (`alerts` app) ≠ **Alerts ops** (A10); no mezclar.

---

## 9. URLs / dominio

| Uso | Valor |
|-----|--------|
| Prueba durante migración | **`http://34.170.20.250/`** (NAT efímera; re-verificar tras reboot/stop-start) |
| Dominio definitivo | `auðr.com` / `xn--aur-4ma.com` |
| Cutover DNS | **Tarde** — tras smoke estable (T5/T6+ o cutover T9), no día 1 |

---

## 10. Fase 4 Limpieza final

Ver [MIGRATE_ON_PROD_VM.md](MIGRATE_ON_PROD_VM.md) §7 + checklist bootstrap §0b de este doc.

---

## 11. Orden inmediato (cuando se autorice ejecutar)

```
F0.01–F0.04d   Sync espejo prod→Mac FollowUp + backup local espejo
F0.05–F0.15    Tarball + GCS + RESTORE + apagar Flask + nginx mantenimiento
P1.01–P1.12    amieva91/audr + commits lógicos + tag (CI aún no)
F1.01–F1.20    e2-medium + disco 40GB + (GoDaddy si IP cambia) + clone + Compose + smoke
F1.21          CI después del smoke
F2… / T4 validación en VM / T5…
T9a (MVP admin tablas+SSE) → … → T9b (diagrama+alertas ops) → T9c (migrate+DNS)
(al final) checklist bootstrap §0b
```

**Sin ejecutar hasta que el usuario lo pida.** Primer bloque: F0 (espejo Mac + GCS) → P1.

**Admin:** detalle de vistas y micro-pasos en **§8b** ([ADMIN_OBSERVABILITY.md](ADMIN_OBSERVABILITY.md)).

---

## 12. Preguntas abiertas (restantes)

| # | Pregunta | Bloquea |
|---|----------|---------|
| — | _(ninguna bloqueante ahora)_ | — |

*Q9–Q18 cerradas. age = higiene de backup, no runtime; sin demo; espejo = §3e.*

---

## 13. Historial

| Fecha | Cambio |
|-------|--------|
| 2026-07-17 | Creación inicial |
| 2026-07-17 | Respuestas 1–5; bootstrap §0b; gap apps |
| 2026-07-17 | Q1–Q8; §3b sync Mac + GoDaddy |
| 2026-07-17 | Q9–Q14: IP efímera, age, workspace |
| 2026-07-19 | §8b Admin: inventario vistas A1–A12, SSE, Beat, T9a/T9b/T9c desde ADMIN_OBSERVABILITY |
| 2026-07-19 | Protocolo: checklist `- [ ]`/`[x]` + explicación previa por paso (modifica / feature / ventaja / web) |
| 2026-07-19 | F0.01: VM RUNNING, e2-medium, disco 20 GB, IP `35.226.138.80` |
| 2026-07-19 | F0.02: tag `finaloldversion` remoto → commit `e20b415` |
| 2026-07-19 | F0.03: snapshot GCP READY |
| 2026-07-19 | F0.04: SHA BD Mac == VM `4c4b1463…` |
| 2026-07-19 | F0.04a: código prod→Mac (sin venv/.env); HEAD `e20b415`; tree=prod |
| 2026-07-19 | F0.04b: `instance/followup.db` Mac = live prod `36298a4d…` (≠ freeze `4c4b1463…`) |
| 2026-07-19 | F0.04c: uploads + watchlist_baseline + `.flaskenv` (sin `.env`) |
| 2026-07-19 | F0.04d: espejo local `~/backups/followup_mirror_20260719/` + RESTORE_LOCAL |
| 2026-07-19 | F0.04e: venv Mac con Python 3.12 + requirements |
| 2026-07-19 | F0.05: tarball VM `/var/www/followup-backups/…110247.tgz` SHA `1b8ba07f…` |
| 2026-07-19 | F0.06: `.env` → `env_finaloldversion_20260719.age` (identity solo Mac) |
| 2026-07-19 | F0.07: tarball + `.age` en Mac `~/backups/followup_finaloldversion/` |
| 2026-07-19 | F0.08: bucket `gs://audr-backups-amieva91` + upload `finaloldversion/20260719/` |
| 2026-07-19 | F0.09: `RESTORE.md` en Mac backups |
| 2026-07-19 | F0.10: `RESTORE.md` en Mac + VM + GCS |
| 2026-07-19 | F0.11: restore smoke BD ok (Mac/GCS/VM) |
| 2026-07-19 | F0.12: unpack tarball /tmp OK (6605 files) |
| 2026-07-19 | F0.13: `followup` + `followup-jobs` inactive |
| 2026-07-19 | F0.14: nginx mantenimiento AUÐR en IP `35.226.138.80` |
| 2026-07-19 | **F0.15: Fase 0 HECHO** — siguiente P1 |
| 2026-07-19 | P1.01: inventario Auðr (sin commits; excl. venv/node_modules/.env) |
| 2026-07-19 | P1.02: `.gitignore` endurecido (celerybeat, *.db, .env.*) |
| 2026-07-19 | P1.03: repo privado vacío https://github.com/amieva91/audr |
| 2026-07-19 | P1.04: commit `9763e56` docs+rules+prompts+adr |
| 2026-07-19 | P1.05: commit `640d40e` contracts |
| 2026-07-19 | P1.06: commit `f6ded1b` backend T3–T4b |
| 2026-07-19 | P1.07: commit `087dd19` frontend |
| 2026-07-19 | P1.08: commit `db94c15` docker + workspace |
| 2026-07-19 | P1.09: push `main` → github.com/amieva91/audr |
| 2026-07-19 | P1.10: tag `audr-pre-vm-seed-20260719` |
| 2026-07-19 | P1.11: clone fresco /tmp OK (8 rules) |
| 2026-07-19 | P1.12: smoke Compose Mac OK (swagger 200) |
| 2026-07-19 | P1.13: CI diferido → F1.21; **P1 cerrado** |
| 2026-07-19 | F1.01: RAM 3.2 GiB avail; disco libres 8.1G (necesita resize) |
| 2026-07-19 | F1.02: disco 40 GB; IP `34.61.176.75` (cambió) |
| 2026-07-19 | F1.03: §9+RESTORE → IP nueva; sin GoDaddy (placeholder) |
| 2026-07-19 | F1.04: disco libres 28G PASS |
| 2026-07-19 | F1.05: Docker 29.6.2 + Compose v5.3.1 |
| 2026-07-19 | F1.06: `/var/www/audr` creado |
| 2026-07-19 | F1.07: clone `/var/www/audr` @ `db94c15` |
| 2026-07-19 | F1.08: checkout tag `audr-pre-vm-seed-20260719` |
| 2026-07-19 | F1.09: 8 rules + docs bootstrap OK en VM |
| 2026-07-19 | F1.10: gap apps = solo T3–T4b (6 apps) |
| 2026-07-19 | F1.11: `.env` prod en VM (600; secretos nuevos) |
| 2026-07-19 | F1.12: `docker-compose.vm.yml` config OK |
| 2026-07-19 | F1.13: postgres + redis healthy |
| 2026-07-19 | F1.14: migrate Django OK (28) |
| 2026-07-19 | **Override OpenFIGI:** import CSV como FollowUp (con OpenFIGI); no aplicar R-03 / ADR-014 aún — ver BRIEF |
| 2026-07-19 | **Override delistings:** corporate actions como FollowUp (`CASH_ACQUISITION`/`BANKRUPTCY` + reconciliación); no modelo Auðr redesigned |
| 2026-07-19 | Alineados docs secundarios al override: TRANSFORM_INVENTORY, PLANNING_MASTER, TRANSFORM_FOLLOWUP_TO_AUDR, REQUISITOS_NF, MODULES_REDESIGN, adr/README |
| 2026-07-19 | F1.15: backend+celery+beat up; `/api/health/` 200 |
| 2026-07-19 | F1.16: frontend up; `127.0.0.1:3000` → 200 |
| 2026-07-19 | F1.17: auth smoke OK (401/400 sin usuarios); login 200 diferido a migración |
| 2026-07-19 | F1.18: SSE heartbeat OK (JWT efímero; 0 users al terminar) |
| 2026-07-19 | F1.19: nginx IP → Next:3000 + API:8000; `http://34.61.176.75/` app; health 200 |
| 2026-07-20 | IP efímera cambió → **`34.170.20.250`**; `.env` ALLOWED_HOSTS/CORS/NEXT_PUBLIC actualizados; app OK |
| 2026-07-20 | F1.20: `docs/PHASE_VM_SEED.md` (tag/hash/IP/machine/smokes) |
| 2026-07-20 | F1.21: CI verde (`1c8aafc`); **F1 cerrado** |
| 2026-07-20 | F2.01: Flask congelado — sin deploy-experimental/features; guard script + rule Cursor |
