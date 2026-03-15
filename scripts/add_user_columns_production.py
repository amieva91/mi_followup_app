#!/usr/bin/env python3
"""Add missing user columns (avatar_id, birth_year, enabled_modules) to production DB.
Run as user followup: sudo -u followup python3 add_user_columns_production.py /var/www/followup
"""
import sqlite3
import os
import sys

app_root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(app_root, "instance", "followup.db")
if not os.path.exists(db_path):
    db_path = os.path.join(app_root, "instance", "app.db")
if not os.path.exists(db_path):
    print("DB not found at", db_path)
    exit(1)

conn = sqlite3.connect(db_path)
for col, typ in [("avatar_id", "INTEGER"), ("birth_year", "INTEGER"), ("enabled_modules", "TEXT")]:
    try:
        conn.execute("ALTER TABLE users ADD COLUMN " + col + " " + typ)
        conn.commit()
        print("Added", col)
    except sqlite3.OperationalError as e:
        if "duplicate" in str(e).lower():
            print(col, "already exists")
        else:
            print(col, "error:", e)
conn.close()
print("Done")
