"""Synthetic fixtures. No actual seller data or inferred business figures."""
from datetime import date, timedelta
from random import Random
from store import put_entries

ACCOUNTS = [dict(id='wb-1', name='Wildberries · 01', platform='WB')] + [
    dict(id='ozon-' + str(i), name='Ozon · 0' + str(i), platform='Ozon') for i in range(1, 5)]
PRODUCTS = [
    ('HOME-001', 'Набор контейнеров', 'Дом и кухня', 159000, 57000),
    ('TEXT-002', 'Плед хлопковый', 'Текстиль', 249000, 99000),
    ('KIT-003', 'Подарочный набор', 'Наборы', 329000, 145000),
    ('HOME-004', 'Органайзер', 'Дом и кухня', 89000, 35000),
    ('PROD-005', 'Свеча ручной работы', 'Производство', 119000, 37000),
    ('ACC-006', 'Дорожная косметичка', 'Аксессуары', 79000, 46000),
    ('TEXT-007', 'Набор полотенец', 'Текстиль', 189000, 69000),
    ('HOME-008', 'Подставка для книг', 'Дом и кухня', 139000, 49000),
]

def seed(db):
    rng = Random(140)
    rows = []
    for day_index in range(30):
        day = (date(2026, 9, 1) + timedelta(days=day_index)).isoformat()
        for account in ACCOUNTS:
            for sku, name, category, price, cost in PRODUCTS:
                qty = rng.randint(0, 4)
                revenue = price * qty
                base = dict(account_id=account['id'], sku=sku, day=day)
                amounts = dict(sale=revenue, cogs=-cost*qty,
                    commission=-round(revenue*.19), logistics=-14500*qty,
                    storage=-rng.randint(50, 250), ads=-round(revenue * (.28 if sku=='ACC-006' else .085)))
                if qty and rng.random() < .1:
                    amounts['refund'] = -price
                    amounts['cogs'] += cost
                for kind, amount in amounts.items():
                    if amount:
                        rows.append(dict(base, source_id=f'{day}:{sku}:{kind}', kind=kind,
                                         amount=amount, note='Синтетический пример'))
    put_entries(db, 'demo', 'synthetic', rows)
    db.commit()

def campaigns(selected=None):
    result = []
    for i, account in enumerate(ACCOUNTS):
        if selected and selected != account['id']:
            continue
        for j, product in enumerate(PRODUCTS[:3]):
            spend = (i+2)*(j+1)*89000
            sales = spend * (3+j)
            result.append(dict(account_id=account['id'], name=product[1] + ' · пример',
                platform=account['platform'], spend=spend, attributed_sales=sales,
                clicks=220*(j+1), orders=27*(j+1), roas=sales/spend,
                drr=round(spend/sales*100, 1)))
    return result
