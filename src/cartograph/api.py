
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from cartograph.onboard import add_repo
from cartograph.graph import graph

from fastapi.responses import StreamingResponse
from cartograph.tools import Context

import os
import json
import psycopg

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Cartograph API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def ensure_jobs_table():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS index_jobs (
                job_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                repo_id TEXT,
                status TEXT NOT NULL,
                result JSONB,
                error TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_repo ON index_jobs (repo_id)")


ensure_jobs_table()


def save_job(job_id, url, status, repo_id=None, result=None, error=None):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(
            """
            INSERT INTO index_jobs (job_id, url, repo_id, status, result, error)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_id) DO UPDATE SET
                repo_id = EXCLUDED.repo_id,
                status = EXCLUDED.status,
                result = EXCLUDED.result,
                error = EXCLUDED.error
            """,
            (job_id, url, repo_id, status, json.dumps(result) if result else None, error),
        )


def load_job(job_id):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        row = conn.execute(
            "SELECT job_id, url, repo_id, status, result, error FROM index_jobs WHERE job_id = %s",
            (job_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "job_id": row[0],
        "url": row[1],
        "repo_id": row[2],
        "status": row[3],
        "result": row[4],
        "error": row[5],
    }


def find_repo_status(repo_id):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        row = conn.execute(
            "SELECT status FROM index_jobs WHERE repo_id = %s AND status = 'completed' LIMIT 1",
            (repo_id,),
        ).fetchone()

    return {"status": row[0]} if row else None
# Request models
class RepoRequest(BaseModel):
    url: str


class AskRequest(BaseModel):
    repo_id: str
    question: str
    thread_id: str = "default"



# # Temporary in-memory job status storage
# repo_status = {}


# Background repository indexing
def index_repository(job_id: str, url: str):
    save_job(job_id, url, "in_progress")

    try:
        result = add_repo(url)
        save_job(job_id, url, "completed", repo_id=result["repo_id"], result=result)
    except Exception as e:
        save_job(job_id, url, "failed", error=str(e))


# Health check
@app.get("/health")
def health_check():
    return {"status": "healthy"}


# Submit a repository for indexing
@app.post("/repos", status_code=202)
def add_repository(
    request: RepoRequest,
    background_tasks: BackgroundTasks,
):
    job_id = str(uuid4())
    save_job(job_id, request.url, "queued")
    background_tasks.add_task(index_repository, job_id, request.url)
    return {"job_id": job_id,
            "status": "queued",
            "url": request.url,
            "message": "Repository indexing has been queued. Check the job status using the job_id."}


# Check indexing job status
@app.get("/repos/{job_id}")
def get_repository_status(job_id: str):
    job = load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Indexing job not found")
    return job


# # Find the indexing job for an actual repository ID
# def find_repo_status(repo_id: str):
#     for job in repo_status.values():
#         if job.get("actual_repo_id") == repo_id:
#             return job

#     return None


# Ask a question about an indexed repository
@app.post("/ask")
def ask_repository(request: AskRequest):
    # Confirm that indexing completed successfully
    status = find_repo_status(request.repo_id)

    if status is None:
        raise HTTPException(
            status_code=404,
            detail="Repository is not registered or indexing has not completed.",
        )

    if status["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Repository indexing status: {status['status']}",
        )

    # Locate the cloned repository directory
    repos_root = Path("data/repos").resolve()
    repo_path = (
        repos_root / request.repo_id.replace("/", "__")
    ).resolve()

    # Prevent paths from escaping the repositories directory
    if not repo_path.is_relative_to(repos_root):
        raise HTTPException(
            status_code=400,
            detail="Invalid repository ID",
        )

    if not repo_path.is_dir():
        raise HTTPException(
            status_code=404,
            detail="Repository directory not found",
        )

    # Run the existing LangGraph workflow
    initial_state = {
        "messages": [
            HumanMessage(content=request.question)
        ],
        "answer": None,
        "unread": [],
        "checks": 0,
        "kind": "",
        "todos": [],
        "notes": [],
        "blocked": False,
    }
    config = {
        "configurable": {
            "thread_id": request.thread_id,
        }
    }

    context = Context(repo_path=str(repo_path), repo_id=request.repo_id)

    # Stream the graph's final answer
    def generate():
        sent = False
        for update in graph.stream(
            initial_state,
            context=context,
            config=config,
            stream_mode="updates",
        ):
            
            for node_output in update.values():
                answer = node_output.get("answer")

                if answer is not None and not sent:
                    yield answer.answer + "\n"
                    sent = True

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
    )

@app.get("/threads/{thread_id}")
def get_thread(thread_id: str):
  config = {"configurable": {"thread_id": thread_id}}
  state = graph.get_state(config)
  messages = state.values.get("messages", [])
  return {
    "thread_id": thread_id,
    "messages": [{"role": m.type, "content": m.content} for m in messages],
  }