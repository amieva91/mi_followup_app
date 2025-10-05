# 🗄️ PROPUESTA DE BASE DE DATOS - MVP

## 📊 COMPARATIVA: ACTUAL vs PROPUESTO

### Sistema Actual
```
❌ 25+ tablas
❌ Relaciones complejas en cascada
❌ Múltiples tablas para una sola funcionalidad
❌ Campos redundantes y poco usados
❌ Sin índices optimizados documentados
❌ Mezcla de funcionalidades core y opcionales
```

### Sistema Propuesto (MVP)
```
✅ 7 tablas core
✅ Relaciones simples y claras
✅ Una tabla por entidad principal
✅ Solo campos esenciales
✅ Índices definidos desde el inicio
✅ Solo funcionalidades críticas
```

**Reducción**: ~71% menos tablas

---

## 🎯 TABLAS CORE DEL MVP

### 1. `users` - Usuarios

```sql
CREATE TABLE users (
    -- Identificación
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    
    -- Información personal
    birth_year INTEGER,
    annual_net_salary DECIMAL(12, 2),
    
    -- Control de acceso
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE NOT NULL,
    
    -- Auditoría
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_login_at TIMESTAMP
);

-- Índices
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_active ON users(is_active);
```

**Campos eliminados del original:**
- `must_change_password` (simplificado en lógica de aplicación)
- `current_login_at` (usar solo `last_login_at`)
- `login_count` (no esencial)

**Decisión**: Mantener lo mínimo necesario para autenticación y perfil.

---

### 2. `bank_accounts` - Cuentas Bancarias

```sql
CREATE TABLE bank_accounts (
    -- Identificación
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    -- Información de la cuenta
    bank_name VARCHAR(100) NOT NULL,
    account_name VARCHAR(100),
    account_number_last4 CHAR(4),  -- Últimos 4 dígitos (opcional)
    
    -- Saldo
    current_balance DECIMAL(12, 2) DEFAULT 0.00 NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR' NOT NULL,
    
    -- Estado
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    
    -- Auditoría
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Foreign Keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Índices
CREATE INDEX idx_bank_accounts_user ON bank_accounts(user_id);
CREATE INDEX idx_bank_accounts_active ON bank_accounts(user_id, is_active);
```

**Campos añadidos**:
- `account_number_last4`: Para diferenciación (privacidad)
- `currency`: Preparado para multi-divisa futura
- `is_active`: Para cuentas cerradas (histórico)

**Uso**: Tracking de efectivo total del usuario.

---

### 3. `expense_categories` - Categorías de Gastos

```sql
CREATE TABLE expense_categories (
    -- Identificación
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    -- Información
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Jerarquía
    parent_id INTEGER,
    
    -- Clasificación
    is_default BOOLEAN DEFAULT FALSE NOT NULL,
    category_type VARCHAR(20) DEFAULT 'expense' NOT NULL,  -- 'expense' o 'debt'
    
    -- Estado
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    
    -- Auditoría
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Foreign Keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES expense_categories(id) ON DELETE SET NULL,
    
    -- Constraints
    UNIQUE(user_id, name)
);

-- Índices
CREATE INDEX idx_expense_categories_user ON expense_categories(user_id);
CREATE INDEX idx_expense_categories_parent ON expense_categories(parent_id);
CREATE INDEX idx_expense_categories_type ON expense_categories(user_id, category_type);
```

**Campos añadidos**:
- `category_type`: Diferencia gastos normales de deudas
- `is_active`: Para categorías eliminadas (mantener histórico)

**Uso**: Organización jerárquica de gastos y deudas.

---

### 4. `expenses` - Gastos

```sql
CREATE TABLE expenses (
    -- Identificación
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category_id INTEGER,
    
    -- Información básica
    description VARCHAR(200) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    date DATE NOT NULL,
    
    -- Tipo
    expense_type VARCHAR(20) DEFAULT 'punctual' NOT NULL,  -- 'punctual' o 'fixed'
    
    -- Recurrencia
    is_recurring BOOLEAN DEFAULT FALSE NOT NULL,
    recurrence_months INTEGER,  -- 1=mensual, 3=trimestral, 6=semestral, 12=anual
    start_date DATE,
    end_date DATE,
    
    -- Metadatos
    notes TEXT,
    
    -- Auditoría
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Foreign Keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES expense_categories(id) ON DELETE SET NULL,
    
    -- Constraints
    CHECK (amount > 0),
    CHECK (recurrence_months IS NULL OR recurrence_months > 0)
);

-- Índices críticos para performance
CREATE INDEX idx_expenses_user_date ON expenses(user_id, date DESC);
CREATE INDEX idx_expenses_category ON expenses(category_id);
CREATE INDEX idx_expenses_recurring ON expenses(user_id, is_recurring) 
    WHERE is_recurring = TRUE;
```

