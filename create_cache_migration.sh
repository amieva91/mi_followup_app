#!/bin/bash
# Script para crear la migración de MetricsCache

cd ~/www
source venv/bin/activate
flask db migrate -m "Add MetricsCache table for performance optimization"

