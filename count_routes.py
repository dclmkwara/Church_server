
import sys
import os
import asyncio

sys.path.append(os.getcwd())

from app.main import app

def count_routes():
    routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            methods = ",".join(route.methods)
            routes.append(f"{methods} {route.path}")
    
    print(f"Total Routes: {len(routes)}")
    print("--- Sample Routes ---")
    for r in routes[:10]:
        print(r)
    print("...")

if __name__ == "__main__":
    count_routes()
