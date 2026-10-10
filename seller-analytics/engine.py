"""Deterministic management-accounting primitives; amounts are integer kopecks."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date

COST_KINDS = ('cogs', 'commission', 'logistics', 'storage', 'ads', 'other', 'overhead')

def money(value):
    try:
        amount = Decimal(str(value).replace(' ', '').replace(',', '.'))
        if not amount.is_finite() or abs(amount) > Decimal('100000000000'):
            raise ValueError('Недопустимая сумма')
        return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError):
        raise ValueError('Введите сумму в рублях')

def ratio(numerator, denominator, percent=True):
    if denominator <= 0:
        return None
    return round(numerator / denominator * (100 if percent else 1), 2)

def select_cost(history, day):
    """Cost effective on sale date, never today's replacement cost."""
    date.fromisoformat(day)
    candidates = [row for row in history if row['effective_from'] <= day]
    return max(candidates, key=lambda row: row['effective_from'])['unit_cost'] if candidates else None

def summarize(entries, *, tax_complete=False, costs_complete=True):
    totals = {}
    for row in entries:
        if row['kind'] not in COST_KINDS + ('sale', 'refund', 'compensation', 'tax'):
            raise ValueError('Неизвестная финансовая статья: ' + str(row['kind']))
        totals[row['kind']] = totals.get(row['kind'], 0) + row['amount']
    revenue = totals.get('sale', 0) + totals.get('refund', 0)
    costs = sum(totals.get(kind, 0) for kind in COST_KINDS)
    pre_tax = revenue + totals.get('compensation', 0) + costs
    tax = totals.get('tax', 0)
    return {
        'revenue': revenue, 'gross_sales': totals.get('sale', 0),
        'refunds': -totals.get('refund', 0), 'costs': -costs,
        'ad_spend': -totals.get('ads', 0), 'pre_tax_profit': pre_tax,
        'net_profit': pre_tax + tax if tax_complete and costs_complete else None,
        'margin_before_tax': ratio(pre_tax, revenue),
        'drr_total': ratio(-totals.get('ads', 0), revenue),
        'return_on_cost_before_tax': ratio(pre_tax, -costs),
        'totals': totals,
    }

def return_entries(sale, refund_amount, returned_cost, resellable, day, source_id):
    """Refund is negative revenue; only resellable goods restore inventory cost."""
    if refund_amount < 0 or returned_cost < 0:
        raise ValueError('Суммы возврата должны быть положительными')
    base = dict(account_id=sale['account_id'], sku=sale['sku'], day=day)
    rows = [dict(base, source_id=source_id + ':refund', kind='refund', amount=-refund_amount)]
    if resellable:
        rows.append(dict(base, source_id=source_id + ':cogs', kind='cogs', amount=returned_cost))
    return rows
