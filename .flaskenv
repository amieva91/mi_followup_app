# Flask environment configuration
FLASK_APP=run.py
FLASK_ENV=development
FLASK_DEBUG=1
FLASK_RUN_PORT=5000
FLASK_RUN_HOST=127.0.0.1

# IMPORTANTE: Estas opciones no se pueden configurar en .flaskenv
# Para ejecutar con threading habilitado, usa:
# python run.py
# 
# NO usar: flask run (no soporta threading correctamente)

