# Cryptocurrency Matching Engine

This project implements a high-performance cryptocurrency matching engine based on price-time priority principles, inspired by REG NMS. It provides a real-time trading environment with API endpoints for order submission and real-time data dissemination via WebSockets.

## Objective

The primary objective is to develop a matching engine capable of processing trading orders efficiently, maintaining a real-time order book, calculating the Best Bid and Offer (BBO), and generating a stream of trade execution data.

## Features

*   **Matching Algorithm:** Implements strict price-time priority matching.
*   **Order Types:** Supports Market, Limit, Immediate-Or-Cancel (IOC), and Fill-Or-Kill (FOK) orders.
*   **Internal Order Protection:** Prevents internal trade-throughs by ensuring execution at the best available prices.
*   **Real-time Market Data:** Disseminates real-time BBO and Order Book depth via WebSockets.
*   **Trade Execution Data:** Generates and streams trade execution reports as trades occur.
*   **API:** Provides REST endpoints for order submission and data retrieval, and WebSocket endpoints for real-time feeds.
*   **Simple Web Interface:** Includes a basic HTML/JavaScript interface for interacting with the engine.

## Architecture

The project follows a simple architecture:

*   **Matching Engine Core (`engine/`)**: Contains the core logic for order book management, matching algorithms, and trade generation.
*   **API Layer (`api/server.py`)**: Built with FastAPI, handling incoming requests (REST and WebSocket) and interacting with the matching engine.
*   **Utilities (`utils/`)**: Provides helper functions, such as logging.
*   **Frontend (Embedded HTML/JS)**: A basic web interface served directly by the FastAPI application for demonstration purposes.

## Setup and Running

1.  **Install Dependencies:**
    It's recommended to use a virtual environment.
    ```bash
    python -m venv venv
    .\venv\Scripts\activate  # On Windows
    # source venv/bin/activate # On macOS/Linux
    ```
    Install the required packages using the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Application:**
    Execute the `main.py` file to start the FastAPI server using Uvicorn:
    ```bash
    python main.py
    ```

4.  **Access the Interface:**
    Open your web browser and navigate to `http://127.0.0.1:8000/`.

## Dependencies

The project relies on the following Python packages:

*   `fastapi`
*   `uvicorn`
*   `pydantic`
*   `python-multipart`
*   `websockets`

These are listed in the `requirements.txt` file.

