import os
import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8010"))
    reload = os.getenv("RELOAD", "false").strip().lower() in {"true", "1", "yes"}

    print("=" * 70)
    print(f"🚀 Launching DCLM Church Management System on http://{host}:{port}")
    print(f"   - Faststrap Admin UI: http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}/")
    print(f"   - FastAPI Backend API: http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}/api/v1")
    print(f"   - In-Memory ASGI Transport: ACTIVE (0ms socket latency)")
    print("=" * 70)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
    )
