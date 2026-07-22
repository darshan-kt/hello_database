class MiniEcommerceError(Exception):
    """Base class for all domain errors."""


class DuplicateEmailError(MiniEcommerceError):
    pass


class ProductNotFoundError(MiniEcommerceError):
    pass


class OutOfStockError(MiniEcommerceError):
    def __init__(self, product_id: int, requested: int, available: int):
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Product {product_id}: requested {requested}, only {available} in stock"
        )


class EmptyCartError(MiniEcommerceError):
    pass


class PaymentFailedError(MiniEcommerceError):
    pass