**Campos añadidos**:
- `notes`: Notas adicionales del usuario

**Validaciones**:
- `amount` debe ser positivo
- `recurrence_months` debe ser positivo si existe

**Uso**: Tracking de gastos puntuales y recurrentes.

---

### 5. `income_categories` - Categorías de Ingresos

```sql
CREATE TABLE income_categories (
    -- Identificación
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    -- Información
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Jerarquía
    parent_id INTEGER,
    
    -- Clasificación
    is_default BOOLEAN DEFAULT FALSE NOT NULL,
    
    -- Estado
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    
    -- Auditoría
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Foreign Keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES income_categories(id) ON DELETE SET NULL,
    
    -- Constraints
    UNIQUE(user_id, name)
);

-- Índices
CREATE INDEX idx_income_categories_user ON income_categories(user_id);
CREATE INDEX idx_income_categories_parent ON income_categories(parent_id);
```

**Uso**: Organización de fuentes de ingreso variable.

---

### 6. `incomes` - Ingresos Variables

```sql
CREATE TABLE incomes (
    -- Identificación
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category_id INTEGER,
    
    -- Información básica
    description VARCHAR(200) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    date DATE NOT NULL,
    
    -- Tipo
    income_type VARCHAR(20) DEFAULT 'punctual' NOT NULL,  -- 'punctual' o 'recurring'
    
    -- Recurrencia
    is_recurring BOOLEAN DEFAULT FALSE NOT NULL,
    recurrence_months INTEGER,
    start_date DATE,
    end_date DATE,
    
    -- Metadatos
    notes TEXT,
    
    -- Auditoría
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Foreign Keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES income_categories(id) ON DELETE SET NULL,
    
    -- Constraints
    CHECK (amount > 0),
    CHECK (recurrence_months IS NULL OR recurrence_months > 0)
);

-- Índices
CREATE INDEX idx_incomes_user_date ON incomes(user_id, date DESC);
CREATE INDEX idx_incomes_category ON incomes(category_id);
CREATE INDEX idx_incomes_recurring ON incomes(user_id, is_recurring) 
    WHERE is_recurring = TRUE;
```

**Uso**: Tracking de ingresos variables (freelance, bonos, dividendos, etc.).

---

### 7. `financial_snapshots` - Snapshots Financieros

```sql
CREATE TABLE financial_snapshots (
    -- Identificación
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    -- Período
    snapshot_date DATE NOT NULL,
    period_type VARCHAR(20) DEFAULT 'monthly' NOT NULL,  -- 'daily', 'monthly', 'yearly'
    
    -- Métricas calculadas (en EUR)
    total_income DECIMAL(12, 2) DEFAULT 0.00,
    total_expenses DECIMAL(12, 2) DEFAULT 0.00,
    monthly_savings DECIMAL(12, 2) DEFAULT 0.00,
    
    total_cash DECIMAL(12, 2) DEFAULT 0.00,
    total_investments DECIMAL(12, 2) DEFAULT 0.00,
    total_debt DECIMAL(12, 2) DEFAULT 0.00,
    
    net_worth DECIMAL(12, 2) DEFAULT 0.00,
    
    -- Ratios
    savings_rate DECIMAL(5, 2),  -- Porcentaje (0-100)
    debt_to_income_ratio DECIMAL(5, 2),
    
    -- Metadata
    calculation_notes TEXT,
    
    -- Auditoría
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Foreign Keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- Constraints
    UNIQUE(user_id, snapshot_date, period_type)
);

-- Índices
CREATE INDEX idx_snapshots_user_date ON financial_snapshots(user_id, snapshot_date DESC);
CREATE INDEX idx_snapshots_period ON financial_snapshots(user_id, period_type, snapshot_date DESC);
```

**Propósito**:
- Almacenar snapshots periódicos de métricas
- Generar gráficos históricos sin recalcular cada vez
- Tracking de evolución temporal

**Uso**:
```python
# Guardar snapshot mensual automáticamente
snapshot = FinancialSnapshot(
    user_id=user_id,
    snapshot_date=date.today().replace(day=1),  # Primer día del mes
    period_type='monthly',
    total_income=calculate_monthly_income(user_id),
    total_expenses=calculate_monthly_expenses(user_id),
    # ... otros campos
)
```

