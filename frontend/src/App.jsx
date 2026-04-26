import { useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function App() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        throw new Error("Request failed");
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError("Could not fetch recommendations.");
      setResult(null);
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
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="I liked a fast-paced mystery with strong characters..."
          required
        />
        <button type="submit" disabled={loading}>
          {loading ? "Searching..." : "Recommend"}
        </button>
      </form>

      <section className="results">
        <h2>Results</h2>
        {error && <p className="error">{error}</p>}
        {!error && !result && <p>No recommendations yet.</p>}
        {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
      </section>
    </main>
  );
}
