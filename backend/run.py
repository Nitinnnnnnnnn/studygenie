import uvicorn

if __name__ == "__main__":
    print("Starting StudyGenie Backend Server on http://localhost:8000...")
    print("Swagger API documentation available at http://localhost:8000/docs")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