---

## 📋 CATEGORÍAS PREDETERMINADAS

### Categorías de Gastos (Default)
```python
DEFAULT_EXPENSE_CATEGORIES = [
    # Categorías principales
    {'name': 'Vivienda', 'description': 'Alquiler, hipoteca, IBI, comunidad'},
    {'name': 'Alimentación', 'description': 'Supermercado, restaurantes'},
    {'name': 'Transporte', 'description': 'Gasolina, transporte público, mantenimiento vehículo'},
    {'name': 'Salud', 'description': 'Seguro médico, medicinas, consultas'},
    {'name': 'Educación', 'description': 'Matrícula, libros, cursos'},
    {'name': 'Ocio', 'description': 'Entretenimiento, hobbies, vacaciones'},
    {'name': 'Servicios', 'description': 'Teléfono, internet, streaming, seguros'},
    {'name': 'Deudas', 'description': 'Préstamos, tarjetas de crédito', 'category_type': 'debt'},
    {'name': 'Otros', 'description': 'Gastos varios no categorizados'},
]

# Subcategorías (ejemplos)
SUBCATEGORIES = {
    'Alimentación': ['Supermercado', 'Restaurantes', 'Delivery'],
    'Transporte': ['Combustible', 'Mantenimiento', 'Transporte Público', 'Parking'],
    'Servicios': ['Teléfono', 'Internet', 'Streaming', 'Seguros'],
}
```

### Categorías de Ingresos (Default)
```python
DEFAULT_INCOME_CATEGORIES = [
    {'name': 'Freelance', 'description': 'Trabajos independientes'},
    {'name': 'Bonos', 'description': 'Bonos y comisiones'},
    {'name': 'Alquileres', 'description': 'Ingresos por alquiler de propiedades'},
    {'name': 'Inversiones', 'description': 'Dividendos, intereses'},
    {'name': 'Otros', 'description': 'Ingresos varios'},
]
```

---

## 🚀 SCRIPT DE INICIALIZACIÓN

### `init_db.py`

```python
"""
Script de inicialización de base de datos para MVP.
"""
from datetime import datetime
from models import db, User, ExpenseCategory, IncomeCategory
from werkzeug.security import generate_password_hash

def init_database(app):
    """Inicializa la base de datos con datos básicos"""
    with app.app_context():
        # Crear todas las tablas
        db.create_all()
        print("✅ Tablas creadas")
        
        # Verificar si ya existe el usuario admin
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # Crear usuario admin por defecto
            admin = User(
                username='admin',
                email='admin@localhost',
                password_hash=generate_password_hash('admin123'),
                is_admin=True,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Usuario admin creado (username: admin, password: admin123)")
        else:
            print("ℹ️ Usuario admin ya existe")
        
        # Crear categorías predeterminadas para admin
        create_default_categories(admin.id)
        
        print("✅ Base de datos inicializada correctamente")

def create_default_categories(user_id):
    """Crea categorías predeterminadas para un usuario"""
    
    # Categorías de gastos
    expense_categories = [
        {'name': 'Vivienda', 'description': 'Alquiler, hipoteca, IBI, comunidad'},
        {'name': 'Alimentación', 'description': 'Supermercado, restaurantes'},
        {'name': 'Transporte', 'description': 'Gasolina, transporte público'},
        {'name': 'Salud', 'description': 'Seguro médico, medicinas'},
        {'name': 'Educación', 'description': 'Matrícula, libros, cursos'},
        {'name': 'Ocio', 'description': 'Entretenimiento, hobbies'},
        {'name': 'Servicios', 'description': 'Teléfono, internet, seguros'},
        {'name': 'Deudas', 'description': 'Préstamos, tarjetas', 'category_type': 'debt'},
        {'name': 'Otros', 'description': 'Gastos varios'},
    ]
    
    for cat_data in expense_categories:
        # Verificar si ya existe
        existing = ExpenseCategory.query.filter_by(
            user_id=user_id, 
            name=cat_data['name']
        ).first()
        
        if not existing:
            category = ExpenseCategory(
                user_id=user_id,
                name=cat_data['name'],
                description=cat_data['description'],
                is_default=True,
                category_type=cat_data.get('category_type', 'expense')
            )
            db.session.add(category)
    
    # Categorías de ingresos
    income_categories = [
        {'name': 'Freelance', 'description': 'Trabajos independientes'},
        {'name': 'Bonos', 'description': 'Bonos y comisiones'},
        {'name': 'Alquileres', 'description': 'Ingresos por alquiler'},
        {'name': 'Inversiones', 'description': 'Dividendos, intereses'},
        {'name': 'Otros', 'description': 'Ingresos varios'},
    ]
    
    for cat_data in income_categories:
        existing = IncomeCategory.query.filter_by(
            user_id=user_id, 
            name=cat_data['name']
        ).first()
        
        if not existing:
            category = IncomeCategory(
                user_id=user_id,
                name=cat_data['name'],
                description=cat_data['description'],
                is_default=True
            )
            db.session.add(category)
    
    db.session.commit()
    print(f"✅ Categorías predeterminadas creadas para user_id={user_id}")

if __name__ == '__main__':
    from app import create_app
    app = create_app()
    init_database(app)
```

