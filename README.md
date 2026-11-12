# 📚 The Next Chapter Librarian

An AI-powered book recommender that matches books to your **mood**. Tell the librarian how you're feeling, and it searches real books from Open Library, then uses an LLM to pick the best three and write a personalized *Librarian's Note* explaining why each one fits.

> *"I'm feeling nostalgic and a little lonely."* → three real books, each with a cozy, poetic note on why it might be your next chapter.

## How It Works

1. You enter a mood in the React frontend.
2. The FastAPI backend searches the [Open Library API](https://openlibrary.org/dev/docs/api/search) for up to 8 matching books.
3. Those real results are sent to a Groq-hosted LLM (Llama 3.3 70B by default), which picks the top 3 and writes a 2-sentence Librarian's Note for each.
4. The recommendations are returned to the UI and logged to PostgreSQL.

Because the LLM only chooses from real Open Library results, the books it recommends actually exist.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, Vite 5 |
| Backend | Python 3.11, FastAPI, Uvicorn, SQLAlchemy |
| Database | PostgreSQL 16 |
| AI | [Groq](https://groq.com/) (`llama-3.3-70b-versatile`) |
| Book data | [Open Library Search API](https://openlibrary.org/dev/docs/api/search) |
| Infra | Docker & Docker Compose |

## Project Structure

```text
next-chapter-librarian/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py          # FastAPI app, Open Library + Groq logic, DB model
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main UI
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── Dockerfile
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml
└── .gitignore
```

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- A free [Groq API key](https://console.groq.com/keys)

### 1. Clone the repository

```bash
git clone https://github.com/lrouse9-stack/next-chapter-librarian.git
cd next-chapter-librarian
```

### 2. Add your API key

Create a `.env` file in **both** `backend/` and the project root, each containing:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
```

- `backend/.env` is loaded by the backend container (`env_file` in `docker-compose.yml`).
- The root `.env` is used by Docker Compose to fill in `${GROQ_API_KEY}` in `docker-compose.yml`.

Both files are already listed in `.gitignore`, so your key won't be committed.

### 3. Run the app

```bash
docker compose up --build
```

Once everything is up:

| Service | URL |
| --- | --- |
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| PostgreSQL | `localhost:5432` |

Open http://localhost:5173, type a mood, and hit **Recommend**.

To stop the stack:

```bash
docker compose down        # keep database data
docker compose down -v     # also delete the database volume
```

## API Reference

### `GET /health`

Simple health check.

```json
{ "status": "ok" }
```

### `POST /recommend`

Returns up to three book recommendations for a mood.

**Request**

```json
{ "mood": "cozy and curious on a rainy day" }
```

**Response**

```json
{
  "mood": "cozy and curious on a rainy day",
  "recommendations": [
    {
      "title": "Book Title",
      "author": "Author Name",
      "librarians_note": "Two sentences on why this book matches your mood."
    }
  ],
  "source_count": 8
}
```

If no books are found or the AI step fails, `recommendations` is an empty list and a `message` field explains what happened.

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GROQ_API_KEY` | Yes | none | Your Groq API key |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model used for recommendations |
| `DATABASE_URL` | No | `postgresql://postgres:postgres@postgres:5432/librarian` | PostgreSQL connection string |

## Data Storage

Every successful recommendation is saved to a `recommendation_logs` table (created automatically on startup) with the mood query, the AI's response, and a timestamp.

## Troubleshooting

- **"Recommendation engine error" or empty results:** Check that `GROQ_API_KEY` is set correctly in both `.env` files, then restart with `docker compose up --build`.
- **Frontend can't reach the backend:** Make sure the backend is running on port 8000. CORS is configured for `http://localhost:5173` and `http://127.0.0.1:5173` only.
- **Port already in use:** Stop whatever is using ports 5173, 8000, or 5432, or change the port mappings in `docker-compose.yml`.

## Roadmap Ideas

- Book covers and links via Open Library
- A history page powered by the logged recommendations
- Smarter search (genre/theme extraction from the mood before querying)
- Tests and CI


## Acknowledgments

- [Open Library](https://openlibrary.org/) for the book data
- [Groq](https://groq.com/) for fast LLM inference
