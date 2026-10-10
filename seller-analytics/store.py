import sqlite3
import json
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent / '.runtime' / 'analytics.sqlite3'

def connect(path=DEFAULT_DB):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.executescript('''
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS entries (
      tenant TEXT NOT NULL, source TEXT NOT NULL, source_id TEXT NOT NULL,
      account_id TEXT NOT NULL, sku TEXT, day TEXT NOT NULL,
      kind TEXT NOT NULL, amount INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '',
      PRIMARY KEY(tenant, account_id, source, source_id)
    );
    CREATE TABLE IF NOT EXISTS costs (
      tenant TEXT NOT NULL, sku TEXT NOT NULL, effective_from TEXT NOT NULL,
      unit_cost INTEGER NOT NULL, PRIMARY KEY(tenant, sku, effective_from)
    );
    CREATE TABLE IF NOT EXISTS audit (
      id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, event TEXT NOT NULL,
      details TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    return db

def put_entries(db, tenant, source, rows):
    for row in rows:
        db.execute('''INSERT INTO entries
          (tenant, source, source_id, account_id, sku, day, kind, amount, note)
          VALUES (?,?,?,?,?,?,?,?,?)
          ON CONFLICT(tenant, account_id, source, source_id) DO UPDATE SET
          sku=excluded.sku, day=excluded.day, kind=excluded.kind,
          amount=excluded.amount, note=excluded.note''',
          (tenant, source, row['source_id'], row['account_id'], row.get('sku'),
           row['day'], row['kind'], row['amount'], row.get('note', '')))

def audit(db, tenant, event, details):
    db.execute('INSERT INTO audit(tenant,event,details) VALUES(?,?,?)',
               (tenant, event, json.dumps(details, ensure_ascii=False)))

def entries(db, tenant, start, end, account=None):
    sql = 'SELECT * FROM entries WHERE tenant=? AND day>=? AND day<=?'
    args = [tenant, start, end]
    if account:
        sql += ' AND account_id=?'
        args.append(account)
    return [dict(row) for row in db.execute(sql + ' ORDER BY day DESC, source_id', args)]
