import json
import os
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/librarian"
)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendRequest(BaseModel):
    mood: str


async def search_open_library(mood: str) -> list[dict[str, str]]:
    params = {"q": mood, "limit": 8}
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(OPEN_LIBRARY_SEARCH_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    books: list[dict[str, str]] = []
    for doc in payload.get("docs", [])[:8]:
        title = str(doc.get("title", "Unknown Title"))
        authors = doc.get("author_name") or ["Unknown Author"]
        author = ", ".join([str(a) for a in authors[:2]])
        books.append(
            {
                "title": title,
                "author": author,
            }
        )
    return books


def _extract_json(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    # First try direct JSON parse.
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Remove markdown code fences if present.
    if "```" in cleaned:
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # Fallback: extract the first JSON object block from conversational filler.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start : end + 1])

    raise json.JSONDecodeError("No JSON object found in model output.", cleaned, 0)


def rank_books_with_ai(mood: str, books: list[dict[str, str]]) -> list[dict[str, str]]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY is missing from environment!")
        return []

    # Force the base_url to the bare minimum to prevent double-prefixing
    client = Groq(
        api_key=api_key,
        base_url="https://api.groq.com" 
    )
    prompt = (
        "You are a cozy librarian. Based on these search results and the user's mood, "
        "pick the best 3 books. For each, write a 2-sentence Librarian's Note "
        "explaining why it matches their feeling.\n\n"
        f"User mood: {mood}\n\n"
        "Search results (real books):\n"
        f"{json.dumps(books, indent=2)}\n\n"
        "Return ONLY valid JSON with this exact shape:\n"
        '{"picks":[{"title":"...","author":"...","librarians_note":"..."}]}'
    )

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.7,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a world-class librarian with the soul of a poet. "
                        "Use sophisticated, cozy language. Do not just list facts; "
                        "tell the user why this book will heal their heart or ignite "
                        "their imagination."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as e:
        print(f"Groq Error: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail="Groq request failed while generating recommendations.",
        ) from e
    content = completion.choices[0].message.content or ""

    try:
        parsed = _extract_json(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Groq returned non-JSON output; try again.",
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
    mood = payload.mood.strip()
    if not mood:
        raise HTTPException(status_code=400, detail="Mood cannot be empty.")
    print(f"Mood: {mood}")

    try:
        books = await search_open_library(mood)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Open Library request failed: {exc}",
        ) from exc
    print(f"Books found: {len(books)}")

    if not books:
        return {
            "mood": mood,
            "recommendations": [],
            "message": "I could not find books for that mood yet. Try a different feeling.",
        }

    try:
        picks = rank_books_with_ai(mood, books)
    except HTTPException as exc:
        return {
            "mood": mood,
            "recommendations": [],
            "message": f"Recommendation engine error: {exc.detail}",
        }
    except Exception as exc:
        return {
            "mood": mood,
            "recommendations": [],
            "message": f"Recommendation engine failed unexpectedly: {exc}",
        }

    log_recommendation(mood, picks)

    return {
        "mood": mood,
        "recommendations": picks,
        "source_count": len(books),
    }
