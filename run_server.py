"""Entry point script for running the FastAPI application with Uvicorn."""

import uvicorn

if __name__ == "__main__":
    # Local development server
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8010,
        reload=True
    )

    # Deployment example (use 0.0.0.0 for external access)
    # uvicorn.run("app.main:app", host="0.0.0.0", port=10000)
