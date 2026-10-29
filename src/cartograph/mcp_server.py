import os
import httpx
from mcp.server.fastmcp import FastMCP

API = os.getenv("CARTOGRAPH_API", "https://ca-cartograph.wittysmoke-9790e289.uaenorth.azurecontainerapps.io")

mcp = FastMCP("cartograph")

@mcp.tool()
def list_repos() -> list[dict]:
  """List the code repositories Cartograph has indexed and can answer questions about."""
  response = httpx.get(f"{API}/repos", timeout=120)
  response.raise_for_status()
  return response.json()


@mcp.tool()
def ask_repo(repo_id: str, question:str) -> str:
      
      """Ask Cartograph a question about an indexed repository's code.
      repo_id looks like 'Irfan240305/OmniReserve'. Returns an answer with cited source files."""

      response = httpx.post(f"{API}/ask", json={"repo_id": repo_id, "question": question, "thread_id": "mcp"}, timeout=300)
      response.raise_for_status()
      return response.text


if __name__ == "__main__":
    mcp.run()