---

## 🔐 CONSIDERACIONES DE SEGURIDAD

### Campos Sensibles
```python
# Campos que NUNCA deben exponerse en API
SENSITIVE_FIELDS = [
    'password_hash',
    'account_number_last4',  # Solo en contextos específicos
]

# Sanitización en serializers
class UserSchema:
    exclude = ['password_hash']
    
class BankAccountSchema:
    exclude = ['account_number_last4']  # O maskear: "****1234"
```

### Encriptación (Futura)
```python
# Para datos MUY sensibles (opcional)
from cryptography.fernet import Fernet

# Encriptar saldos/transacciones (si requerido por regulación)
def encrypt_sensitive_data(data: str, key: bytes) -> str:
    f = Fernet(key)
    encrypted = f.encrypt(data.encode())
    return encrypted.decode()

def decrypt_sensitive_data(encrypted_data: str, key: bytes) -> str:
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_data.encode())
    return decrypted.decode()
```

---

## 📊 MIGRACIONES

### Alembic (Recomendado)
```bash
# Inicializar Alembic
alembic init migrations

# Crear migración automática
alembic revision --autogenerate -m "Initial tables"

# Aplicar migración
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Script de Migración Manual (SQLite)
```python
"""
Script para migrar datos del sistema antiguo al nuevo.
"""
import sqlite3
import json
from datetime import datetime

