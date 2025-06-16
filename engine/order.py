import uuid
from datetime import datetime
from enum import Enum
from decimal import Decimal
from typing import Optional, Dict, Any


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    IOC = "ioc"  # Immediate-Or-Cancel
    FOK = "fok"  # Fill-Or-Kill


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Order:
    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        client_order_id: Optional[str] = None,
    ):
        self.order_id = str(uuid.uuid4())
        self.client_order_id = client_order_id
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.status = OrderStatus.PENDING
        self.created_at = datetime.utcnow()
        self.updated_at = self.created_at
        self.filled_quantity = Decimal("0")
        self.remaining_quantity = quantity
        
        # Validate order
        self._validate()
    
    def _validate(self):
        """Validate order parameters."""
        if self.quantity <= Decimal("0"):
            raise ValueError("Quantity must be positive")
        
        if self.order_type != OrderType.MARKET and (self.price is None or self.price <= Decimal("0")):
            raise ValueError("Price must be positive for non-market orders")
    
    def fill(self, fill_quantity: Decimal, fill_price: Decimal) -> None:
        """Record a fill for this order."""
        if fill_quantity > self.remaining_quantity:
            raise ValueError(f"Fill quantity {fill_quantity} exceeds remaining quantity {self.remaining_quantity}")
        
        self.filled_quantity += fill_quantity
        self.remaining_quantity -= fill_quantity
        self.updated_at = datetime.utcnow()
        
        if self.remaining_quantity == Decimal("0"):
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED
    
    def cancel(self) -> bool:
        """Cancel the order if possible."""
        if self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            return False
        
        self.status = OrderStatus.CANCELLED
        self.updated_at = datetime.utcnow()
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary for API responses."""
        return {
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": str(self.quantity),
            "price": str(self.price) if self.price is not None else None,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
            "filled_quantity": str(self.filled_quantity),
            "remaining_quantity": str(self.remaining_quantity)
        }