import { useState, useEffect } from "react";

import ReactMarkdown from "react-markdown";

const API = "http://localhost:8000";

export default function App() {
  const [url, setUrl] = useState("");
  const [repos, setRepos] = useState([]);
  const [status, setStatus] = useState("");

  // NEW: state for the Ask feature
  const [selectedRepo, setSelectedRepo] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [asking, setAsking] = useState(false);

  async function addRepo() {
    setStatus("Indexing repository...");

    const response = await fetch(`${API}/repos`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url: url }),
    });
    const data = await response.json();
    setRepos([...repos, { url: url, jobId: data.job_id, status: "queued" }]);
    setUrl("");
    setStatus(`Job started with ID: ${data.job_id}`);
  }

  // NEW: ask a question and stream the answer
  async function askQuestion() {
    setAnswer("");
    setAsking(true);

    const response = await fetch(`${API}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_id: selectedRepo,
        question: question,
        thread_id: "web-1",
      }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      setAnswer(prev => prev + decoder.decode(value));
    }

    setAsking(false);
  }

  useEffect(() => {
    const timer = setInterval(async () => {
      setRepos(current => {
        const unfinished = current.filter(
          r => r.status !== "completed" && r.status !== "failed"
        );
        if (unfinished.length === 0) return current;

        unfinished.forEach(async (r) => {
          const res = await fetch(`${API}/repos/${r.jobId}`);
          const job = await res.json();
          setRepos(prev =>
            prev.map(p =>
              p.jobId === r.jobId
                ? { ...p, status: job.status, repoId: job.repo_id }
                : p
            )
          );
        });

        return current;
      });
    }, 3000);

    return () => clearInterval(timer);
  }, []);

  return (
    <div>
      <h1>Cartograph</h1>

      <input
        value={url}
        onChange={e => setUrl(e.target.value)}
        placeholder="https://github.com/owner/repo"
      />
      <button onClick={addRepo}>Add</button>

      <p>{status}</p>

      <ul>
        {repos.map((r, i) => <li key={i}>{r.url} - {r.status || "queued"}</li>)}
      </ul>

      {/* NEW: the Ask section */}
      <hr />

      <select value={selectedRepo} onChange={e => setSelectedRepo(e.target.value)}>
        <option value="">Choose a repo</option>
        {repos
          .filter(r => r.status === "completed" && r.repoId)
          .map((r, i) => <option key={i} value={r.repoId}>{r.repoId}</option>)}
      </select>

      <input
        value={question}
        onChange={e => setQuestion(e.target.value)}
        placeholder="Ask about this repo..."
      />
      <button onClick={askQuestion} disabled={asking || !selectedRepo}>
        {asking ? "Thinking..." : "Ask"}
      </button>

      <pre>{answer && (
        <div className="answer">
          <ReactMarkdown>{answer}</ReactMarkdown>
        </div>
      )}</pre>
    </div>
  );
}