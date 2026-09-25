import os
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.routers import auth, documents, chat, quiz

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Full-stack AI Study & Exam Prep Assistant with Multi-Doc RAG and AI Quizzes"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(documents.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(quiz.router, prefix=settings.API_V1_STR)


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        openapi_version="3.0.3"
    )
        # Make Swagger use simple Bearer JWT authentication
    security_schemes = schema.get("components", {}).get("securitySchemes", {})

    if "OAuth2PasswordBearer" in security_schemes:
        security_schemes["OAuth2PasswordBearer"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }

    upload_schema = schema["components"]["schemas"].get(
        "Body_upload_documents_api_documents_upload_post"
    )

    if upload_schema:
        files = upload_schema.get("properties", {}).get("files")

        if files:
            item = files.get("items", {})

            if item.get("contentMediaType") == "application/octet-stream":
                item.pop("contentMediaType", None)
                item["format"] = "binary"

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/")
def root():
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "docs_url": "/docs"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "groq_configured": bool(
            settings.GROQ_API_KEY
            and settings.GROQ_API_KEY != "your_groq_api_key_here"
        ),
        "database": "connected"
    }