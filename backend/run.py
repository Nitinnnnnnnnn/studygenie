import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))

    print(f"Starting StudyGenie Backend Server on port {port}...")
    print(f"Swagger API documentation available at /docs")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port
    )