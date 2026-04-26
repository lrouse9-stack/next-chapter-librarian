import json
import os
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/librarian"
)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class Base(DeclarativeBase):
    pass


class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mood_query: Mapped[str] = mapped_column(Text, nullable=False)
    ai_response: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="The Next Chapter Librarian API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendRequest(BaseModel):
    query: str


def _normalize_first_sentence(doc: dict[str, Any]) -> str:
    first_sentence = doc.get("first_sentence")
    if isinstance(first_sentence, str):
        return first_sentence
    if isinstance(first_sentence, list) and first_sentence:
        first = first_sentence[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict) and "value" in first:
            return str(first["value"])
    if isinstance(first_sentence, dict) and "value" in first_sentence:
        return str(first_sentence["value"])
    return "No first sentence/description available."


async def search_open_library(mood: str) -> list[dict[str, str]]:
    params = {"q": mood, "limit": 10}
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(OPEN_LIBRARY_SEARCH_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    books: list[dict[str, str]] = []
    for doc in payload.get("docs", [])[:10]:
        title = str(doc.get("title", "Unknown Title"))
        authors = doc.get("author_name") or ["Unknown Author"]
        author = ", ".join([str(a) for a in authors[:2]])
        first_sentence = _normalize_first_sentence(doc)
        books.append(
            {
                "title": title,
                "author": author,
                "description": first_sentence,
            }
        )
    return books


def _extract_json(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    return json.loads(cleaned)


def rank_books_with_ai(mood: str, books: list[dict[str, str]]) -> list[dict[str, str]]:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is missing. Set it in backend environment.",
        )

    client = OpenAI()
    prompt = (
        "You are a cozy librarian. Based on the user's mood and this list of real books, "
        "pick the 3 best matches and write a 2-sentence Librarian's Note for each.\n\n"
        f"User mood: {mood}\n\n"
        "Books:\n"
        f"{json.dumps(books, indent=2)}\n\n"
        "Return ONLY valid JSON with this exact shape:\n"
        '{"picks":[{"title":"...","author":"...","librarians_note":"..."}]}'
    )

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.7,
        messages=[
            {
                "role": "system",
                "content": "You are a warm, thoughtful librarian assistant.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = completion.choices[0].message.content or ""

    try:
        parsed = _extract_json(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="OpenAI returned non-JSON output; try again.",
        ) from exc

    picks = parsed.get("picks", [])
    if not isinstance(picks, list):
        raise HTTPException(status_code=502, detail="Invalid AI response format.")
    return picks[:3]


def log_recommendation(query: str, picks: list[dict[str, str]]) -> None:
    with Session(engine) as session:
        row = RecommendationLog(mood_query=query, ai_response=json.dumps(picks))
        session.add(row)
        session.commit()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/recommend")
async def recommend_books(payload: RecommendRequest) -> dict[str, Any]:
    mood = payload.query.strip()
    if not mood:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        books = await search_open_library(mood)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Open Library request failed: {exc}",
        ) from exc

    if not books:
        return {"query": mood, "recommendations": [], "message": "No books found."}

    picks = rank_books_with_ai(mood, books)
    log_recommendation(mood, picks)

    return {
        "query": mood,
        "recommendations": picks,
        "source_count": len(books),
    }
