from decimal import Decimal
from typing import Dict, List, Tuple, Optional
import heapq
from collections import defaultdict
from datetime import datetime

from .order import Order, OrderSide, OrderStatus


class PriceLevel:
    """Represents a price level in the order book with a queue of orders."""
    
    def __init__(self, price: Decimal):
        self.price = price
        self.orders = []  # List of (timestamp, order_id, Order) tuples for price-time priority
        self.total_quantity = Decimal("0")
    
    def add_order(self, order: Order) -> None:
        """Add an order to this price level."""
        timestamp = order.created_at.timestamp()
        heapq.heappush(self.orders, (timestamp, order.order_id, order))
        self.total_quantity += order.remaining_quantity
    
    def remove_order(self, order_id: str) -> Optional[Order]:
        """Remove an order from this price level by order_id."""
        for i, (_, oid, order) in enumerate(self.orders):
            if oid == order_id:
                self.orders.pop(i)
                heapq.heapify(self.orders)  # Re-heapify after removal
                self.total_quantity -= order.remaining_quantity
                return order
        return None
    
    def get_oldest_order(self) -> Optional[Order]:
        """Get the oldest order at this price level without removing it."""
        if not self.orders:
            return None
        return self.orders[0][2]
    
    def pop_oldest_order(self) -> Optional[Order]:
        """Remove and return the oldest order at this price level."""
        if not self.orders:
            return None
        _, _, order = heapq.heappop(self.orders)
        self.total_quantity -= order.remaining_quantity
        return order
    
    def is_empty(self) -> bool:
        """Check if this price level has no orders."""
        return len(self.orders) == 0


class OrderBook:
    """Maintains the order book for a trading pair."""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids = {}  # Price -> PriceLevel (sorted high to low)
        self.asks = {}  # Price -> PriceLevel (sorted low to high)
        self.orders = {}  # Order ID -> Order
        self.last_updated = datetime.utcnow()
    
    def add_order(self, order: Order) -> None:
        """Add a new order to the book."""
        if order.order_id in self.orders:
            raise ValueError(f"Order with ID {order.order_id} already exists")
        
        # Only add limit orders to the book
        if order.status == OrderStatus.OPEN:
            price_map = self.bids if order.side == OrderSide.BUY else self.asks
            
            if order.price not in price_map:
                price_map[order.price] = PriceLevel(order.price)
            
            price_map[order.price].add_order(order)
            self.orders[order.order_id] = order
            self.last_updated = datetime.utcnow()
    
    def remove_order(self, order_id: str) -> Optional[Order]:
        """Remove an order from the book by order ID."""
        if order_id not in self.orders:
            return None
        
        order = self.orders[order_id]
        price_map = self.bids if order.side == OrderSide.BUY else self.asks
        
        if order.price in price_map:
            price_level = price_map[order.price]
            price_level.remove_order(order_id)
            
            # Remove empty price levels
            if price_level.is_empty():
                del price_map[order.price]
        
        del self.orders[order_id]
        self.last_updated = datetime.utcnow()
        return order
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID without removing it."""
        return self.orders.get(order_id)
    
    def get_best_bid(self) -> Optional[Tuple[Decimal, Decimal]]:
        """Get the best (highest) bid price and quantity."""
        if not self.bids:
            return None
        best_price = max(self.bids.keys())
        return (best_price, self.bids[best_price].total_quantity)
    
    def get_best_ask(self) -> Optional[Tuple[Decimal, Decimal]]:
        """Get the best (lowest) ask price and quantity."""
        if not self.asks:
            return None
        best_price = min(self.asks.keys())
        return (best_price, self.asks[best_price].total_quantity)
    
    def get_order_book_snapshot(self):
        """Get a snapshot of the order book for API responses."""
        timestamp = datetime.utcnow().isoformat()
        
        # Convert bids to list of [price, quantity] pairs
        bids = []
        for price in sorted(self.bids.keys(), reverse=True):
            price_level = self.bids[price]
            if price_level.total_quantity > 0:
                bids.append([str(price), str(price_level.total_quantity)])
        
        # Convert asks to list of [price, quantity] pairs
        asks = []
        for price in sorted(self.asks.keys()):
            price_level = self.asks[price]
            if price_level.total_quantity > 0:
                asks.append([str(price), str(price_level.total_quantity)])
        
        return {
            "symbol": self.symbol,
            "timestamp": timestamp,
            "bids": bids,
            "asks": asks
        }
    
    def get_bbo(self):
        """Get the best bid and offer (BBO)."""
        timestamp = datetime.utcnow().isoformat()
        
        # Get best bid
        bid = None
        if self.bids:
            best_bid_price = max(self.bids.keys()) if self.bids else None
            if best_bid_price and self.bids[best_bid_price].total_quantity > 0:
                bid = {
                    "price": str(best_bid_price),
                    "quantity": str(self.bids[best_bid_price].total_quantity)
                }
        
        # Get best ask
        ask = None
        if self.asks:
            best_ask_price = min(self.asks.keys()) if self.asks else None
            if best_ask_price and self.asks[best_ask_price].total_quantity > 0:
                ask = {
                    "price": str(best_ask_price),
                    "quantity": str(self.asks[best_ask_price].total_quantity)
                }
        
        return {
            "symbol": self.symbol,
            "timestamp": timestamp,
            "bid": bid,
            "ask": ask
        }