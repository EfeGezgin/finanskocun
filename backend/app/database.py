try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False

import sqlite3
import re
from contextlib import contextmanager
from typing import Generator, Any, Optional, List, Dict
from app.config import MSSQL_DRIVER, MSSQL_SERVER, MSSQL_DATABASE, MSSQL_TRUSTED_CONNECTION, DB_PATH

DB_ENGINE_TYPE = "mssql"  # 'mssql' or 'sqlite'

class DictRow(dict):
    """Row object that supports both dictionary-like key lookup and index access."""
    def __init__(self, cols: List[str], values: tuple):
        super().__init__(zip(cols, values))
        self._values = values

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)

    def get(self, key: Any, default: Any = None) -> Any:
        if isinstance(key, int):
            try:
                return self._values[key]
            except IndexError:
                return default
        return super().get(key, default)

class DictCursor:
    """Wrapper around Cursor to provide dict-like rows and lastrowid support with transparent cross-engine compatibility."""
    def __init__(self, raw_cursor: Any):
        self._raw = raw_cursor
        self.lastrowid: Optional[int] = getattr(raw_cursor, 'lastrowid', None)
        self.rowcount: int = getattr(raw_cursor, 'rowcount', -1)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._raw, name)

    def execute(self, query: str, params: tuple = None) -> 'DictCursor':
        is_sqlite = isinstance(self._raw, sqlite3.Cursor)
        if is_sqlite:
            # 1. Compatibility: GETDATE() -> CURRENT_TIMESTAMP
            query = re.sub(r'\bGETDATE\(\)', 'CURRENT_TIMESTAMP', query, flags=re.IGNORECASE)

            # 2. Compatibility: SELECT TOP N -> SELECT ... LIMIT N
            top_match = re.search(r'\bSELECT\s+TOP\s+(\d+)\b', query, flags=re.IGNORECASE)
            if top_match:
                limit_num = top_match.group(1)
                query = re.sub(r'\bSELECT\s+TOP\s+\d+\s+', 'SELECT ', query, count=1, flags=re.IGNORECASE)
                if not re.search(r'\bLIMIT\b', query, flags=re.IGNORECASE):
                    query = query.rstrip().rstrip(';') + f' LIMIT {limit_num}'

            # 3. Compatibility: INSERT ... OUTPUT INSERTED.col1, INSERTED.col2 ... VALUES ...
            output_match = re.search(r'\bOUTPUT\s+(INSERTED\.[^Vv]+?)(?=\s*\bVALUES\b)', query, re.IGNORECASE | re.DOTALL)
            if output_match:
                raw_cols = output_match.group(1)
                col_names = [re.sub(r'(?i)inserted\.', '', c).strip(' []"`\'') for c in raw_cols.split(',')]
                table_match = re.search(r'\bINSERT\s+INTO\s+([^\s\(]+)', query, re.IGNORECASE)
                clean_query = query[:output_match.start()] + query[output_match.end():]

                if params is not None:
                    self._raw.execute(clean_query, params)
                else:
                    self._raw.execute(clean_query)

                self.lastrowid = getattr(self._raw, 'lastrowid', None)
                self.rowcount = getattr(self._raw, 'rowcount', 1)

                if table_match and self.lastrowid is not None:
                    table_name = table_match.group(1).strip('[]"`\'')
                    cols_sql = ', '.join(f'"{c}"' for c in col_names)
                    self._raw.execute(f'SELECT {cols_sql} FROM "{table_name}" WHERE rowid = ?', (self.lastrowid,))
                return self

        if params is not None:
            self._raw.execute(query, params)
        else:
            self._raw.execute(query)

        self.lastrowid = getattr(self._raw, 'lastrowid', None)
        self.rowcount = getattr(self._raw, 'rowcount', -1)
        return self

    def fetchone(self) -> Optional[DictRow]:
        row = self._raw.fetchone()
        if not row:
            return None
        cols = [col[0] for col in self._raw.description]
        return DictRow(cols, row)

    def fetchall(self) -> List[DictRow]:
        rows = self._raw.fetchall()
        if not rows:
            return []
        cols = [col[0] for col in self._raw.description]
        return [DictRow(cols, r) for r in rows]

class DBConnectionWrapper:
    """Wrapper around pyodbc or sqlite3 Connection to return DictCursor."""
    def __init__(self, raw_conn: Any):
        self._raw = raw_conn

    def __getattr__(self, name: str) -> Any:
        return getattr(self._raw, name)

    def cursor(self) -> DictCursor:
        return DictCursor(self._raw.cursor())

    def commit(self):
        return self._raw.commit()

    def rollback(self):
        return self._raw.rollback()

    def close(self):
        return self._raw.close()

