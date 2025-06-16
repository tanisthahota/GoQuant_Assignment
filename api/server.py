from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Set
from decimal import Decimal
import json
import asyncio
from datetime import datetime
import uuid

from engine.order import Order, OrderType, OrderSide, OrderStatus
from engine.matcher import MatchingEngine, Trade
from utils.logger import log_api_request, log_order, log_trade


# Pydantic models for API requests and responses
class OrderRequest(BaseModel):
    symbol: str
    side: str
    order_type: str = Field(..., alias="type")
    quantity: str
    price: Optional[str] = None
    client_order_id: Optional[str] = None

    class Config:
        populate_by_name = True  # Updated from allow_population_by_field_name


class OrderResponse(BaseModel):
    order_id: str
    client_order_id: Optional[str]
    symbol: str
    side: str
    type: str
    quantity: str
    price: Optional[str]
    status: str
    created_at: str
    updated_at: str
    filled_quantity: str
    remaining_quantity: str


class TradeResponse(BaseModel):
    trade_id: str
    symbol: str
    price: str
    quantity: str
    maker_order_id: str
    taker_order_id: str
    aggressor_side: str
    timestamp: str


class OrderBookResponse(BaseModel):
    symbol: str
    timestamp: str
    bids: List[List[str]]
    asks: List[List[str]]


class BBOResponse(BaseModel):
    symbol: str
    timestamp: str
    bid: Optional[Dict[str, str]]
    ask: Optional[Dict[str, str]]


# Create FastAPI app
app = FastAPI(title="Cryptocurrency Matching Engine API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create matching engine instance
matching_engine = MatchingEngine()

# WebSocket connection managers
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = set()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]

    def subscribe(self, websocket: WebSocket, symbol: str):
        if websocket in self.subscriptions:
            self.subscriptions[websocket].add(symbol)

    def unsubscribe(self, websocket: WebSocket, symbol: str):
        if websocket in self.subscriptions:
            self.subscriptions[websocket].discard(symbol)

    async def broadcast(self, message: str, symbol: str = None):
        for connection in self.active_connections:
            if symbol is None or (connection in self.subscriptions and 
                                 (symbol in self.subscriptions[connection] or 
                                  '*' in self.subscriptions[connection])):
                await connection.send_text(message)


# Create connection managers for different feeds
trade_manager = ConnectionManager()
order_book_manager = ConnectionManager()
bbo_manager = ConnectionManager()


# Register trade listener
async def trade_listener(trade: Trade):
    trade_data = trade.to_dict()
    log_trade(trade)
    
    # Broadcast trade to subscribers
    await trade_manager.broadcast(json.dumps(trade_data), trade.symbol)
    
    # Also update order book and BBO after trade
    symbol = trade.symbol
    order_book = matching_engine.get_order_book(symbol)
    
    # Update order book
    order_book_data = order_book.get_order_book_snapshot()
    await order_book_manager.broadcast(json.dumps(order_book_data), symbol)
    
    # Update BBO
    bbo_data = order_book.get_bbo()
    await bbo_manager.broadcast(json.dumps(bbo_data), symbol)


# Convert sync trade listener to async
def trade_callback(trade: Trade):
    asyncio.create_task(trade_listener(trade))


# Register the callback
matching_engine.add_trade_listener(trade_callback)


