from decimal import Decimal
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import uuid

from .order import Order, OrderType, OrderSide, OrderStatus
from .order_book import OrderBook


class Trade:
    """Represents a trade execution."""
    
    def __init__(
        self,
        symbol: str,
        price: Decimal,
        quantity: Decimal,
        maker_order_id: str,
        taker_order_id: str,
        aggressor_side: OrderSide
    ):
        self.trade_id = str(uuid.uuid4())
        self.symbol = symbol
        self.price = price
        self.quantity = quantity
        self.maker_order_id = maker_order_id
        self.taker_order_id = taker_order_id
        self.aggressor_side = aggressor_side
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary for API responses."""
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "price": str(self.price),
            "quantity": str(self.quantity),
            "maker_order_id": self.maker_order_id,
            "taker_order_id": self.taker_order_id,
            "aggressor_side": self.aggressor_side.value,
            "timestamp": self.timestamp.isoformat() + "Z"
        }


class MatchingEngine:
    """Core matching engine implementing price-time priority matching."""
    
    def __init__(self):
        self.order_books = {}  # Symbol -> OrderBook
        self.trades = []  # List of executed trades
        self.trade_listeners = []  # Callbacks for trade notifications
    
    def get_order_book(self, symbol: str) -> OrderBook:
        """Get or create an order book for a symbol."""
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
        return self.order_books[symbol]
    
    def add_trade_listener(self, callback):
        """Add a callback function to be notified of trades."""
        self.trade_listeners.append(callback)
    
    def _notify_trade(self, trade: Trade):
        """Notify all listeners of a new trade."""
        for callback in self.trade_listeners:
            callback(trade)
    
    def process_order(self, order: Order) -> Tuple[Order, List[Trade]]:
        """Process an incoming order according to its type and matching rules."""
        order_book = self.get_order_book(order.symbol)
        trades = []
        
        # Handle different order types
        if order.order_type == OrderType.MARKET:
            trades = self._match_market_order(order, order_book)
        elif order.order_type == OrderType.LIMIT:
            trades = self._match_limit_order(order, order_book)
        elif order.order_type == OrderType.IOC:
            trades = self._match_ioc_order(order, order_book)
        elif order.order_type == OrderType.FOK:
            trades = self._match_fok_order(order, order_book)
        
        # Notify listeners of trades
        for trade in trades:
            self.trades.append(trade)
            self._notify_trade(trade)
        
        return order, trades
    
    def _match_market_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """Match a market order against the order book."""
        trades = []
        
        # Market orders execute immediately at best available price(s)
        opposite_side = OrderSide.SELL if order.side == OrderSide.BUY else OrderSide.BUY
        price_map = order_book.asks if order.side == OrderSide.BUY else order_book.bids
        price_getter = min if order.side == OrderSide.BUY else max
        
        # Continue matching until the order is filled or no more liquidity
        while order.remaining_quantity > Decimal("0") and price_map:
            # Get the best price level
            best_price = price_getter(price_map.keys())
            price_level = price_map[best_price]
            
            while order.remaining_quantity > Decimal("0") and not price_level.is_empty():
                resting_order = price_level.get_oldest_order()
                
                # Calculate fill quantity
                fill_quantity = min(order.remaining_quantity, resting_order.remaining_quantity)
                
                # Execute the trade
                trade = Trade(
                    symbol=order.symbol,
                    price=resting_order.price,
                    quantity=fill_quantity,
                    maker_order_id=resting_order.order_id,
                    taker_order_id=order.order_id,
                    aggressor_side=order.side
                )
                trades.append(trade)
                
                # Update orders
                order.fill(fill_quantity, resting_order.price)
                resting_order.fill(fill_quantity, resting_order.price)
                
                # Remove filled resting order
                if resting_order.status == OrderStatus.FILLED:
                    price_level.pop_oldest_order()
            
            # Remove empty price level
            if price_level.is_empty():
                del price_map[best_price]
        
        # If market order couldn't be fully filled, mark as partially filled
        if order.remaining_quantity > Decimal("0"):
            order.status = OrderStatus.PARTIALLY_FILLED
        
        return trades
    
    def _match_limit_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """Match a limit order against the order book."""
        trades = []
        
        # For buy orders, match against asks where ask price <= limit price
        # For sell orders, match against bids where bid price >= limit price
        opposite_side = OrderSide.SELL if order.side == OrderSide.BUY else OrderSide.BUY
        price_map = order_book.asks if order.side == OrderSide.BUY else order_book.bids
        price_getter = min if order.side == OrderSide.BUY else max
        price_valid = (lambda p: p <= order.price) if order.side == OrderSide.BUY else (lambda p: p >= order.price)
        
        # Match against existing orders
        while order.remaining_quantity > Decimal("0") and price_map:
            # Check if there are any valid price levels
            if not price_map or not price_valid(price_getter(price_map.keys())):
                break
            
            best_price = price_getter(price_map.keys())
            price_level = price_map[best_price]
            
            while order.remaining_quantity > Decimal("0") and not price_level.is_empty() and price_valid(best_price):
                resting_order = price_level.get_oldest_order()
                
                # Calculate fill quantity
                fill_quantity = min(order.remaining_quantity, resting_order.remaining_quantity)
                
                # Execute the trade
                trade = Trade(
                    symbol=order.symbol,
                    price=resting_order.price,
                    quantity=fill_quantity,
                    maker_order_id=resting_order.order_id,
                    taker_order_id=order.order_id,
                    aggressor_side=order.side
                )
                trades.append(trade)
                
                # Update orders
                order.fill(fill_quantity, resting_order.price)
                resting_order.fill(fill_quantity, resting_order.price)
                
                # Remove filled resting order
                if resting_order.status == OrderStatus.FILLED:
                    price_level.pop_oldest_order()
            
            # Remove empty price level
            if price_level.is_empty():
                del price_map[best_price]
        
        # If limit order has remaining quantity, add to the book
        if order.remaining_quantity > Decimal("0"):
            order.status = OrderStatus.OPEN
            order_book.add_order(order)
        
        return trades
    
    def _match_ioc_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """Match an IOC (Immediate-Or-Cancel) order against the order book."""
        # IOC orders are like limit orders but any unfilled portion is cancelled
        trades = []
        
        # Same matching logic as limit orders
        opposite_side = OrderSide.SELL if order.side == OrderSide.BUY else OrderSide.BUY
        price_map = order_book.asks if order.side == OrderSide.BUY else order_book.bids
        price_getter = min if order.side == OrderSide.BUY else max
        price_valid = (lambda p: p <= order.price) if order.side == OrderSide.BUY else (lambda p: p >= order.price)
        
        # Match against existing orders
        while order.remaining_quantity > Decimal("0") and price_map:
            # Check if there are any valid price levels
            if not price_map or not price_valid(price_getter(price_map.keys())):
                break
            
            best_price = price_getter(price_map.keys())
            price_level = price_map[best_price]
            
            while order.remaining_quantity > Decimal("0") and not price_level.is_empty() and price_valid(best_price):
                resting_order = price_level.get_oldest_order()
                
                # Calculate fill quantity
                fill_quantity = min(order.remaining_quantity, resting_order.remaining_quantity)
                
                # Execute the trade
                trade = Trade(
                    symbol=order.symbol,
                    price=resting_order.price,
                    quantity=fill_quantity,
                    maker_order_id=resting_order.order_id,
                    taker_order_id=order.order_id,
                    aggressor_side=order.side
                )
                trades.append(trade)
                
                # Update orders
                order.fill(fill_quantity, resting_order.price)
                resting_order.fill(fill_quantity, resting_order.price)
                
                # Remove filled resting order
                if resting_order.status == OrderStatus.FILLED:
                    price_level.pop_oldest_order()
            
            # Remove empty price level
            if price_level.is_empty():
                del price_map[best_price]
        
        # Cancel any unfilled portion
        if order.remaining_quantity > Decimal("0"):
            order.status = OrderStatus.CANCELLED
        
        return trades
    
    def _match_fok_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """Match a FOK (Fill-Or-Kill) order against the order book."""
        # FOK orders must be filled completely or not at all
        trades = []
        
        # Check if the order can be fully filled
        can_fill = self._can_fully_fill_order(order, order_book)
        
        if can_fill:
            # Same matching logic as limit orders
            opposite_side = OrderSide.SELL if order.side == OrderSide.BUY else OrderSide.BUY
            price_map = order_book.asks if order.side == OrderSide.BUY else order_book.bids
            price_getter = min if order.side == OrderSide.BUY else max
            price_valid = (lambda p: p <= order.price) if order.side == OrderSide.BUY else (lambda p: p >= order.price)
            
            # Match against existing orders
            while order.remaining_quantity > Decimal("0") and price_map:
                # Check if there are any valid price levels
                if not price_map or not price_valid(price_getter(price_map.keys())):
                    break
                
                best_price = price_getter(price_map.keys())
                price_level = price_map[best_price]
                
                while order.remaining_quantity > Decimal("0") and not price_level.is_empty() and price_valid(best_price):
                    resting_order = price_level.get_oldest_order()
                    
                    # Calculate fill quantity
                    fill_quantity = min(order.remaining_quantity, resting_order.remaining_quantity)
                    
                    # Execute the trade
                    trade = Trade(
                        symbol=order.symbol,
                        price=resting_order.price,
                        quantity=fill_quantity,
                        maker_order_id=resting_order.order_id,
                        taker_order_id=order.order_id,
                        aggressor_side=order.side
                    )
                    trades.append(trade)
                    
                    # Update orders
                    order.fill(fill_quantity, resting_order.price)
                    resting_order.fill(fill_quantity, resting_order.price)
                    
                    # Remove filled resting order
                    if resting_order.status == OrderStatus.FILLED:
                        price_level.pop_oldest_order()
                
                # Remove empty price level
                if price_level.is_empty():
                    del price_map[best_price]
        else:
            # Cannot fully fill, cancel the order
            order.status = OrderStatus.CANCELLED
        
        return trades
    
    def _can_fully_fill_order(self, order: Order, order_book: OrderBook) -> bool:
        """Check if an order can be fully filled at the current order book state."""
        remaining_quantity = order.quantity
        
        # For buy orders, check asks
        # For sell orders, check bids
        price_map = order_book.asks if order.side == OrderSide.BUY else order_book.bids
        price_getter = min if order.side == OrderSide.BUY else max
        price_valid = (lambda p: p <= order.price) if order.side == OrderSide.BUY else (lambda p: p >= order.price)
        
        # Make a copy of price levels to avoid modifying the actual order book
        price_levels = sorted(price_map.keys())
        
        for price in price_levels:
            if not price_valid(price):
                break
            
            price_level = price_map[price]
            available_quantity = price_level.total_quantity
            
            if remaining_quantity <= available_quantity:
                return True
            
            remaining_quantity -= available_quantity
        
        return False
    
    def cancel_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Cancel an order by ID."""
        if symbol not in self.order_books:
            return None
        
        order_book = self.order_books[symbol]
        order = order_book.get_order(order_id)
        
        if order:
            order_book.remove_order(order_id)
            order.cancel()
            return order
        
        return None