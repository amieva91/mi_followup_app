ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92 << 'EOF'
cd ~/www
echo "📦 Haciendo backup de BD..."
cp instance/app.db instance/app.db.backup_$(date +%Y%m%d_%H%M%S)
echo "🔄 Pulling cambios..."
git fetch origin
git pull origin main
echo "🔧 Aplicando migraciones..."
source venv/bin/activate
export FLASK_APP=run.py
flask db upgrade
echo "🔄 Reiniciando servicio..."
sudo systemctl restart followup
echo "✅ Deploy completado"
sudo systemctl status followup --no-pager -l
EOF
