import unittest
from monitor import Catalog, Vendors, changes

class MonitorTests(unittest.TestCase):
    def test_vendor_scope_and_decimal(self):
        p = Vendors()
        p.feed('<li data-id="9" data-qty="999" data-price="8"></li><ul id="item_partners"><li data-id="2465" data-qty="271" data-price="1.48">Partner</li></ul>')
        self.assertEqual(p.rows, {'2465': {'stock':271,'price':1.48}})
    def test_product_and_vendor_independent(self):
        a = {'1:2': {'stock':3,'price':1}, '2:2':{'stock':4,'price':2}}
        b = {'1:2': {'stock':2,'price':1}, '2:2':{'stock':4,'price':2}}
        self.assertEqual([x['key'] for x in changes(a,b)], ['1:2'])
    def test_catalog(self):
        p = Catalog(); p.feed('<div class="soc-body x" data-id="1" data-qty="3"><a href="/en/item/test-1">Test</a></div>')
        self.assertEqual(p.items['1']['total'], 3)

if __name__ == '__main__': unittest.main()
