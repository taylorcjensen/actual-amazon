import unittest

from bs4 import BeautifulSoup
from amazonorders.conf import AmazonOrdersConfig
from amazonorders.exception import AmazonOrdersError

from amazon_order import RecoverableOrder


ORDER_ID = "111-1111111-1111111"


class RecoverableOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = AmazonOrdersConfig(data={
            "order_class": "amazon_order.RecoverableOrder",
            "selectors_class": "amazon_order.AmazonSelectors",
        })

    def make_order(self, markup, *, full_details=False, clone=None):
        tag = BeautifulSoup(markup, "html.parser").div
        return RecoverableOrder(tag, self.config, full_details=full_details, clone=clone)

    def test_missing_history_total_is_recovered_from_details(self):
        history = self.make_order(
            f'<div class="order-card"><span data-component="orderId">Order # {ORDER_ID}</span>'
            '<div class="order-header"><div class="a-col-left">'
            '<div class="a-span9">Ship to</div></div></div></div>'
        )
        details = self.make_order(
            '<div id="orderDetails"><div class="order-header"><div class="a-col-left">'
            '<div class="a-span9">Total $12.34</div></div></div></div>',
            full_details=True,
            clone=history,
        )

        self.assertIsNone(history.grand_total)
        self.assertEqual(details.grand_total, 12.34)

    def test_valid_history_total_is_preserved(self):
        history = self.make_order(
            f'<div class="order-card"><span data-component="orderId">Order # {ORDER_ID}</span>'
            '<div class="yohtmlc-order-total"><span class="value">$12.34</span></div></div>'
        )
        details = self.make_order(
            '<div id="orderDetails"></div>', full_details=True, clone=history
        )

        self.assertEqual(details.grand_total, 12.34)

    def test_cancelled_details_without_total_are_allowed(self):
        history = self.make_order(
            f'<div class="order-card"><span data-component="orderId">Order # {ORDER_ID}</span>'
            '<div class="order-header"><div class="a-col-left">'
            '<div class="a-span9">Ship to</div></div></div></div>'
        )
        details = self.make_order(
            '<div id="orderDetails"><h4 class="od-status-message">'
            '<span>Cancelled</span></h4></div>',
            full_details=True,
            clone=history,
        )

        self.assertIsNone(details.grand_total)

    def test_missing_total_on_details_still_fails(self):
        history = self.make_order(
            f'<div class="order-card"><span data-component="orderId">Order # {ORDER_ID}</span>'
            '<div class="order-header"><div class="a-col-left">'
            '<div class="a-span9">Ship to</div></div></div></div>'
        )

        with self.assertRaisesRegex(AmazonOrdersError, "grand_total.*could not be parsed"):
            self.make_order('<div id="orderDetails"></div>', full_details=True, clone=history)


if __name__ == "__main__":
    unittest.main()