# API routes
@app.post("/api/orders", response_model=OrderResponse)
async def create_order(order_request: OrderRequest):
    try:
        log_api_request("POST", "/api/orders", order_request.dict())
        
        # Convert string values to appropriate types
        quantity = Decimal(order_request.quantity)
        price = Decimal(order_request.price) if order_request.price else None
        
        # Map string values to enum types
        try:
            order_side = OrderSide(order_request.side.lower())
            order_type = OrderType(order_request.order_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid order side or type")
        
        # Create order object
        order = Order(
            symbol=order_request.symbol,
            side=order_side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            client_order_id=order_request.client_order_id
        )
        
        log_order(order, "created")
        
        # Process the order
        processed_order, trades = matching_engine.process_order(order)
        
        log_order(processed_order, "processed")
        
        # Convert order to response format
        response_data = processed_order.to_dict()
        response_data["type"] = response_data.pop("order_type")
        
        return response_data
    
    except ValueError as e:
        log_api_request("POST", "/api/orders", order_request.dict(), "400 - " + str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_api_request("POST", "/api/orders", order_request.dict(), "500 - " + str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


# Add WebSocket endpoints for real-time data
@app.websocket("/ws/trades/{symbol}")
async def websocket_trades(websocket: WebSocket, symbol: str):
    await trade_manager.connect(websocket)
    try:
        trade_manager.subscribe(websocket, symbol)
        while True:
            # Keep the connection alive and wait for client messages
            data = await websocket.receive_text()
            # You could process client messages here if needed
    except WebSocketDisconnect:
        trade_manager.disconnect(websocket)

@app.websocket("/ws/orderbook/{symbol}")
async def websocket_orderbook(websocket: WebSocket, symbol: str):
    await order_book_manager.connect(websocket)
    try:
        order_book_manager.subscribe(websocket, symbol)
        # Send initial order book snapshot
        order_book = matching_engine.get_order_book(symbol)
        order_book_data = order_book.get_order_book_snapshot()
        await websocket.send_text(json.dumps(order_book_data))
        
        while True:
            # Keep the connection alive and wait for client messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        order_book_manager.disconnect(websocket)

@app.websocket("/ws/bbo/{symbol}")
async def websocket_bbo(websocket: WebSocket, symbol: str):
    await bbo_manager.connect(websocket)
    try:
        bbo_manager.subscribe(websocket, symbol)
        # Send initial BBO
        order_book = matching_engine.get_order_book(symbol)
        bbo_data = order_book.get_bbo()
        await websocket.send_text(json.dumps(bbo_data))
        
        while True:
            # Keep the connection alive and wait for client messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        bbo_manager.disconnect(websocket)

# Add REST endpoints for order book and BBO data
@app.get("/api/orderbook/{symbol}", response_model=OrderBookResponse)
async def get_order_book(symbol: str):
    log_api_request("GET", f"/api/orderbook/{symbol}")
    order_book = matching_engine.get_order_book(symbol)
    return order_book.get_order_book_snapshot()

@app.get("/api/bbo/{symbol}", response_model=BBOResponse)
async def get_bbo(symbol: str):
    log_api_request("GET", f"/api/bbo/{symbol}")
    order_book = matching_engine.get_order_book(symbol)
    return order_book.get_bbo()

# Add endpoint to cancel orders
@app.delete("/api/orders/{order_id}", response_model=OrderResponse)
async def cancel_order(order_id: str, symbol: str = Query(...)):
    try:
        log_api_request("DELETE", f"/api/orders/{order_id}", {"symbol": symbol})
        
        # Cancel the order
        cancelled_order = matching_engine.cancel_order(order_id, symbol)
        
        if not cancelled_order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        log_order(cancelled_order, "cancelled")
        
        # Convert order to response format
        response_data = cancelled_order.to_dict()
        response_data["type"] = response_data.pop("order_type")
        
        return response_data
    
    except Exception as e:
        log_api_request("DELETE", f"/api/orders/{order_id}", {"symbol": symbol}, "500 - " + str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

# Add a simple HTML page for the web interface
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

# Create a directory for static files if it doesn't exist
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# Mount the static files directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_web_interface():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cryptocurrency Matching Engine</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            h1, h2 {
                color: #333;
            }
            .section {
                margin-bottom: 30px;
                padding: 20px;
                background-color: #f9f9f9;
                border-radius: 5px;
            }
            .order-form {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            input, select, button {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                width: 100%;
            }
            button {
                background-color: #4CAF50;
                color: white;
                cursor: pointer;
                border: none;
                font-weight: bold;
            }
            button:hover {
                background-color: #45a049;
            }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                padding: 8px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background-color: #f2f2f2;
            }
            .order-book {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }
            .bids, .asks {
                width: 100%;
            }
            .bids th {
                background-color: rgba(0, 128, 0, 0.1);
            }
            .asks th {
                background-color: rgba(255, 0, 0, 0.1);
            }
            #trades {
                max-height: 300px;
                overflow-y: auto;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Cryptocurrency Matching Engine</h1>
            
            <div class="section">
                <h2>Place Order</h2>
                <form id="orderForm" class="order-form">
                    <div>
                        <label for="symbol">Symbol:</label>
                        <input type="text" id="symbol" name="symbol" value="BTC-USDT" required>
                    </div>
                    <div>
                        <label for="side">Side:</label>
                        <select id="side" name="side" required>
                            <option value="buy">Buy</option>
                            <option value="sell">Sell</option>
                        </select>
                    </div>
                    <div>
                        <label for="type">Type:</label>
                        <select id="type" name="type" required>
                            <option value="limit">Limit</option>
                            <option value="market">Market</option>
                            <option value="ioc">IOC</option>
                            <option value="fok">FOK</option>
                        </select>
                    </div>
                    <div>
                        <label for="quantity">Quantity:</label>
                        <input type="number" id="quantity" name="quantity" step="0.00000001" min="0" required>
                    </div>
                    <div>
                        <label for="price">Price:</label>
                        <input type="number" id="price" name="price" step="0.01" min="0">
                    </div>
                    <div>
                        <label for="clientOrderId">Client Order ID (optional):</label>
                        <input type="text" id="clientOrderId" name="clientOrderId">
                    </div>
                    <div></div>
                    <div>
                        <button type="submit">Place Order</button>
                    </div>
                </form>
            </div>
            
            <div class="section">
                <h2>Order Book</h2>
                <div class="order-book">
                    <div class="bids">
                        <h3>Bids</h3>
                        <table id="bidsTable">
                            <thead>
                                <tr>
                                    <th>Price</th>
                                    <th>Quantity</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                    </div>
                    <div class="asks">
                        <h3>Asks</h3>
                        <table id="asksTable">
                            <thead>
                                <tr>
                                    <th>Price</th>
                                    <th>Quantity</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2>Recent Trades</h2>
                <table id="tradesTable">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Price</th>
                            <th>Quantity</th>
                            <th>Side</th>
                        </tr>
                    </thead>
                    <tbody id="trades"></tbody>
                </table>
            </div>
        </div>

        <script>
            // Current symbol
            let currentSymbol = 'BTC-USDT';
            
            // WebSocket connections
            let tradeSocket;
            let orderBookSocket;
            
            // Connect to WebSockets
            function connectWebSockets() {
                // Close existing connections if any
                if (tradeSocket) tradeSocket.close();
                if (orderBookSocket) orderBookSocket.close();
                
                // Connect to trade WebSocket
                tradeSocket = new WebSocket(`ws://${window.location.host}/ws/trades/${currentSymbol}`);
                tradeSocket.onmessage = function(event) {
                    console.log("Trade message received:", event.data);
                    try {
                        const trade = JSON.parse(event.data);
                        addTradeToTable(trade);
                    } catch (error) {
                        console.error("Error processing trade data:", error);
                    }
                };
                
                tradeSocket.onopen = function() {
                    console.log("Trade WebSocket connected");
                };
                
                tradeSocket.onerror = function(error) {
                    console.error("Trade WebSocket error:", error);
                };
                
                tradeSocket.onclose = function() {
                    console.log("Trade WebSocket closed, reconnecting in 3 seconds...");
                    setTimeout(connectWebSockets, 3000);
                };
                
                // Connect to order book WebSocket
                orderBookSocket = new WebSocket(`ws://${window.location.host}/ws/orderbook/${currentSymbol}`);
                orderBookSocket.onmessage = function(event) {
                    console.log("Order book message received:", event.data);
                    try {
                        const orderBook = JSON.parse(event.data);
                        updateOrderBook(orderBook);
                    } catch (error) {
                        console.error("Error processing order book data:", error);
                    }
                };
                
                orderBookSocket.onopen = function() {
                    console.log("Order book WebSocket connected");
                };
                
                orderBookSocket.onerror = function(error) {
                    console.error("Order book WebSocket error:", error);
                };
                
                orderBookSocket.onclose = function() {
                    console.log("Order book WebSocket closed, reconnecting in 3 seconds...");
                    setTimeout(connectWebSockets, 3000);
                };
            }
            
            // Add a trade to the trades table
            function addTradeToTable(trade) {
                const tbody = document.getElementById('trades');
                const row = document.createElement('tr');
                
                // Format timestamp
                const date = new Date(trade.timestamp);
                const time = date.toLocaleTimeString();
                
                row.innerHTML = `
                    <td>${time}</td>
                    <td>${trade.price}</td>
                    <td>${trade.quantity}</td>
                    <td>${trade.aggressor_side}</td>
                `;
                
                // Add the row at the top
                tbody.insertBefore(row, tbody.firstChild);
                
                // Limit to 50 trades
                if (tbody.children.length > 50) {
                    tbody.removeChild(tbody.lastChild);
                }
            }
            
            // Update the order book display
            function updateOrderBook(orderBook) {
                console.log("Received order book update:", orderBook);
                
                // Update bids
                const bidsBody = document.querySelector('#bidsTable tbody');
                bidsBody.innerHTML = '';
                
                if (orderBook.bids && Array.isArray(orderBook.bids)) {
                    orderBook.bids.forEach(bid => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${bid[0]}</td>
                            <td>${bid[1]}</td>
                        `;
                        bidsBody.appendChild(row);
                    });
                } else {
                    console.error("Invalid bids data:", orderBook.bids);
                }
                
                // Update asks
                const asksBody = document.querySelector('#asksTable tbody');
                asksBody.innerHTML = '';
                
                if (orderBook.asks && Array.isArray(orderBook.asks)) {
                    orderBook.asks.forEach(ask => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${ask[0]}</td>
                            <td>${ask[1]}</td>
                        `;
                        asksBody.appendChild(row);
                    });
                } else {
                    console.error("Invalid asks data:", orderBook.asks);
                }
            }
            
            // Handle order form submission
            document.getElementById('orderForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                
                // Get form data
                const formData = new FormData(this);
                const orderData = {
                    symbol: formData.get('symbol'),
                    side: formData.get('side'),
                    type: formData.get('type'),
                    quantity: formData.get('quantity')
                };
                
                // Add price if it's not a market order
                if (orderData.type !== 'market' && formData.get('price')) {
                    orderData.price = formData.get('price');
                }
                
                // Add client order ID if provided
                if (formData.get('clientOrderId')) {
                    orderData.client_order_id = formData.get('clientOrderId');
                }
                
                try {
                    // Send the order
                    const response = await fetch('/api/orders', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(orderData)
                    });
                    
                    if (!response.ok) {
                        const error = await response.json();
                        alert(`Error: ${error.detail}`);
                        return;
                    }
                    
                    const result = await response.json();
                    alert(`Order placed successfully! Order ID: ${result.order_id}`);
                    
                    // Update current symbol if changed
                    if (orderData.symbol !== currentSymbol) {
                        currentSymbol = orderData.symbol;
                        connectWebSockets();
                    }
                    
                } catch (error) {
                    alert(`Error: ${error.message}`);
                }
            });
            
            // Initialize
            document.addEventListener('DOMContentLoaded', function() {
                // Load initial order book
                fetch(`/api/orderbook/${currentSymbol}`)
                    .then(response => response.json())
                    .then(data => updateOrderBook(data))
                    .catch(error => console.error('Error loading order book:', error));
                
                // Connect to WebSockets
                connectWebSockets();
                
                // Handle type change to show/hide price field
                document.getElementById('type').addEventListener('change', function() {
                    const priceField = document.getElementById('price');
                    const priceLabel = document.querySelector('label[for="price"]');
                    
                    if (this.value === 'market') {
                        priceField.disabled = true;
                        priceField.required = false;
                        priceLabel.innerHTML = 'Price (not required for market orders):';
                    } else {
                        priceField.disabled = false;
                        priceField.required = true;
                        priceLabel.innerHTML = 'Price:';
                    }
                });
            });
        </script>
    </body>
    </html>
    """