import logging
import os
from datetime import datetime

# Configure logging
def setup_logger(name, log_file=None, level=logging.INFO):
    """Set up and return a logger with the given name and configuration."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler if log_file is provided
    if log_file:
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Create default loggers
engine_logger = setup_logger('engine', 'logs/engine.log')
api_logger = setup_logger('api', 'logs/api.log')
trade_logger = setup_logger('trades', 'logs/trades.log')

def log_order(order, action):
    """Log order-related actions."""
    engine_logger.info(
        f"Order {action}: ID={order.order_id}, Symbol={order.symbol}, "
        f"Type={order.order_type.value}, Side={order.side.value}, "
        f"Quantity={order.quantity}, Price={order.price}, Status={order.status.value}"
    )

def log_trade(trade):
    """Log trade executions."""
    trade_logger.info(
        f"Trade executed: ID={trade.trade_id}, Symbol={trade.symbol}, "
        f"Price={trade.price}, Quantity={trade.quantity}, "
        f"Maker={trade.maker_order_id}, Taker={trade.taker_order_id}, "
        f"Aggressor={trade.aggressor_side.value}"
    )

def log_api_request(method, endpoint, params=None, status_code=None):
    """Log API requests."""
    api_logger.info(
        f"API {method} {endpoint} - Params: {params} - Status: {status_code}"
    )