def get_connection_string(database: Optional[str] = None) -> str:
    db = database or MSSQL_DATABASE
    return (
        f"DRIVER={{{MSSQL_DRIVER}}};"
        f"SERVER={MSSQL_SERVER};"
        f"DATABASE={db};"
        f"Trusted_Connection={MSSQL_TRUSTED_CONNECTION};"
    )

def ensure_database_exists():
    """Ensures SmartFinanceDB database exists in MSSQL or SQLite directory exists."""
    global DB_ENGINE_TYPE
    if not HAS_PYODBC:
        DB_ENGINE_TYPE = "sqlite"
        return
    try:
        master_conn_str = get_connection_string("master")
        with pyodbc.connect(master_conn_str, autocommit=True, timeout=2) as conn:
            cursor = conn.cursor()
            cursor.execute(f"IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '{MSSQL_DATABASE}') CREATE DATABASE [{MSSQL_DATABASE}]")
        DB_ENGINE_TYPE = "mssql"
    except Exception as e:
        print(f"MSSQL not reachable, switching to SQLite engine: {e}")
        DB_ENGINE_TYPE = "sqlite"

def get_connection() -> DBConnectionWrapper:
    """Returns an active DB connection wrapped in DBConnectionWrapper (MSSQL or SQLite)."""
    global DB_ENGINE_TYPE
    if DB_ENGINE_TYPE == "mssql" and HAS_PYODBC:
        try:
            raw = pyodbc.connect(get_connection_string(), timeout=2)
            return DBConnectionWrapper(raw)
        except Exception:
            DB_ENGINE_TYPE = "sqlite"
    
    # SQLite connection fallback
    raw = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    return DBConnectionWrapper(raw)

@contextmanager
def get_db() -> Generator[DBConnectionWrapper, None, None]:
    """Context manager for safe transactional database operations."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_sqlite_tables(cursor):
    """Initializes schema in SQLite."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0,
        plan TEXT NOT NULL DEFAULT 'free',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        currency TEXT NOT NULL DEFAULT 'TRY',
        balance REAL NOT NULL DEFAULT 0.0,
        exchange_rate REAL NOT NULL DEFAULT 1.0,
        is_active_cash INTEGER NOT NULL DEFAULT 1,
        bank_name TEXT,
        bank_code TEXT,
        account_number TEXT,
        color TEXT DEFAULT '#10b981',
        icon TEXT DEFAULT 'wallet',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS credit_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        bank_name TEXT NOT NULL,
        bank_code TEXT,
        card_name TEXT NOT NULL,
        total_limit REAL NOT NULL,
        current_debt REAL NOT NULL DEFAULT 0.0,
        statement_debt REAL NOT NULL DEFAULT 0.0,
        installment_debt REAL NOT NULL DEFAULT 0.0,
        cutoff_day INTEGER NOT NULL,
        due_day INTEGER NOT NULL,
        min_payment_rate REAL DEFAULT 0.20,
        interest_rate REAL DEFAULT 4.25,
        color TEXT DEFAULT '#6366f1',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS credit_card_statements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        credit_card_id INTEGER NOT NULL REFERENCES credit_cards(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        period TEXT NOT NULL,
        statement_date TEXT,
        due_date TEXT,
        statement_amount REAL NOT NULL,
        min_payment_amount REAL DEFAULT 0.0,
        paid_amount REAL DEFAULT 0.0,
        remaining_debt REAL DEFAULT 0.0,
        interest_rate REAL DEFAULT 4.25,
        status TEXT DEFAULT 'unpaid',
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        bank_name TEXT NOT NULL,
        bank_code TEXT,
        loan_title TEXT NOT NULL,
        total_amount REAL NOT NULL,
        monthly_installment REAL NOT NULL,
        remaining_installments INTEGER NOT NULL,
        total_installments INTEGER NOT NULL,
        due_day INTEGER NOT NULL,
        interest_rate REAL DEFAULT 0.0,
        color TEXT DEFAULT '#f59e0b',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recurring_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        type TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        day_of_month INTEGER NOT NULL,
        account_id INTEGER,
        is_active INTEGER DEFAULT 1,
        notes TEXT
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        date TEXT NOT NULL,
        type TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'cash',
        account_id INTEGER,
        credit_card_id INTEGER,
        is_nlp_generated INTEGER DEFAULT 0,
        raw_input TEXT,
        emotion_tag TEXT DEFAULT 'essential',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Column migration for emotion_tag if table existed earlier
    try:
        cursor.execute("ALTER TABLE transactions ADD COLUMN emotion_tag TEXT DEFAULT 'essential';")
    except Exception:
        pass

    # Category Budgets Table (Module 1)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS category_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        category TEXT NOT NULL,
        monthly_limit REAL NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, category)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_pairings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        platform TEXT NOT NULL DEFAULT 'telegram',
        bot_user_id TEXT NOT NULL,
        pairing_code TEXT,
        is_verified INTEGER NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(platform, bot_user_id)
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        platform TEXT,
        sender_id TEXT,
        message_text TEXT,
        reply_text TEXT,
        status TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'info',
        is_read INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)


