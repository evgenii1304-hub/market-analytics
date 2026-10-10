#!/usr/bin/env python3
"""Loopback-only single-user development server. Not a production deployment."""
import csv
import io
import json
import os
import secrets
import uuid
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from engine import money, ratio, summarize
from store import connect, entries, put_entries, audit
from demo import ACCOUNTS, PRODUCTS, seed

ROOT = Path(__file__).resolve().parent
DB_PATH = os.environ.get('SELLER_DB_PATH', str(ROOT / '.runtime' / 'analytics.sqlite3'))
CSRF = secrets.token_urlsafe(32)
KINDS = {'overhead': 'Операционные расходы', 'other': 'Прочие расходы', 'ads': 'Реклама'}

def validate_cost_csv(content):
    reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')), delimiter=';' if ';' in content.splitlines()[0] else ',')
    if not reader.fieldnames or set(reader.fieldnames) != {'sku', 'effective_from', 'cost_rub'}:
        raise ValueError('Нужны столбцы sku, effective_from, cost_rub')
    result, seen = [], set()
    for n, row in enumerate(reader, 2):
        if n > 10002:
            raise ValueError('Не более 10 000 строк')
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'Строка {n}: неверное число столбцов')
        sku = row['sku'].strip()
        if not sku or len(sku) > 120:
            raise ValueError(f'Строка {n}: неверный артикул')
        day = date.fromisoformat(row['effective_from'].strip()).isoformat()
        cost = money(row['cost_rub'])
        if cost < 0:
            raise ValueError(f'Строка {n}: себестоимость не может быть отрицательной')
        if (sku, day) in seen:
            raise ValueError(f'Строка {n}: повтор артикула и даты')
        seen.add((sku, day))
        result.append((sku, day, cost))
    if not result:
        raise ValueError('Файл не содержит строк')
    return result

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def allowed(self):
        # Prevent DNS rebinding; refuse cross-origin requests even on loopback.
        port = self.server.server_port
        allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
        origin = self.headers.get('Origin')
        return self.headers.get('Host') in allowed and (not origin or origin in {'http://' + h for h in allowed})

    def reply(self, payload, status=200, content_type='application/json; charset=utf-8', filename=None):
        data = json.dumps(payload, ensure_ascii=False).encode() if content_type.startswith('application/json') else payload
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def context(self, query):
        mode = query.get('mode', ['demo'])[0]
        if mode not in ('demo', 'local'):
            raise ValueError('Неизвестный режим')
        start = date.fromisoformat(query.get('start', ['2026-09-01'])[0]).isoformat()
        end = date.fromisoformat(query.get('end', ['2026-09-30'])[0]).isoformat()
        if start > end:
            raise ValueError('Начало периода позже окончания')
        account = query.get('account', [''])[0]
        if account and account not in {a['id'] for a in ACCOUNTS}:
            raise ValueError('Неизвестный кабинет')
        return mode, start, end, account

    def do_GET(self):
        if not self.allowed():
            return self.reply({'error': 'Доступ разрешён только локально'}, 403)
        parsed = urlparse(self.path)
        try:
            if parsed.path == '/api/state' or parsed.path == '/api/export':
                tenant, start, end, account = self.context(parse_qs(parsed.query))
                db = connect(DB_PATH)
                try:
                    rows = entries(db, tenant, start, end, account)
                    cost_rows = [dict(r) for r in db.execute('SELECT * FROM costs WHERE tenant=? ORDER BY sku,effective_from DESC', (tenant,))]
                finally:
                    db.close()
                if parsed.path == '/api/export':
                    buffer = io.StringIO()
                    writer = csv.writer(buffer, delimiter=';')
                    writer.writerow(['mode', 'day', 'account', 'sku', 'kind', 'amount_rub', 'source', 'source_id'])
                    for row in rows:
                        fields = [tenant, row['day'], row['account_id'], row['sku'] or '', row['kind'], f"{row['amount']/100:.2f}", row['source'], row['source_id']]
                        writer.writerow([("'"+v) if isinstance(v,str) and v.startswith(('=', '+', '@', '\t', '\r', '-')) else v for v in fields])
                    return self.reply(('\ufeff'+buffer.getvalue()).encode(), content_type='text/csv; charset=utf-8', filename=f'{tenant}-operations.csv')
                products = []
                for sku, name, category, price, cost in PRODUCTS if tenant == 'demo' else []:
                    subset = [r for r in rows if r['sku'] == sku]
                    products.append(dict(sku=sku, name=name, category=category, **summarize(subset)))
                trends = []
                for day in sorted({r['day'] for r in rows}):
                    trends.append(dict(day=day, **summarize([r for r in rows if r['day']==day])))
                campaigns = []
                if tenant == 'demo':
                    for a in ACCOUNTS:
                        for i, (sku, name, *_rest) in enumerate(PRODUCTS):
                            spend = -sum(r['amount'] for r in rows if r['account_id']==a['id'] and r['sku']==sku and r['kind']=='ads')
                            if not spend:
                                continue
                            attributed = spend * (2 + i % 5)
                            clicks = max(1, spend // 2300)
                            campaigns.append(dict(name=name, account=a['name'], spend=spend, attributed=attributed,
                                clicks=clicks, orders=clicks//8, roas=ratio(attributed, spend, False), drr=ratio(spend, attributed)))
                return self.reply(dict(mode=tenant, csrf=CSRF, accounts=ACCOUNTS, summary=summarize(rows, costs_complete=tenant=='demo'),
                    products=products, campaigns=campaigns, trends=trends, entries=rows[:250], total_entries=len(rows),
                    cost_history=cost_rows, start=start, end=end,
                    limitations=['Налоговые профили не настроены', 'Маркетплейсы не подключены',
                                 'Привязка кабинетов к юрлицам не задана']))
            files = {'/': ('index.html','text/html'), '/app.js': ('app.js','text/javascript'), '/style.css': ('style.css','text/css')}
            if parsed.path not in files:
                return self.reply({'error':'Не найдено'}, 404)
            filename, mime = files[parsed.path]
            return self.reply((ROOT/'static'/filename).read_bytes(), content_type=mime+'; charset=utf-8')
        except (ValueError, IndexError) as exc:
            return self.reply({'error':str(exc)}, 400)

    def do_POST(self):
        if not self.allowed() or not secrets.compare_digest(self.headers.get('X-CSRF-Token',''), CSRF):
            return self.reply({'error':'Недопустимый запрос'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2_000_000:
                raise ValueError('Пустой или слишком большой запрос')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Ожидается объект JSON')
            tenant = body.get('mode')
            if tenant not in ('demo', 'local'):
                raise ValueError('Неизвестный режим')
            db = connect(DB_PATH)
            try:
                with db:
                    if self.path == '/api/expenses':
                        account = body.get('account_id')
                        if account not in {a['id'] for a in ACCOUNTS}:
                            raise ValueError('Выберите кабинет')
                        day = date.fromisoformat(body['day']).isoformat()
                        amount = money(body['amount'])
                        if amount <= 0:
                            raise ValueError('Расход должен быть больше нуля')
                        kind = body.get('kind')
                        if kind not in KINDS:
                            raise ValueError('Неизвестная статья')
                        note = str(body.get('note', '')).strip()
                        if not note or len(note) > 500:
                            raise ValueError('Добавьте описание до 500 символов')
                        source_id = str(uuid.UUID(body['request_id']))
                        put_entries(db, tenant, 'manual', [dict(account_id=account, day=day, kind=kind,
                                    amount=-amount, note=note, source_id=source_id)])
                        audit(db, tenant, 'expense.upsert', {'source_id':source_id, 'amount':amount})
                        db.commit()
                        return self.reply({'ok':True})
                    if self.path == '/api/costs/import':
                        validated = validate_cost_csv(body.get('csv',''))
                        for sku, day, cost in validated:
                            db.execute('''INSERT INTO costs VALUES(?,?,?,?) ON CONFLICT(tenant,sku,effective_from)
                                DO UPDATE SET unit_cost=excluded.unit_cost''', (tenant, sku, day, cost))
                        audit(db, tenant, 'cost.import', {'rows':len(validated)})
                        db.commit()
                        return self.reply({'ok':True, 'count':len(validated)})
                    return self.reply({'error':'Не найдено'}, 404)
            finally:
                db.close()
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            return self.reply({'error':str(exc)}, 400)

if __name__ == '__main__':
    db = connect(DB_PATH)
    seed(db)
    db.close()
    port = int(os.environ.get('SELLER_PORT', '8765'))
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'Local: http://127.0.0.1:{port} — local development only', flush=True)
    server.serve_forever()
