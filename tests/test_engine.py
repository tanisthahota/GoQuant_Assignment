import unittest
from decimal import Decimal
import sys
import os

# Add the parent directory to the path so we can import the engine modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.order import Order, OrderType, OrderSide, OrderStatus
from engine.order_book import OrderBook, PriceLevel
from engine.matcher import MatchingEngine, Trade


class TestOrder(unittest.TestCase):
    def test_order_creation(self):
        # Test limit order creation
        limit_order = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.5"),
            price=Decimal("50000")
        )
        
        self.assertEqual(limit_order.symbol, "BTC-USDT")
        self.assertEqual(limit_order.side, OrderSide.BUY)
        self.assertEqual(limit_order.order_type, OrderType.LIMIT)
        self.assertEqual(limit_order.quantity, Decimal("1.5"))
        self.assertEqual(limit_order.price, Decimal("50000"))
        self.assertEqual(limit_order.status, OrderStatus.PENDING)
        self.assertEqual(limit_order.filled_quantity, Decimal("0"))
        self.assertEqual(limit_order.remaining_quantity, Decimal("1.5"))
        
        # Test market order creation
        market_order = Order(
            symbol="ETH-USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("2.0")
        )
        
        self.assertEqual(market_order.symbol, "ETH-USDT")
        self.assertEqual(market_order.side, OrderSide.SELL)
        self.assertEqual(market_order.order_type, OrderType.MARKET)
        self.assertEqual(market_order.quantity, Decimal("2.0"))
        self.assertIsNone(market_order.price)
        self.assertEqual(market_order.status, OrderStatus.PENDING)
    
    def test_order_validation(self):
        # Test invalid quantity
        with self.assertRaises(ValueError):
            Order(
                symbol="BTC-USDT",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("-1.5"),
                price=Decimal("50000")
            )
        
        # Test invalid price for limit order
        with self.assertRaises(ValueError):
            Order(
                symbol="BTC-USDT",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("1.5"),
                price=Decimal("-50000")
            )
        
        # Test missing price for limit order
        with self.assertRaises(ValueError):
            Order(
                symbol="BTC-USDT",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("1.5")
            )
    
    def test_order_fill(self):
        order = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2.0"),
            price=Decimal("50000")
        )
        
        # Partial fill
        order.fill(Decimal("0.5"), Decimal("49900"))
        self.assertEqual(order.filled_quantity, Decimal("0.5"))
        self.assertEqual(order.remaining_quantity, Decimal("1.5"))
        self.assertEqual(order.status, OrderStatus.PARTIALLY_FILLED)
        
        # Complete fill
        order.fill(Decimal("1.5"), Decimal("49900"))
        self.assertEqual(order.filled_quantity, Decimal("2.0"))
        self.assertEqual(order.remaining_quantity, Decimal("0"))
        self.assertEqual(order.status, OrderStatus.FILLED)
        
        # Attempt to overfill
        with self.assertRaises(ValueError):
            order.fill(Decimal("0.1"), Decimal("49900"))
    
    def test_order_cancel(self):
        order = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2.0"),
            price=Decimal("50000")
        )
        
        # Cancel open order
        result = order.cancel()
        self.assertTrue(result)
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        
        # Try to cancel already cancelled order
        result = order.cancel()
        self.assertFalse(result)


