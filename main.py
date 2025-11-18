import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId
import feedparser

from schemas import Article as ArticleSchema, Project as ProjectSchema
from database import db, create_document

app = FastAPI(title="World Politics News API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Simple admin auth (owner-only create/update/delete) ----
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

class AuthError(HTTPException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status_code=401, detail=detail)

def require_admin(x_admin_token: Optional[str] = Header(None)):
    if not ADMIN_TOKEN:
        # If not configured, lock down writes entirely
        raise AuthError("Admin not configured")
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise AuthError("Invalid admin token")


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
    response["admin_token"] = "✅ Set" if os.getenv("ADMIN_TOKEN") else "❌ Not Set"

    return response


# -------- Articles --------
@app.post("/api/articles")
def create_article(article: ArticleSchema, _: None = Depends(require_admin)):
    try:
        data = article.model_dump()
        data["deleted"] = False
        if data.get("published") and not data.get("published_at"):
            data["published_at"] = datetime.now(timezone.utc).isoformat()
        article_id = create_document("article", data)
        doc = db["article"].find_one({"_id": ObjectId(article_id)})
        return serialize_doc(doc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/articles")
def list_articles(
    q: Optional[str] = Query(None, description="Search in title/content/summary"),
    region: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(24, ge=1, le=100),
):
    try:
        filters = {"published": True, "deleted": {"$ne": True}}
        if region:
            filters["region"] = region
        if category:
            filters["category"] = category
        if q:
            filters["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"content": {"$regex": q, "$options": "i"}},
                {"summary": {"$regex": q, "$options": "i"}},
            ]
        cursor = db["article"].find(filters).sort("published_at", -1).limit(limit)
        return [serialize_doc(d) for d in cursor]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/articles/{article_id}")
def get_article(article_id: str):
    try:
        doc = db["article"].find_one({"_id": ObjectId(article_id), "published": True, "deleted": {"$ne": True}})
        if not doc:
            raise HTTPException(status_code=404, detail="Article not found")
        return serialize_doc(doc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    region: Optional[str] = None
    tags: Optional[list[str]] = None
    author: Optional[str] = None
    image_url: Optional[str] = None
    published: Optional[bool] = None

@app.put("/api/articles/{article_id}")
def update_article(article_id: str, payload: ArticleUpdate, _: None = Depends(require_admin)):
    try:
        update = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not update:
            raise HTTPException(status_code=400, detail="Nothing to update")
        update["updated_at"] = datetime.now(timezone.utc)
        # handle published state
        if "published" in update and update["published"]:
            update.setdefault("published_at", datetime.now(timezone.utc).isoformat())
        res = db["article"].update_one({"_id": ObjectId(article_id), "deleted": {"$ne": True}}, {"$set": update})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Article not found")
        doc = db["article"].find_one({"_id": ObjectId(article_id)})
        return serialize_doc(doc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/articles/{article_id}")
def delete_article(article_id: str, _: None = Depends(require_admin)):
    try:
        res = db["article"].update_one({"_id": ObjectId(article_id)}, {"$set": {"deleted": True, "published": False, "updated_at": datetime.now(timezone.utc)}})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Article not found")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/articles/admin")
def admin_list_articles(q: Optional[str] = None, published: Optional[bool] = None, limit: int = Query(50, ge=1, le=200), _: None = Depends(require_admin)):
    try:
        filters = {"deleted": {"$ne": True}}
        if published is not None:
            filters["published"] = published
        if q:
            filters["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"content": {"$regex": q, "$options": "i"}},
                {"summary": {"$regex": q, "$options": "i"}},
            ]
        cursor = db["article"].find(filters).sort("updated_at", -1).limit(limit)
        return [serialize_doc(d) for d in cursor]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Projects --------
@app.post("/api/projects")
def create_project(project: ProjectSchema, _: None = Depends(require_admin)):
    try:
        project_id = create_document("project", project)
        doc = db["project"].find_one({"_id": ObjectId(project_id)})
        return serialize_doc(doc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/projects")
def list_projects(tag: Optional[str] = None, status: Optional[str] = None, limit: int = Query(24, ge=1, le=100)):
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


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    link: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None

@app.put("/api/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate, _: None = Depends(require_admin)):
    try:
        update = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not update:
            raise HTTPException(status_code=400, detail="Nothing to update")
        update["updated_at"] = datetime.now(timezone.utc)
        res = db["project"].update_one({"_id": ObjectId(project_id)}, {"$set": update})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Project not found")
        doc = db["project"].find_one({"_id": ObjectId(project_id)})
        return serialize_doc(doc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, _: None = Depends(require_admin)):
    try:
        res = db["project"].delete_one({"_id": ObjectId(project_id)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- RSS ingestion (optional) --------
class RSSRequest(BaseModel):
    url: str
    max_items: int = 10
    tag: Optional[str] = None
    region: Optional[str] = None
    category: Optional[str] = None

@app.post("/api/rss/preview")
def rss_preview(req: RSSRequest):
    try:
        feed = feedparser.parse(req.url)
        items = []
        for entry in feed.entries[: req.max_items]:
            items.append({
                "title": entry.get("title"),
                "summary": entry.get("summary") or entry.get("subtitle"),
                "link": entry.get("link"),
                "published": entry.get("published") or entry.get("updated"),
            })
        return {"feed_title": feed.feed.get("title"), "items": items}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
