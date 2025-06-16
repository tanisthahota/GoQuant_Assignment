import uvicorn
import os
from api.server import app
from utils.logger import setup_logger

# Create main logger
main_logger = setup_logger('main', 'logs/main.log')

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

def main():
    """
    Main entry point for the application.
    Starts the FastAPI server using uvicorn.
    """
    main_logger.info("Starting Cryptocurrency Matching Engine API")
    
    # Run the server
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()