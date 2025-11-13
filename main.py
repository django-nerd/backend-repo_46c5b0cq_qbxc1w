import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Book

app = FastAPI(title="Books + Audio Summaries API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Books API is running"}

@app.get("/test")
def test_database():
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
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response

# Pydantic request model for creation/update
class BookCreate(BaseModel):
    title: str
    author: str
    category: str
    description: Optional[str] = None
    text_summary: Optional[str] = None
    cover_image_url: Optional[str] = None
    audio_summary_url: Optional[str] = None


@app.post("/api/books")
def create_book(book: BookCreate):
    try:
        book_id = create_document("book", book)
        return {"id": book_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/books")
def list_books(q: Optional[str] = None, category: Optional[str] = None, limit: int = 100):
    try:
        filter_dict = {}
        if category:
            filter_dict["category"] = {"$regex": category, "$options": "i"}
        # basic text search on title/author/description
        if q:
            filter_dict["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"author": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
            ]
        docs = get_documents("book", filter_dict, limit)
        # serialize ObjectId and datetime
        def serialize(doc):
            doc["id"] = str(doc.pop("_id"))
            for k, v in list(doc.items()):
                if hasattr(v, "isoformat"):
                    doc[k] = v.isoformat()
            return doc
        return [serialize(d) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/books/{book_id}")
def get_book(book_id: str):
    try:
        if db is None:
            raise Exception("Database not available")
        doc = db["book"].find_one({"_id": ObjectId(book_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Book not found")
        doc["id"] = str(doc.pop("_id"))
        for k, v in list(doc.items()):
            if hasattr(v, "isoformat"):
                doc[k] = v.isoformat()
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/books/{book_id}")
def delete_book(book_id: str):
    try:
        if db is None:
            raise Exception("Database not available")
        res = db["book"].delete_one({"_id": ObjectId(book_id)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Book not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
