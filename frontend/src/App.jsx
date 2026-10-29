import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [url, setUrl] = useState("");
  const [repos, setRepos] = useState([]);
  const [selectedRepo, setSelectedRepo] = useState("");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);
  const [adding, setAdding] = useState(false);
  const [notice, setNotice] = useState("");
  const [apiOnline, setApiOnline] = useState(false);
  const [tab, setTab] = useState("Chat");

  const readyRepos = repos.filter(
    r => r.status === "completed" && r.repoId
  );

  const activeRepo = readyRepos.find(r => r.repoId === selectedRepo);

  function repoName(url) {
    return url.replace(/\/+$/, "").split("/").slice(-2).join("/");
  }

  useEffect(() => {
    let alive = true;

    async function checkHealth() {
      try {
        const response = await fetch(`${API}/health`);
        if (alive) setApiOnline(response.ok);
      } catch {
        if (alive) setApiOnline(false);
      }
    }

    checkHealth();
    const timer = setInterval(checkHealth, 10000);

    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const timer = setInterval(async () => {
      const pending = repos.filter(
        r => !["completed", "failed"].includes(r.status)
      );

      for (const repo of pending) {
        try {
          const response = await fetch(`${API}/repos/${repo.jobId}`);
          if (!response.ok) continue;

          const job = await response.json();

          setRepos(current =>
            current.map(r =>
              r.jobId === repo.jobId
                ? {
                    ...r,
                    status: job.status,
                    repoId: job.repo_id || r.repoId,
                  }
                : r
            )
          );
        } catch {
          // Retry on the next polling interval.
        }
      }
    }, 3000);

    return () => clearInterval(timer);
  }, [repos]);

  async function addRepo(e) {
    e.preventDefault();
    if (!url.trim() || adding) return;

    setAdding(true);
    setNotice("");

    try {
      const response = await fetch(`${API}/repos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });

      if (!response.ok) {
        if (response.status === 429) {
          throw new Error("Too many repos added. Please wait an hour.");
        }
        throw new Error(`Request failed (${response.status})`);
      }

      const data = await response.json();

      setRepos(current => [
        ...current,
        {
          url: url.trim(),
          jobId: data.job_id,
          repoId: data.repo_id || "",
          status: "queued",
        },
      ]);

      setUrl("");
      setNotice("Repository indexing started.");
      setTab("Repositories");
    } catch (error) {
      setNotice(error.message || "Could not add repository.");
    } finally {
      setAdding(false);
    }
  }

  async function askQuestion(e, suggestedQuestion) {
    e?.preventDefault();

    const prompt = (suggestedQuestion || question).trim();
    if (!prompt || !selectedRepo || asking) return;

    setQuestion("");
    setAsking(true);

    const userMessage = { role: "user", text: prompt };
    const answerIndex = messages.length + 1;

    setMessages(current => [
      ...current,
      userMessage,
      { role: "assistant", text: "", loading: true },
    ]);

    try {
      const response = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_id: selectedRepo,
          question: prompt,
          thread_id: "web-1",
        }),
      });

      if (!response.ok) {
        if (response.status === 429) {
          throw new Error("Too many requests. Please wait a minute and try again.");
        }
        if (response.status === 404) {
          throw new Error("Repository not found. Please index it first.");
        }
        if (response.status === 409) {
          throw new Error("Repository is still indexing. Please wait.");
        }
        throw new Error(`Request failed (${response.status})`);
      }

      if (!response.body) throw new Error("No response stream returned.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let answer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        answer += decoder.decode(value, { stream: true });

        setMessages(current =>
          current.map((message, index) =>
            index === answerIndex
              ? { ...message, text: answer, loading: false }
              : message
          )
        );
      }

      answer += decoder.decode();

      setMessages(current =>
        current.map((message, index) =>
          index === answerIndex
            ? { ...message, text: answer, loading: false }
            : message
        )
      );
    } catch (error) {
      setMessages(current =>
        current.map((message, index) =>
          index === answerIndex
            ? {
                ...message,
                text: `⚠️ ${error.message}`,
                loading: false,
              }
            : message
        )
      );
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="studio">
      <header className="studio-topbar">
        <div className="studio-brand">
          <div className="brand-mark">C</div>
          <span>cartograph<span className="brand-light">.studio</span></span>
        </div>

        <div className="topbar-project">
          <span className="topbar-label">PROJECT</span>
          <select
            value={selectedRepo}
            onChange={e => {
              setSelectedRepo(e.target.value);
              setMessages([]);
            }}
          >
            <option value="">Select repository</option>
            {readyRepos.map(repo => (
              <option key={repo.jobId} value={repo.repoId}>
                {repoName(repo.url)}
              </option>
            ))}
          </select>
        </div>

        <div className={`api-status ${apiOnline ? "connected" : ""}`}>
          <span />
          {apiOnline ? "API connected" : "API offline"}
        </div>
      </header>

      <div className="studio-layout">
        <aside className="studio-sidebar">
          <div className="sidebar-section-label">WORKSPACE</div>

          {[
            ["Chat", "◫"],
            ["Repositories", "▤"],
            ["Indexing", "◷"],
          ].map(([name, icon]) => (
            <button
              key={name}
              className={`sidebar-link ${tab === name ? "selected" : ""}`}
              onClick={() => setTab(name)}
            >
              <span>{icon}</span>{name}
            </button>
          ))}

          <div className="sidebar-divider" />

          <div className="sidebar-section-label repo-label">
            YOUR PROJECTS
            <button onClick={() => setTab("Repositories")} title="Add repository">+</button>
          </div>

          <div className="sidebar-repos">
            {repos.map(repo => (
              <button
                key={repo.jobId}
                className={`sidebar-repo ${
                  selectedRepo === repo.repoId ? "selected" : ""
                }`}
                onClick={() => {
                  if (repo.status === "completed" && repo.repoId) {
                    setSelectedRepo(repo.repoId);
                    setMessages([]);
                    setTab("Chat");
                  }
                }}
              >
                <span className="folder-icon">⌘</span>
                <span className="sidebar-repo-name">{repoName(repo.url)}</span>
                <span className={`repo-dot ${repo.status}`} />
              </button>
            ))}

            {repos.length === 0 && (
              <p className="sidebar-empty">Your repositories will appear here.</p>
            )}
          </div>

          <div className="sidebar-footer">
            <div className="footer-mark">C</div>
            <div>
              <strong>Cartograph</strong>
              <span>Code intelligence</span>
            </div>
          </div>
        </aside>

        <main className="studio-main">
          {tab === "Repositories" ? (
            <section className="management-page">
              <div className="page-kicker">YOUR CODEBASES</div>
              <h1>Repositories</h1>
              <p className="page-description">
                Connect a GitHub project and let Cartograph map its codebase.
              </p>

              <form className="repo-add-form" onSubmit={addRepo}>
                <input
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo"
                />
                <button disabled={adding || !url.trim()}>
                  {adding ? "Adding..." : "Add repository"}
                </button>
              </form>

              {notice && <p className="notice">{notice}</p>}

              <div className="management-list">
                {repos.map(repo => (
                  <div className="management-repo" key={repo.jobId}>
                    <div className="repo-large-icon">⌘</div>
                    <div className="management-repo-info">
                      <strong>{repoName(repo.url)}</strong>
                      <span>{repo.url}</span>
                      <small>Index status: {repo.status}</small>
                    </div>
                    <span className={`status-pill ${repo.status}`}>
                      {repo.status}
                    </span>
                    {repo.status === "completed" && repo.repoId && (
                      <button
                        className="open-project"
                        onClick={() => {
                          setSelectedRepo(repo.repoId);
                          setMessages([]);
                          setTab("Chat");
                        }}
                      >
                        Open →
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </section>
          ) : tab === "Indexing" ? (
            <section className="management-page">
              <div className="page-kicker">BACKGROUND JOBS</div>
              <h1>Indexing activity</h1>
              <p className="page-description">
                Track the current state of your repository indexing jobs.
              </p>

              <div className="management-list">
                {repos.map(repo => (
                  <div className="management-repo" key={repo.jobId}>
                    <div className="repo-large-icon">◷</div>
                    <div className="management-repo-info">
                      <strong>{repoName(repo.url)}</strong>
                      <span>Job ID: {repo.jobId}</span>
                      <small>Latest reported status: {repo.status}</small>
                    </div>
                    <span className={`status-pill ${repo.status}`}>
                      {repo.status}
                    </span>
                  </div>
                ))}
                {repos.length === 0 && <p>No indexing jobs yet.</p>}
              </div>
            </section>
          ) : (
            <>
              <div className="chat-page-heading">
                <div>
                  <div className="page-kicker">CODEBASE INTELLIGENCE</div>
                  <h1>
                    {activeRepo
                      ? repoName(activeRepo.url)
                      : "Understand any codebase."}
                  </h1>
                  <p>
                    {activeRepo
                      ? "Ask questions. Explore logic. Understand how it works."
                      : "Select an indexed project to start exploring."}
                  </p>
                </div>
                {activeRepo && <span className="indexed-label">● Indexed</span>}
              </div>

              <div className="chat-workspace">
                <section className="conversation">
                  <div className="conversation-scroll">
                    {messages.length === 0 ? (
                      <div className="welcome">
                        <div className="welcome-mark">C</div>
                        <div className="welcome-eyebrow">MEET YOUR CODEBASE GUIDE</div>
                        <h2>What do you want to understand?</h2>
                        <p>
                          Ask Cartograph about architecture, functions,
                          dependencies and execution flow.
                        </p>

                        <div className="prompt-grid">
                          {[
                            ["Architecture", "How is this project organised?"],
                            ["Find a function", "Where is the safe_path function defined?"],
                            ["Trace execution", "How does a question travel through Cartograph?"],
                            ["Search code", "How does hybrid_search work?"],
                          ].map(([title, prompt]) => (
                            <button
                              className="prompt-card"
                              key={title}
                              disabled={!selectedRepo || asking}
                              onClick={() => askQuestion(null, prompt)}
                            >
                              <span>{title}</span>
                              <strong>{prompt}</strong>
                              <span className="prompt-arrow">↗</span>
                            </button>
                          ))}
                        </div>

                        {!selectedRepo && (
                          <div className="select-hint">
                            Choose an indexed repository from the top bar to begin.
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="conversation-messages">
                        {messages.map((message, index) => (
                          <article
                            className={`chat-message ${message.role}`}
                            key={index}
                          >
                            <div className="message-avatar">
                              {message.role === "user" ? "Y" : "C"}
                            </div>
                            <div className="message-body">
                              <div className="message-name">
                                {message.role === "user" ? "You" : "Cartograph"}
                              </div>
                              {message.loading && !message.text ? (
                                <div className="thinking">
                                  <span /><span /><span />
                                  <small>Exploring the codebase…</small>
                                </div>
                              ) : (
                                <ReactMarkdown>{message.text}</ReactMarkdown>
                              )}
                            </div>
                          </article>
                        ))}
                      </div>
                    )}
                  </div>

                  <form
                    className="message-composer"
                    onSubmit={askQuestion}
                  >
                    <textarea
                      value={question}
                      onChange={e => setQuestion(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          askQuestion();
                        }
                      }}
                      placeholder={
                        selectedRepo
                          ? "Ask anything about your codebase..."
                          : "Select a repository to start asking..."
                      }
                      disabled={!selectedRepo || asking}
                      rows={2}
                    />
                    <div className="composer-tools">
                      <span>Enter to send · Shift + Enter for a new line</span>
                      <button
                        type="submit"
                        disabled={!selectedRepo || !question.trim() || asking}
                      >
                        {asking ? "Working…" : "Ask ↗"}
                      </button>
                    </div>
                  </form>
                </section>

                <aside className="context-panel">
                  <div className="context-heading">
                    <span>⌘</span>
                    <strong>Code context</strong>
                  </div>

                  {activeRepo ? (
                    <>
                      <div className="context-block">
                        <div className="context-label">ACTIVE REPOSITORY</div>
                        <strong>{repoName(activeRepo.url)}</strong>
                        <a href={activeRepo.url} target="_blank" rel="noreferrer">
                          View on GitHub ↗
                        </a>
                      </div>

                      <div className="context-block">
                        <div className="context-label">INDEX STATUS</div>
                        <div className="context-status">
                          <span className="repo-dot completed" />
                          Repository indexed
                        </div>
                        <p>
                          Cartograph can use its indexed repository tools
                          to investigate code questions.
                        </p>
                      </div>

                      <div className="context-block">
                        <div className="context-label">TRY ASKING</div>
                        {[
                          "Explain the architecture",
                          "Find important functions",
                          "Trace a request flow",
                        ].map(prompt => (
                          <button
                            className="context-prompt"
                            key={prompt}
                            disabled={asking}
                            onClick={() => setQuestion(prompt)}
                          >
                            {prompt}<span>↗</span>
                          </button>
                        ))}
                      </div>

                      <div className="context-note">
                        <strong>Source explorer</strong>
                        <p>
                          File-level citations will appear here when the
                          backend exposes source metadata with its answers.
                        </p>
                      </div>
                    </>
                  ) : (
                    <div className="context-empty">
                      <div>⌘</div>
                      <strong>No project selected</strong>
                      <p>Select an indexed repository to see its context.</p>
                    </div>
                  )}
                </aside>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}