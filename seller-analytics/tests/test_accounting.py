import unittest
import tempfile
from pathlib import Path
from engine import money, ratio, select_cost, summarize, return_entries
from store import connect, entries, put_entries
from server import validate_cost_csv

class AccountingTests(unittest.TestCase):
    def test_money_decimal_and_invalid(self):
        self.assertEqual(money('1 234,56'),123456)
        self.assertEqual(money('0.105'),11)
        for value in ['NaN','Infinity','wrong']:
            with self.assertRaises(ValueError): money(value)

    def test_tax_and_missing_costs_never_imply_net_profit(self):
        rows=[dict(kind='sale',amount=100000),dict(kind='cogs',amount=-40000),
              dict(kind='ads',amount=-10000),dict(kind='tax',amount=-5000)]
        self.assertIsNone(summarize(rows)['net_profit'])
        self.assertIsNone(summarize(rows,tax_complete=True,costs_complete=False)['net_profit'])
        self.assertEqual(summarize(rows,tax_complete=True)['net_profit'],45000)

    def test_return_next_month_restores_only_resellable_cost(self):
        sale=dict(account_id='wb-1',sku='A')
        rows=return_entries(sale,100000,40000,True,'2026-10-02','return1')
        self.assertEqual(summarize(rows)['pre_tax_profit'],-60000)
        rows=return_entries(sale,100000,40000,False,'2026-10-02','return1')
        self.assertEqual(summarize(rows)['pre_tax_profit'],-100000)

    def test_historical_cost(self):
        history=[dict(effective_from='2026-09-01',unit_cost=500),dict(effective_from='2026-10-01',unit_cost=900)]
        self.assertEqual(select_cost(history,'2026-09-30'),500)
        self.assertIsNone(select_cost(history,'2026-08-31'))

    def test_ratio_zero_and_negative_base(self):
        self.assertIsNone(ratio(1,0))
        self.assertIsNone(ratio(1,-5))
        self.assertEqual(ratio(25,100),25)

    def test_unknown_financial_category_is_not_silently_ignored(self):
        with self.assertRaises(ValueError):
            summarize([dict(kind='new_marketplace_fee',amount=-10000)])

    def test_csv_rejects_invalid_history_before_writing(self):
        valid=validate_cost_csv('sku;effective_from;cost_rub\nA;2026-09-01;23,50\n')
        self.assertEqual(valid,[('A','2026-09-01',2350)])
        for content in ['sku;effective_from;cost_rub\nA;2026-09-01;-1',
            'sku;effective_from;cost_rub\nA;2026-09-01;1\nA;2026-09-01;2',
            'sku;effective_from;cost_rub\nA;2026-13-01;1']:
            with self.assertRaises(ValueError): validate_cost_csv(content)

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=connect(Path(self.temp.name)/'test.db')
    def tearDown(self):
        self.db.close(); self.temp.cleanup()
    def test_repeat_ingestion_and_correction(self):
        row=dict(source_id='1',account_id='wb-1',sku='A',day='2026-09-01',kind='sale',amount=100)
        put_entries(self.db,'one','api',[row]);put_entries(self.db,'one','api',[row])
        found=entries(self.db,'one','2026-09-01','2026-09-30')
        self.assertEqual(len(found),1)
        put_entries(self.db,'one','api',[dict(row,amount=200)])
        self.assertEqual(entries(self.db,'one','2026-09-01','2026-09-30')[0]['amount'],200)
    def test_account_and_tenant_filters(self):
        row=dict(source_id='1',account_id='wb-1',day='2026-09-01',kind='sale',amount=100)
        put_entries(self.db,'demo','api',[row,dict(row,account_id='ozon-1')])
        self.assertEqual(entries(self.db,'local','2026-09-01','2026-09-30'),[])
        self.assertEqual(len(entries(self.db,'demo','2026-09-01','2026-09-30','wb-1')),1)

if __name__=='__main__':unittest.main()
