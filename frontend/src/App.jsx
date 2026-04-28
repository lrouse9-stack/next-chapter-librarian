import { useState } from "react";

const API_BASE_URL = "http://localhost:8000";

export default function App() {
  const [mood, setMood] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [recommendations, setRecommendations] = useState([]);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setRecommendations([]);

    try {
      const response = await fetch(`${API_BASE_URL}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mood }),
      });

      if (!response.ok) {
        throw new Error("Request failed");
      }

      const data = await response.json();
      console.log("Received data:", data);
      const recs = Array.isArray(data.recommendations) ? data.recommendations : [];
      setRecommendations(recs);
    } catch (err) {
      setError("Could not fetch recommendations.");
      setRecommendations([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <h1>The Next Chapter Librarian</h1>
      <p>Describe what you loved reading, and get your next recommendation.</p>

      <form onSubmit={handleSubmit} className="search-form">
        <input
          type="text"
          value={mood}
          onChange={(event) => setMood(event.target.value)}
          placeholder="What mood are you in today?"
          required
        />
        <button type="submit" disabled={loading}>
          {loading ? "Consulting..." : "Recommend"}
        </button>
      </form>

      <section className="results">
        <h2>Results</h2>
        {error && <p className="error">{error}</p>}
        {loading && <p className="loading">Consulting the card catalog...</p>}
        {!loading && !error && recommendations.length === 0 && (
          <p>No recommendations yet.</p>
        )}
        {!loading && recommendations.length > 0 && (
          <div className="results-grid">
            {recommendations.map((book, index) => (
              <article className="book-card" key={`${book.title}-${index}`}>
                <h3>{book.title}</h3>
                <p className="book-author">by {book.author}</p>
                <div className="librarian-note-box">
                  <p className="librarian-note-title">Librarian's Note</p>
                  <p>{book.librarians_note}</p>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