def migrate_from_old_db(old_db_path: str, new_db_path: str):
    """Migra datos del sistema antiguo al nuevo"""
    
    old_conn = sqlite3.connect(old_db_path)
    new_conn = sqlite3.connect(new_db_path)
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    print("🔄 Iniciando migración...")
    
    # 1. Migrar usuarios
    print("  → Migrando usuarios...")
    old_cursor.execute("SELECT id, username, email, password_hash, birth_year FROM user")
    users = old_cursor.fetchall()
    
    for user in users:
        new_cursor.execute("""
            INSERT INTO users (id, username, email, password_hash, birth_year, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (*user, datetime.utcnow()))
    
    print(f"    ✅ {len(users)} usuarios migrados")
    
    # 2. Migrar cuentas bancarias
    print("  → Migrando cuentas bancarias...")
    old_cursor.execute("""
        SELECT id, user_id, bank_name, account_name, current_balance 
        FROM bank_account
    """)
    accounts = old_cursor.fetchall()
    
    for account in accounts:
        new_cursor.execute("""
            INSERT INTO bank_accounts 
            (id, user_id, bank_name, account_name, current_balance, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (*account, datetime.utcnow()))
    
    print(f"    ✅ {len(accounts)} cuentas migradas")
    
    # 3. Migrar categorías de gastos
    # ... (similar para cada tabla)
    
    new_conn.commit()
    old_conn.close()
    new_conn.close()
    
    print("✅ Migración completada")

if __name__ == '__main__':
    migrate_from_old_db('old_site.db', 'new_site.db')
```

---

## 🧪 DATOS DE PRUEBA

### `seed_test_data.py`

```python
"""
Script para poblar la BD con datos de prueba.
"""
from datetime import date, timedelta
from decimal import Decimal
from models import db, User, BankAccount, Expense, Income, ExpenseCategory, IncomeCategory
from werkzeug.security import generate_password_hash
import random

def seed_test_data(app):
    """Crea datos de prueba para desarrollo"""
    with app.app_context():
        print("🌱 Sembrando datos de prueba...")
        
        # Usuario de prueba
        test_user = User(
            username='test_user',
            email='test@example.com',
            password_hash=generate_password_hash('test123'),
            birth_year=1990,
            annual_net_salary=35000.00
        )
        db.session.add(test_user)
        db.session.commit()
        
        # Crear categorías para test_user
        create_default_categories(test_user.id)
        
        # Cuenta bancaria
        account = BankAccount(
            user_id=test_user.id,
            bank_name='Banco Test',
            account_name='Cuenta Principal',
            current_balance=5000.00
        )
        db.session.add(account)
        
        # Gastos de los últimos 12 meses
        expense_cat = ExpenseCategory.query.filter_by(
            user_id=test_user.id, 
            name='Alimentación'
        ).first()
        
        for i in range(12):
            expense_date = date.today() - timedelta(days=30*i)
            expense = Expense(
                user_id=test_user.id,
                category_id=expense_cat.id,
                description=f'Supermercado mes {i+1}',
                amount=random.uniform(200, 400),
                date=expense_date,
                expense_type='punctual'
            )
            db.session.add(expense)
        
        # Ingresos
        income_cat = IncomeCategory.query.filter_by(
            user_id=test_user.id, 
            name='Freelance'
        ).first()
        
        for i in range(12):
            income_date = date.today() - timedelta(days=30*i)
            income = Income(
                user_id=test_user.id,
                category_id=income_cat.id,
                description=f'Proyecto freelance {i+1}',
                amount=random.uniform(500, 1500),
                date=income_date,
                income_type='punctual'
            )
            db.session.add(income)
        
        db.session.commit()
        print("✅ Datos de prueba creados")

if __name__ == '__main__':
    from app import create_app
    app = create_app()
    seed_test_data(app)
```

---

## 📈 ESTRATEGIA DE CRECIMIENTO

### Fase 2: Tablas Adicionales (Opcional)

```sql
-- Planes de Deuda
CREATE TABLE debt_plans (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    category_id INTEGER,
    description VARCHAR(200) NOT NULL,
    total_amount DECIMAL(12, 2) NOT NULL,
    monthly_payment DECIMAL(12, 2) NOT NULL,
    start_date DATE NOT NULL,
    duration_months INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES expense_categories(id)
);

-- Portfolio de Inversiones
CREATE TABLE portfolio_holdings (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    avg_cost DECIMAL(12, 2),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Transacciones de Inversiones
CREATE TABLE investment_transactions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    transaction_type VARCHAR(10) NOT NULL,  -- 'buy', 'sell'
    quantity DECIMAL(18, 8) NOT NULL,
    price DECIMAL(12, 2) NOT NULL,
    fees DECIMAL(12, 2),
    date DATE NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

---

## ✅ CHECKLIST DE VALIDACIÓN

### Antes de Implementar
- [ ] Revisar todas las relaciones
- [ ] Confirmar tipos de datos apropiados
- [ ] Definir todos los índices necesarios
- [ ] Documentar constraints y validaciones
- [ ] Planificar estrategia de migración
- [ ] Preparar scripts de seed data

### Durante Implementación
- [ ] Crear modelos SQLAlchemy
- [ ] Implementar validaciones en modelos
- [ ] Crear migraciones Alembic
- [ ] Tests unitarios para modelos
- [ ] Script de inicialización
- [ ] Script de seed data

### Después de Implementar
- [ ] Verificar integridad referencial
- [ ] Comprobar performance de queries
- [ ] Validar backups funcionan
- [ ] Documentar esquema final
- [ ] Crear diagrama ER

---

## 📚 RECURSOS

### Herramientas Útiles
```bash
# Visualizar esquema SQLite
sqlite3 site.db .schema

# Exportar diagrama ER (usando SchemaCrawler)
schemacrawler --server=sqlite --database=site.db --command=schema --output-format=png

# Análizar tamaño de BD
sqlite3 site.db "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();"
```

### Referencias
- SQLAlchemy ORM: https://docs.sqlalchemy.org/
- Alembic Migrations: https://alembic.sqlalchemy.org/
- Flask-SQLAlchemy: https://flask-sqlalchemy.palletsprojects.com/

---

## 🎯 CONCLUSIÓN

Este diseño de base de datos para el MVP:

✅ **Es simple**: 7 tablas vs 25+ original
✅ **Es escalable**: Estructura permite crecimiento
✅ **Es eficiente**: Índices optimizados desde el inicio
✅ **Es mantenible**: Relaciones claras y documentadas
✅ **Es completo**: Cubre todos los casos de uso core

**Próximo paso**: Implementar los modelos SQLAlchemy basados en este esquema.

¿Necesitas ayuda implementando los modelos o tienes preguntas sobre el diseño?

