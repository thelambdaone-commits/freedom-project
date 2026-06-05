CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER REFERENCES users(telegram_id),
    service TEXT NOT NULL,
    encrypted_data BLOB NOT NULL,
    scopes TEXT,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    api_key_encrypted BLOB NOT NULL,
    base_url TEXT,
    status TEXT DEFAULT 'active',
    source TEXT DEFAULT 'manual',
    model_capabilities TEXT,
    rate_limit_rpm INTEGER,
    last_validated TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER REFERENCES users(telegram_id),
    domain TEXT NOT NULL UNIQUE,
    extension TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    registered_at TIMESTAMP,
    expires_at TIMESTAMP,
    nameservers TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER REFERENCES users(telegram_id),
    service TEXT NOT NULL,
    session_data BLOB,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS provider_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL UNIQUE,
    signup_url TEXT,
    requires_phone BOOLEAN DEFAULT 0,
    requires_credit_card BOOLEAN DEFAULT 0,
    free_models TEXT,
    rate_limits TEXT,
    registered BOOLEAN DEFAULT 0,
    last_registered TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