def init_db():
    """Initializes all Microsoft SQL Server database tables with strict multi-user foreign keys and indexes."""
    ensure_database_exists()
    
    with get_db() as conn:
        cursor = conn.cursor()
        if DB_ENGINE_TYPE == "sqlite":
            init_sqlite_tables(cursor)
            return

        # 0. Users Table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' AND xtype='U')
        CREATE TABLE users (
            id INT IDENTITY(1,1) PRIMARY KEY,
            email NVARCHAR(255) UNIQUE NOT NULL,
            password_hash NVARCHAR(255) NOT NULL,
            full_name NVARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT GETDATE()
        );
        """)

        # Ensure is_admin and plan columns exist
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'is_admin')
        ALTER TABLE users ADD is_admin BIT NOT NULL DEFAULT 0;
        """)
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'plan')
        ALTER TABLE users ADD [plan] NVARCHAR(50) NOT NULL DEFAULT 'free';
        """)

        # 0.1 Sessions Table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='user_sessions' AND xtype='U')
        CREATE TABLE user_sessions (
            token NVARCHAR(128) PRIMARY KEY,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE,
            created_at DATETIME DEFAULT GETDATE()
        );
        """)

        # 1. Accounts Table (Strict user_id NOT NULL)
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='accounts' AND xtype='U')
        CREATE TABLE accounts (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE,
            name NVARCHAR(150) NOT NULL,
            type NVARCHAR(50) NOT NULL,
            currency NVARCHAR(10) NOT NULL DEFAULT 'TRY',
            balance FLOAT NOT NULL DEFAULT 0.0,
            exchange_rate FLOAT NOT NULL DEFAULT 1.0,
            is_active_cash BIT NOT NULL DEFAULT 1,
            bank_name NVARCHAR(100),
            bank_code NVARCHAR(50),
            account_number NVARCHAR(50),
            color NVARCHAR(30) DEFAULT '#10b981',
            icon NVARCHAR(50) DEFAULT 'wallet',
            updated_at DATETIME DEFAULT GETDATE()
        );
        """)

        # 2. Credit Cards Table (Strict user_id NOT NULL)
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='credit_cards' AND xtype='U')
        CREATE TABLE credit_cards (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE,
            bank_name NVARCHAR(100) NOT NULL,
            bank_code NVARCHAR(50),
            card_name NVARCHAR(100) NOT NULL,
            total_limit FLOAT NOT NULL,
            current_debt FLOAT NOT NULL DEFAULT 0.0,
            statement_debt FLOAT NOT NULL DEFAULT 0.0,
            installment_debt FLOAT NOT NULL DEFAULT 0.0,
            cutoff_day INT NOT NULL,
            due_day INT NOT NULL,
            min_payment_rate FLOAT DEFAULT 0.20,
            interest_rate FLOAT DEFAULT 4.25,
            color NVARCHAR(30) DEFAULT '#6366f1',
            created_at DATETIME DEFAULT GETDATE()
        );
        """)

        # 2.1 Credit Card Statements History Table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='credit_card_statements' AND xtype='U')
        CREATE TABLE credit_card_statements (
            id INT IDENTITY(1,1) PRIMARY KEY,
            credit_card_id INT NOT NULL FOREIGN KEY REFERENCES credit_cards(id) ON DELETE CASCADE,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(id),
            period NVARCHAR(50) NOT NULL,
            statement_date NVARCHAR(30),
            due_date NVARCHAR(30),
            statement_amount FLOAT NOT NULL,
            min_payment_amount FLOAT DEFAULT 0.0,
            paid_amount FLOAT DEFAULT 0.0,
            remaining_debt FLOAT DEFAULT 0.0,
            interest_rate FLOAT DEFAULT 4.25,
            status NVARCHAR(30) DEFAULT 'unpaid',
            notes NVARCHAR(500),
            created_at DATETIME DEFAULT GETDATE()
        );
        """)

        # 3. Loans Table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='loans' AND xtype='U')
        CREATE TABLE loans (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE,
            bank_name NVARCHAR(100) NOT NULL,
            bank_code NVARCHAR(50),
            loan_title NVARCHAR(150) NOT NULL,
            total_amount FLOAT NOT NULL,
            monthly_installment FLOAT NOT NULL,
            remaining_installments INT NOT NULL,
            total_installments INT NOT NULL,
            due_day INT NOT NULL,
            interest_rate FLOAT DEFAULT 0.0,
            color NVARCHAR(30) DEFAULT '#f59e0b',
            created_at DATETIME DEFAULT GETDATE()
        );
        """)

        # 4. Recurring Items Table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='recurring_items' AND xtype='U')
        CREATE TABLE recurring_items (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE,
            title NVARCHAR(150) NOT NULL,
            type NVARCHAR(20) NOT NULL,
            category NVARCHAR(50) NOT NULL,
            amount FLOAT NOT NULL,
            day_of_month INT NOT NULL,
            account_id INT,
            is_active BIT DEFAULT 1,
            notes NVARCHAR(500)
        );
        """)

        # 5. Transactions Table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='transactions' AND xtype='U')
        CREATE TABLE transactions (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE,
            date NVARCHAR(30) NOT NULL,
            type NVARCHAR(20) NOT NULL,
            category NVARCHAR(50) NOT NULL,
            amount FLOAT NOT NULL,
            description NVARCHAR(500) NOT NULL,
            payment_method NVARCHAR(50) NOT NULL DEFAULT 'cash',
            account_id INT,
            credit_card_id INT,
            is_nlp_generated BIT DEFAULT 0,
            raw_input NVARCHAR(1000),
            emotion_tag NVARCHAR(50) DEFAULT 'essential',
            created_at DATETIME DEFAULT GETDATE()
        );
        """)

        # Column migration for emotion_tag in MSSQL
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'transactions' AND COLUMN_NAME = 'emotion_tag')
        ALTER TABLE transactions ADD emotion_tag NVARCHAR(50) DEFAULT 'essential';
        """)

        # 5.1 Category Budgets Table (MSSQL)
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='category_budgets' AND xtype='U')
        CREATE TABLE category_budgets (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE,
            category NVARCHAR(50) NOT NULL,
            monthly_limit FLOAT NOT NULL,
            created_at DATETIME DEFAULT GETDATE(),
            CONSTRAINT UQ_user_category UNIQUE (user_id, category)
        );
        """)

        # 6. AI Chat & Financial Memory Table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='ai_chat_history' AND xtype='U')
        CREATE TABLE ai_chat_history (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE,
            role NVARCHAR(50) NOT NULL,
            message NVARCHAR(MAX) NOT NULL,
            created_at DATETIME DEFAULT GETDATE()
        );
        """)

        # 7. App Settings Table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='app_settings' AND xtype='U')
        CREATE TABLE app_settings (
            [key] NVARCHAR(100) PRIMARY KEY,
            [value] NVARCHAR(MAX) NOT NULL
        );
        """)

        # 8. Bot Pairings Table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='bot_pairings' AND xtype='U')
        CREATE TABLE bot_pairings (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE,
            platform NVARCHAR(50) NOT NULL DEFAULT 'telegram',
            bot_user_id NVARCHAR(100) NOT NULL,
            pairing_code NVARCHAR(50),
            is_verified BIT NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT GETDATE(),
            CONSTRAINT UQ_bot_platform_user UNIQUE (platform, bot_user_id)
        );
        """)

        # 9. Bot Logs Table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='bot_logs' AND xtype='U')
        CREATE TABLE bot_logs (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT,
            platform NVARCHAR(50),
            sender_id NVARCHAR(100),
            message_text NVARCHAR(MAX),
            reply_text NVARCHAR(MAX),
            status NVARCHAR(50),
            created_at DATETIME DEFAULT GETDATE()
        );
        """)

        # 10. Notifications Table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='notifications' AND xtype='U')
        CREATE TABLE notifications (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(id) ON DELETE CASCADE,
            title NVARCHAR(255) NOT NULL,
            message NVARCHAR(MAX) NOT NULL,
            type NVARCHAR(50) NOT NULL DEFAULT 'info',
            is_read BIT NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT GETDATE()
        );
        """)

        # Indexes for fast user queries
        cursor.execute("IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_accounts_user') CREATE INDEX idx_accounts_user ON accounts(user_id);")
        cursor.execute("IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_cards_user') CREATE INDEX idx_cards_user ON credit_cards(user_id);")
        cursor.execute("IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_loans_user') CREATE INDEX idx_loans_user ON loans(user_id);")
        cursor.execute("IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_trans_user_date') CREATE INDEX idx_trans_user_date ON transactions(user_id, date);")
        cursor.execute("IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_stmts_user') CREATE INDEX idx_stmts_user ON credit_card_statements(user_id);")
        cursor.execute("IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_ai_user') CREATE INDEX idx_ai_user ON ai_chat_history(user_id);")
        cursor.execute("IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_budgets_user') CREATE INDEX idx_budgets_user ON category_budgets(user_id);")
        cursor.execute("IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_notif_user') CREATE INDEX idx_notif_user ON notifications(user_id, is_read);")

def reset_all_data(user_id: int):
    """Completely resets all financial figures, cards, statements, and transactions for the specified user."""
    if not user_id:
        return
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM category_budgets WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM credit_card_statements WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM recurring_items WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM credit_cards WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM loans WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM accounts WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM ai_chat_history WHERE user_id = ?", (user_id,))
