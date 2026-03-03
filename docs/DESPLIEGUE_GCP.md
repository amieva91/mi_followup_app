# Despliegue FollowUp en Google Cloud

## Requisitos previos
- VM e2-micro en Google Cloud (Ubuntu 24.04)
- Dominio followup.fit configurado en GoDaddy (registros A → IP de la VM)
- Repositorio público o acceso por SSH

## Paso 1: Conectar por SSH

**Opción A - Desde la consola de Google Cloud:**
1. Ve a Compute Engine → VM instances
2. Click en **SSH** junto a la VM "followup"

**Opción B - Desde terminal local (con gcloud CLI):**
```bash
gcloud compute ssh followup --zone=us-central1-c
```

## Paso 2: Descargar y ejecutar el script

```bash
# Descargar el script (si el repo es público)
curl -sL https://raw.githubusercontent.com/amieva91/mi_followup_app/main/deploy.sh -o deploy.sh

# O copiar manualmente el contenido de deploy.sh y crear el archivo

# Dar permisos y ejecutar
chmod +x deploy.sh
sudo bash deploy.sh
```

**Si el repositorio es privado:** Modifica el script para usar `git clone` con token o clave SSH, o sube el código manualmente con `scp`.

## Paso 3: Obtener certificado SSL (HTTPS)

Una vez la app funcione en HTTP:

```bash
sudo certbot --nginx -d followup.fit -d www.followup.fit --non-interactive --agree-tos -m TU_EMAIL
```

Reemplaza `TU_EMAIL` con tu email real.

## Paso 4: Crear usuario inicial

La primera vez necesitas crear un usuario. Conéctate a la VM y ejecuta:

```bash
cd /home/followup
sudo -u followup ./venv/bin/flask shell
```

En el shell de Flask:
```python
from app import create_app, db
from app.models import User

app = create_app('production')
with app.app_context():
    from app import bcrypt
    user = User(
        email='tu@email.com',
        username='admin',
        password_hash=bcrypt.generate_password_hash('tu_password_seguro').decode('utf-8')
    )
    db.session.add(user)
    db.session.commit()
    print('Usuario creado')
```

## Comandos útiles

```bash
# Estado del servicio
sudo systemctl status followup

# Ver logs
sudo journalctl -u followup -f

# Reiniciar app
sudo systemctl restart followup

# Actualizar código
cd /home/followup
sudo -u followup git pull
sudo -u followup ./venv/bin/pip install -r requirements.txt
sudo systemctl restart followup
```