class TestOrderBook(unittest.TestCase):
    def test_price_level(self):
        price_level = PriceLevel(Decimal("50000"))
        
        # Create test orders
        order1 = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("50000")
        )
        order1.status = OrderStatus.OPEN
        
        order2 = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2.0"),
            price=Decimal("50000")
        )
        order2.status = OrderStatus.OPEN
        
        # Add orders to price level
        price_level.add_order(order1)
        self.assertEqual(price_level.total_quantity, Decimal("1.0"))
        
        price_level.add_order(order2)
        self.assertEqual(price_level.total_quantity, Decimal("3.0"))
        
        # Test price-time priority
        oldest_order = price_level.get_oldest_order()
        self.assertEqual(oldest_order.order_id, order1.order_id)
        
        # Test removing order
        removed_order = price_level.remove_order(order1.order_id)
        self.assertEqual(removed_order.order_id, order1.order_id)
        self.assertEqual(price_level.total_quantity, Decimal("2.0"))
        
        # Test popping oldest order
        popped_order = price_level.pop_oldest_order()
        self.assertEqual(popped_order.order_id, order2.order_id)
        self.assertEqual(price_level.total_quantity, Decimal("0"))
        self.assertTrue(price_level.is_empty())
    
    def test_order_book(self):
        order_book = OrderBook("BTC-USDT")
        
        # Create test orders
        buy_order1 = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("49000")
        )
        buy_order1.status = OrderStatus.OPEN
        
        buy_order2 = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2.0"),
            price=Decimal("50000")
        )
        buy_order2.status = OrderStatus.OPEN
        
        sell_order1 = Order(
            symbol="BTC-USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.5"),
            price=Decimal("51000")
        )
        sell_order1.status = OrderStatus.OPEN
        
        sell_order2 = Order(
            symbol="BTC-USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2.5"),
            price=Decimal("52000")
        )
        sell_order2.status = OrderStatus.OPEN
        
        # Add orders to book
        order_book.add_order(buy_order1)
        order_book.add_order(buy_order2)
        order_book.add_order(sell_order1)
        order_book.add_order(sell_order2)
        
        # Test best bid/ask
        best_bid = order_book.get_best_bid()
        self.assertEqual(best_bid[0], Decimal("50000"))
        self.assertEqual(best_bid[1], Decimal("2.0"))
        
        best_ask = order_book.get_best_ask()
        self.assertEqual(best_ask[0], Decimal("51000"))
        self.assertEqual(best_ask[1], Decimal("1.5"))
        
        # Test BBO
        bbo = order_book.get_bbo()
        self.assertEqual(bbo["symbol"], "BTC-USDT")
        self.assertEqual(bbo["bid"]["price"], "50000")
        self.assertEqual(bbo["bid"]["quantity"], "2.0")
        self.assertEqual(bbo["ask"]["price"], "51000")
        self.assertEqual(bbo["ask"]["quantity"], "1.5")
        
        # Test order book snapshot
        snapshot = order_book.get_order_book_snapshot()
        self.assertEqual(snapshot["symbol"], "BTC-USDT")
        self.assertEqual(len(snapshot["bids"]), 2)
        self.assertEqual(len(snapshot["asks"]), 2)
        self.assertEqual(snapshot["bids"][0], ["50000", "2.0"])
        self.assertEqual(snapshot["bids"][1], ["49000", "1.0"])
        self.assertEqual(snapshot["asks"][0], ["51000", "1.5"])
        self.assertEqual(snapshot["asks"][1], ["52000", "2.5"])
        
        # Test removing order
        removed_order = order_book.remove_order(buy_order2.order_id)
        self.assertEqual(removed_order.order_id, buy_order2.order_id)
        
        # Verify best bid updated
        best_bid = order_book.get_best_bid()
        self.assertEqual(best_bid[0], Decimal("49000"))
        self.assertEqual(best_bid[1], Decimal("1.0"))


class TestMatchingEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MatchingEngine()
        
        # Add some initial orders to create liquidity
        # Buy side
        buy_limit_order1 = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("49000")
        )
        buy_limit_order1.status = OrderStatus.OPEN
        
        buy_limit_order2 = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2.0"),
            price=Decimal("48000")
        )
        buy_limit_order2.status = OrderStatus.OPEN
        
        # Sell side
        sell_limit_order1 = Order(
            symbol="BTC-USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.5"),
            price=Decimal("51000")
        )
        sell_limit_order1.status = OrderStatus.OPEN
        
        sell_limit_order2 = Order(
            symbol="BTC-USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2.5"),
            price=Decimal("52000")
        )
        sell_limit_order2.status = OrderStatus.OPEN
        
        # Add orders to the book
        order_book = self.engine.get_order_book("BTC-USDT")
        order_book.add_order(buy_limit_order1)
        order_book.add_order(buy_limit_order2)
        order_book.add_order(sell_limit_order1)
        order_book.add_order(sell_limit_order2)
    
    def test_market_buy_order(self):
        # Create a market buy order
        market_buy = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1.0")
        )
        
        # Process the order
        result_order, trades = self.engine.process_order(market_buy)
        
        # Verify the order was filled
        self.assertEqual(result_order.status, OrderStatus.FILLED)
        self.assertEqual(result_order.filled_quantity, Decimal("1.0"))
        self.assertEqual(result_order.remaining_quantity, Decimal("0"))
        
        # Verify a trade was created
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].symbol, "BTC-USDT")
        self.assertEqual(trades[0].price, Decimal("51000"))
        self.assertEqual(trades[0].quantity, Decimal("1.0"))
        self.assertEqual(trades[0].aggressor_side, OrderSide.BUY)
        
        # Verify the order book was updated
        order_book = self.engine.get_order_book("BTC-USDT")
        best_ask = order_book.get_best_ask()
        self.assertEqual(best_ask[0], Decimal("51000"))
        self.assertEqual(best_ask[1], Decimal("0.5"))
    
    def test_market_sell_order(self):
        # Create a market sell order
        market_sell = Order(
            symbol="BTC-USDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.5")
        )
        
        # Process the order
        result_order, trades = self.engine.process_order(market_sell)
        
        # Verify the order was filled
        self.assertEqual(result_order.status, OrderStatus.FILLED)
        self.assertEqual(result_order.filled_quantity, Decimal("0.5"))
        self.assertEqual(result_order.remaining_quantity, Decimal("0"))
        
        # Verify a trade was created
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].symbol, "BTC-USDT")
        self.assertEqual(trades[0].price, Decimal("49000"))
        self.assertEqual(trades[0].quantity, Decimal("0.5"))
        self.assertEqual(trades[0].aggressor_side, OrderSide.SELL)
        
        # Verify the order book was updated
        order_book = self.engine.get_order_book("BTC-USDT")
        best_bid = order_book.get_best_bid()
        self.assertEqual(best_bid[0], Decimal("49000"))
        self.assertEqual(best_bid[1], Decimal("0.5"))
    
    def test_limit_buy_order_immediate_execution(self):
        # Create a limit buy order that crosses the spread
        limit_buy = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("51500")  # Higher than best ask
        )
        
        # Process the order
        result_order, trades = self.engine.process_order(limit_buy)
        
        # Verify the order was filled
        self.assertEqual(result_order.status, OrderStatus.FILLED)
        self.assertEqual(result_order.filled_quantity, Decimal("1.0"))
        self.assertEqual(result_order.remaining_quantity, Decimal("0"))
        
        # Verify a trade was created at the best ask price (price improvement)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].symbol, "BTC-USDT")
        self.assertEqual(trades[0].price, Decimal("51000"))  # Best ask price, not the limit price
        self.assertEqual(trades[0].quantity, Decimal("1.0"))
        self.assertEqual(trades[0].aggressor_side, OrderSide.BUY)
    
    def test_limit_buy_order_resting(self):
        # Create a limit buy order that doesn't cross the spread
        limit_buy = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("50000")  # Below best ask
        )
        
        # Process the order
        result_order, trades = self.engine.process_order(limit_buy)
        
        # Verify the order was not filled and is resting on the book
        self.assertEqual(result_order.status, OrderStatus.OPEN)
        self.assertEqual(result_order.filled_quantity, Decimal("0"))
        self.assertEqual(result_order.remaining_quantity, Decimal("1.0"))
        
        # Verify no trades were created
        self.assertEqual(len(trades), 0)
        
        # Verify the order book was updated
        order_book = self.engine.get_order_book("BTC-USDT")
        best_bid = order_book.get_best_bid()
        self.assertEqual(best_bid[0], Decimal("50000"))
        self.assertEqual(best_bid[1], Decimal("1.0"))
    
    def test_ioc_order_partial_fill(self):
        # Create an IOC buy order
        ioc_buy = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.IOC,
            quantity=Decimal("2.0"),
            price=Decimal("51000")
        )
        
        # Process the order
        result_order, trades = self.engine.process_order(ioc_buy)
        
        # Verify the order was partially filled and the rest was cancelled
        self.assertEqual(result_order.status, OrderStatus.CANCELLED)
        self.assertEqual(result_order.filled_quantity, Decimal("1.5"))
        self.assertEqual(result_order.remaining_quantity, Decimal("0.5"))
        
        # Verify a trade was created
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].symbol, "BTC-USDT")
        self.assertEqual(trades[0].price, Decimal("51000"))
        self.assertEqual(trades[0].quantity, Decimal("1.5"))
        self.assertEqual(trades[0].aggressor_side, OrderSide.BUY)
        
        # Verify the order is not on the book
        order_book = self.engine.get_order_book("BTC-USDT")
        self.assertNotIn(result_order.order_id, order_book.orders)
    
    def test_fok_order_complete_fill(self):
        # Create an FOK buy order that can be completely filled
        fok_buy = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.FOK,
            quantity=Decimal("1.0"),
            price=Decimal("51000")
        )
        
        # Process the order
        result_order, trades = self.engine.process_order(fok_buy)
        
        # Verify the order was completely filled
        self.assertEqual(result_order.status, OrderStatus.FILLED)
        self.assertEqual(result_order.filled_quantity, Decimal("1.0"))
        self.assertEqual(result_order.remaining_quantity, Decimal("0"))
        
        # Verify a trade was created
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].symbol, "BTC-USDT")
        self.assertEqual(trades[0].price, Decimal("51000"))
        self.assertEqual(trades[0].quantity, Decimal("1.0"))
        self.assertEqual(trades[0].aggressor_side, OrderSide.BUY)
    
    def test_fok_order_no_fill(self):
        # Create an FOK buy order that cannot be completely filled
        fok_buy = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.FOK,
            quantity=Decimal("3.0"),  # More than available at 51000
            price=Decimal("51000")
        )
        
        # Process the order
        result_order, trades = self.engine.process_order(fok_buy)
        
        # Verify the order was cancelled
        self.assertEqual(result_order.status, OrderStatus.CANCELLED)
        self.assertEqual(result_order.filled_quantity, Decimal("0"))
        self.assertEqual(result_order.remaining_quantity, Decimal("3.0"))
        
        # Verify no trades were created
        self.assertEqual(len(trades), 0)
        
        # Verify the order book was not changed
        order_book = self.engine.get_order_book("BTC-USDT")
        best_ask = order_book.get_best_ask()
        self.assertEqual(best_ask[0], Decimal("51000"))
        self.assertEqual(best_ask[1], Decimal("1.5"))
    
    def test_cancel_order(self):
        # Add a limit order to cancel
        limit_buy = Order(
            symbol="BTC-USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("47000")
        )
        limit_buy.status = OrderStatus.OPEN
        
        order_book = self.engine.get_order_book("BTC-USDT")
        order_book.add_order(limit_buy)
        
        # Cancel the order
        cancelled_order = self.engine.cancel_order(limit_buy.order_id, "BTC-USDT")
        
        # Verify the order was cancelled
        self.assertIsNotNone(cancelled_order)
        self.assertEqual(cancelled_order.status, OrderStatus.CANCELLED)
        
        # Verify the order is not in the book
        self.assertNotIn(limit_buy.order_id, order_book.orders)


if __name__ == "__main__":
    unittest.main()