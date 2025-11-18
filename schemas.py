"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List

# Example schemas (replace with your own):

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# News website schemas

class Article(BaseModel):
    """
    Political news articles
    Collection name: "article"
    """
    title: str = Field(..., description="Headline")
    summary: Optional[str] = Field(None, description="Short summary/dek")
    content: str = Field(..., description="Full article content (markdown or plain text)")
    category: str = Field(..., description="Topic/category, e.g., Elections, Policy, Diplomacy")
    region: str = Field(..., description="Region or country, e.g., Global, USA, EU, Asia")
    tags: List[str] = Field(default_factory=list, description="Keywords/tags")
    author: Optional[str] = Field(None, description="Author name")
    image_url: Optional[str] = Field(None, description="Hero image URL")
    published: bool = Field(True, description="Whether the article is published")
    published_at: Optional[str] = Field(None, description="ISO timestamp for publication time")

class Project(BaseModel):
    """
    Projects you want to showcase related to the news site
    Collection name: "project"
    """
    name: str = Field(..., description="Project name")
    description: str = Field(..., description="What the project is about")
    link: Optional[str] = Field(None, description="External link to project")
    tags: List[str] = Field(default_factory=list, description="Keywords/tags")
    status: str = Field("active", description="Status: active, paused, completed")

# Add your own schemas here:
# --------------------------------------------------

# Note: The Flames database viewer will automatically:
# 1. Read these schemas from GET /schema endpoint
# 2. Use them for document validation when creating/editing
# 3. Handle all database operations (CRUD) directly
# 4. You don't need to create any database endpoints!
