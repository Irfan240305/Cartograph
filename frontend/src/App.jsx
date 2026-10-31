import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
function getThreadId(repoId) {
  return `web-${encodeURIComponent(repoId)}`;
}

function extractSources(rawText = "") {
  const markerSources = [];
  // Preferred format: explicit source metadata emitted by the backend.
  const sourcePattern = /\[Source:\s*path=([\'\"])(.*?)\1\s+reason=([\'\"])([\s\S]*?)\3\s*\]/g;
  let match;

  while ((match = sourcePattern.exec(rawText)) !== null) {
    const path = match[2].trim();
    const reason = match[4].trim();
    if (path) markerSources.push({ path, reason });
  }

  // Some /ask responses currently stream plain answer text without source
  // metadata. Recover explicit file paths mentioned in that latest answer.
  const text = rawText.replace(sourcePattern, "").trim();
  const fallbackSources = [];
  if (markerSources.length === 0) {
    const filePattern = /(?:[\w@.-]+\/)*[\w@.-]+\.(?:py|pyi|js|jsx|ts|tsx|java|kt|go|rs|cpp|c|h|hpp|cs|rb|php|sql|json|ya?ml|toml|md|html|css|sh)(?=[:),.;\s`]|$)/gi;
    const seen = new Set();
    while ((match = filePattern.exec(text)) !== null) {
      const path = match[0].replace(/[),.;]+$/, "");
      if (!seen.has(path)) {
        seen.add(path);
        fallbackSources.push({
          path,
          reason: "Referenced in the latest Cartograph answer."
        });
      }
    }
  }

  const sources = markerSources.length > 0 ? markerSources : fallbackSources;
  const uniqueSources = [
    ...new Map(sources.map(source => [source.path, source])).values(),
  ];
  return { text, sources: uniqueSources };
}



export default function App() {
  const [url, setUrl] = useState("");
  const [repos, setRepos] = useState([]);
  const [selectedRepo, setSelectedRepo] = useState(
    () => localStorage.getItem("cartograph:selectedRepo") || ""
  );
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);
  const [adding, setAdding] = useState(false);
  const [notice, setNotice] = useState("");
  const [apiOnline, setApiOnline] = useState(false);
  const [tab, setTab] = useState("Chat");
  const [historyRepo, setHistoryRepo] = useState("");

  const readyRepos = repos.filter(
    r => r.status === "completed" && r.repoId
  );

  const activeRepo = readyRepos.find(r => r.repoId === selectedRepo);

  // Show sources for the most recent assistant answer only. Keeping sources
  // from older answers here makes the explorer look stale after a new question.
  const latestAssistantMessage = [...messages]
    .reverse()
    .find(message => message.role === "assistant");
  const sourceFiles = latestAssistantMessage?.sources || [];

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

    return () => {
      alive = false;
    };
  }, []);
  
  // Load already-indexed repos from the backend, so the list survives reloads
  useEffect(() => {
    async function loadRepos() {
      try {
        const response = await fetch(`${API}/repos`);
        if (!response.ok) return;
        const data = await response.json();

        setRepos(current => {
          const known = new Set(current.map(r => r.repoId));
          const fromServer = data
            .filter(r => !known.has(r.repo_id))
            .map(r => ({
              url: r.url,
              jobId: r.repo_id,      // used only as a unique React key
              repoId: r.repo_id,
              status: "completed",
            }));
          return [...fromServer, ...current];
        });
      } catch {
        // Backend asleep or offline: the list just stays empty
      }
    }

    loadRepos();
  }, []);

  // Persist the selected repository across browser refreshes.
  useEffect(() => {
    if (selectedRepo) {
      localStorage.setItem("cartograph:selectedRepo", selectedRepo);
    } else {
      localStorage.removeItem("cartograph:selectedRepo");
    }
  }, [selectedRepo]);

  // Restore only the conversation belonging to the selected repository.
  useEffect(() => {
    setHistoryRepo("");

    if (!selectedRepo) {
      setMessages([]);
      setHistoryRepo("");
      return;
    }

    const storageKey = `cartograph:chat:${selectedRepo}`;

    try {
      const saved = localStorage.getItem(storageKey);
      const parsed = saved ? JSON.parse(saved) : [];
      const restored = Array.isArray(parsed)
        ? parsed.map((message, index) => ({
            ...message,
            id: message.id || `${selectedRepo}-${index}`,
            loading: false,
          }))
        : [];

      setMessages(restored);
    } catch (error) {
      console.error("Could not restore conversation:", error);
      setMessages([]);
    }

    setHistoryRepo(selectedRepo);
  }, [selectedRepo]);

  // Save only after the selected repository's history has been restored.
  useEffect(() => {
    if (!selectedRepo || historyRepo !== selectedRepo) return;

    try {
      localStorage.setItem(
        `cartograph:chat:${selectedRepo}`,
        JSON.stringify(messages)
      );
    } catch (error) {
      console.error("Could not save conversation:", error);
    }
  }, [messages, selectedRepo, historyRepo]);

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
    const repoId = selectedRepo;

    if (!prompt || !repoId || asking) return;

    const threadId = getThreadId(repoId);
    const userId = `${Date.now()}-user`;
    const assistantId = `${Date.now()}-assistant`;

    setQuestion("");
    setAsking(true);

    setMessages(current => [
      ...current,
      { id: userId, role: "user", text: prompt },
      {
        id: assistantId,
        role: "assistant",
        text: "",
        sources: [],
        loading: true,
      },
    ]);

    try {
      const response = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_id: repoId,
          question: prompt,
          thread_id: threadId,
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
      let rawAnswer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        rawAnswer += decoder.decode(value, { stream: true });
        const parsed = extractSources(rawAnswer);

        setMessages(current =>
          current.map(message =>
            message.id === assistantId
              ? {
                  ...message,
                  text: parsed.text,
                  sources: parsed.sources,
                  loading: true,
                }
              : message
          )
        );
      }

      rawAnswer += decoder.decode();
      const finalResult = extractSources(rawAnswer);

      setMessages(current =>
        current.map(message =>
          message.id === assistantId
            ? {
                ...message,
                text: finalResult.text,
                sources: finalResult.sources,
                loading: false,
              }
            : message
        )
      );
    } catch (error) {
      setMessages(current =>
        current.map(message =>
          message.id === assistantId
            ? {
                ...message,
                text: `⚠️ ${error.message || "Something went wrong."}`,
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
            disabled={asking}
            onChange={e => setSelectedRepo(e.target.value)}
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
                disabled={asking || repo.status !== "completed" || !repo.repoId}
                onClick={() => {
                  if (repo.status === "completed" && repo.repoId && !asking) {
                    setSelectedRepo(repo.repoId);
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
                        disabled={asking}
                        onClick={() => {
                          if (asking) return;
                          setSelectedRepo(repo.repoId);
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
                            key={message.id || index}
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
                            onClick={() => {
                              setQuestion(prompt);
                              const textarea = document.querySelector(".message-composer textarea");
                              textarea?.focus();
                            }}
                          >
                            {prompt}<span>↗</span>
                          </button>
                        ))}
                      </div>

                      <div className="context-note source-explorer">
                        <div className="source-heading">
                          <strong>Source explorer</strong>
                          <span>{sourceFiles.length} files</span>
                        </div>

                        {sourceFiles.length > 0 ? (
                          <div className="source-list">
                            {sourceFiles.map(source => (
                              <div className="source-item" key={source.path}>
                                <div className="source-file">
                                  <span>◇</span>
                                  <strong>{source.path}</strong>
                                </div>
                                <p>{source.reason}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p>
                            Sources will appear here after Cartograph reads
                            files to answer your question.
                          </p>
                        )}
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