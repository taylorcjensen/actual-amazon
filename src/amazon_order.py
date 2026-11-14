import logging

from amazonorders.entity.order import Order
from amazonorders.exception import AmazonOrdersEntityError
from amazonauth.selectors import Selector
from amazonorders.selectors import Selectors

logger = logging.getLogger(__name__)


class AmazonSelectors(Selectors):
    ORDER_SKIP_TOTALS = [
        *Selectors.ORDER_SKIP_TOTALS,
        Selector("h4.od-status-message", "Cancelled"),
    ]


class RecoverableOrder(Order):
    def __init__(self, parsed, config, full_details=False, clone=None, index=None, order_number=None):
        super().__init__(parsed, config, full_details, clone, index, order_number)
        if full_details and clone is not None and clone.grand_total is None:
            self.cancelled = self.cancelled or self._parse_cancelled()
            self.grand_total = self.safe_parse(self._parse_grand_total)

    def _parse_grand_total(self):
        try:
            return super()._parse_grand_total()
        except AmazonOrdersEntityError as error:
            if (self.full_details or not str(error).startswith("Order.grand_total ")
                    or "could not be parsed" not in str(error)):
                raise
            logger.warning("Order %s has no history total; trying its details page", self.order_number)
            return None
