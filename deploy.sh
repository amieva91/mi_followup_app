#!/bin/bash
# Script de despliegue FollowUp - Google Cloud VM
# Ejecutar como: bash deploy.sh
# Dominio: followup.fit

set -e

DOMAIN="followup.fit"
REPO="https://github.com/amieva91/mi_followup_app.git"
APP_DIR="/home/followup"
APP_USER="followup"

echo "=== Instalando dependencias del sistema ==="
sudo apt-get update
sudo add-apt-repository -y universe 2>/dev/null || true
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv nginx git

# Certbot: apt en Ubuntu 22/24 o snap como fallback
if ! sudo apt-get install -y certbot python3-certbot-nginx 2>/dev/null; then
    sudo snap install --classic certbot 2>/dev/null || true
    sudo ln -sf /snap/bin/certbot /usr/bin/certbot 2>/dev/null || true
fi

echo "=== Creando usuario y directorio ==="
sudo useradd -m -s /bin/bash $APP_USER 2>/dev/null || true
sudo mkdir -p $APP_DIR
sudo chown $APP_USER:$APP_USER $APP_DIR

echo "=== Clonando repositorio ==="
cd $APP_DIR
if [ -d "app" ]; then
    sudo -u $APP_USER git -C . pull 2>/dev/null || sudo -u $APP_USER git clone $REPO . --depth 1
else
    sudo -u $APP_USER git clone $REPO . --depth 1
fi

echo "=== Configurando entorno Python ==="
sudo -u $APP_USER python3 -m venv venv
sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip
sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r requirements.txt gunicorn

echo "=== Creando archivo .env ==="
SECRET_KEY=$(openssl rand -hex 32)
# SQLite requiere 4 barras para ruta absoluta: sqlite:////path
sudo -u $APP_USER tee $APP_DIR/.env > /dev/null << ENVFILE
FLASK_ENV=production
SECRET_KEY=$SECRET_KEY
DATABASE_URL=sqlite:///$APP_DIR/instance/followup.db
ENVFILE

echo "=== Creando directorios necesarios ==="
sudo -u $APP_USER mkdir -p $APP_DIR/instance $APP_DIR/logs $APP_DIR/uploads $APP_DIR/output

echo "=== Ejecutando migraciones ==="
cd $APP_DIR
sudo -u $APP_USER FLASK_APP=run.py $APP_DIR/venv/bin/flask db upgrade 2>/dev/null || true

echo "=== Creando servicio systemd para Gunicorn ==="
sudo tee /etc/systemd/system/followup.service > /dev/null << SVC
[Unit]
Description=FollowUp Gunicorn
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
Environment="FLASK_ENV=production"
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 --timeout 120 run:app
Restart=always

[Install]
WantedBy=multi-user.target
SVC

echo "=== Configurando Nginx (HTTP temporal) ==="
sudo tee /etc/nginx/sites-available/followup > /dev/null << NGINX
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/followup /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo "=== Iniciando servicio FollowUp ==="
sudo systemctl daemon-reload
sudo systemctl enable followup
sudo systemctl restart followup

echo ""
echo "=== DESPLIEGUE COMPLETADO ==="
echo "La app está corriendo en http://$DOMAIN (puede tardar unos minutos en propagar DNS)"
echo ""
echo "Para obtener certificado SSL (HTTPS), ejecuta:"
echo "  sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos -m TU_EMAIL"
echo ""
echo "Reemplaza TU_EMAIL con tu email real para renovaciones de Let's Encrypt."
echo ""
