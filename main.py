import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from schemas import Article as ArticleSchema, Project as ProjectSchema
from database import db, create_document, get_documents

app = FastAPI(title="World Politics News API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers
class ObjectIdStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str):
            try:
                _ = ObjectId(v)
                return v
            except Exception:
                raise ValueError("Invalid ObjectId string")
        raise ValueError("Invalid ObjectId value")


def serialize_doc(doc: dict) -> dict:
    d = {**doc}
    if d.get("_id") is not None:
        d["id"] = str(d.pop("_id"))
    # Convert datetime to isoformat if present
    for key in ["created_at", "updated_at", "published_at"]:
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat()
    return d


@app.get("/")
def read_root():
    return {"message": "World Politics News API running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Articles Endpoints
@app.post("/api/articles")
def create_article(article: ArticleSchema):
    try:
        article_id = create_document("article", article)
        doc = db["article"].find_one({"_id": ObjectId(article_id)})
        return serialize_doc(doc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/articles")
def list_articles(
    q: Optional[str] = Query(None, description="Search query in title or content"),
    region: Optional[str] = None,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    try:
        filters = {}
        if region:
            filters["region"] = region
        if category:
            filters["category"] = category
        if tag:
            filters["tags"] = {"$in": [tag]}
        if q:
            filters["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"content": {"$regex": q, "$options": "i"}},
                {"summary": {"$regex": q, "$options": "i"}},
            ]
        # Only published by default
        # If client wants drafts, they can explicitly pass published=false in the future
        filters.setdefault("published", True)

        cursor = db["article"].find(filters).sort("created_at", -1).limit(limit)
        return [serialize_doc(d) for d in cursor]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Projects Endpoints
@app.post("/api/projects")
def create_project(project: ProjectSchema):
    try:
        project_id = create_document("project", project)
        doc = db["project"].find_one({"_id": ObjectId(project_id)})
        return serialize_doc(doc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/projects")
def list_projects(
    tag: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    try:
        filters = {}
        if tag:
            filters["tags"] = {"$in": [tag]}
        if status:
            filters["status"] = status
        cursor = db["project"].find(filters).sort("created_at", -1).limit(limit)
        return [serialize_doc(d) for d in cursor]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
