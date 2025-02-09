import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import asyncpg
import os
from typing import List, Optional, Dict, Any
from pathlib import Path
import sys

# Add parent directory to Python path
sys.path.append(str(Path(__file__).parent))

from github_agent import github_agent, GitHubDeps
from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection pool
pool = None

@app.on_event("startup")
async def startup():
    global pool
    try:
        pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
        print("Successfully connected to database")
    except Exception as e:
        print(f"Failed to connect to database: {str(e)}")
        raise

class AgentRequest(BaseModel):
    query: str
    session_id: str
    request_id: str

class AgentResponse(BaseModel):
    success: bool

@app.post("/api/github-agent")
async def github_agent_endpoint(request: AgentRequest):
    try:
        print(f"Received request: {request}")
        # Store user's query
        await store_message(
            session_id=request.session_id,
            message_type="human",
            content=request.query
        )            

        # Initialize agent dependencies
        async with httpx.AsyncClient() as client:
            deps = GitHubDeps(
                client=client,
                github_token=os.getenv("GITHUB_TOKEN")
            )

            # Run the agent
            result = await github_agent.run(
                request.query,
                deps=deps
            )

        # Store agent's response
        await store_message(
            session_id=request.session_id,
            message_type="ai",
            content=result.data,
            data={"request_id": request.request_id}
        )

        return AgentResponse(success=True)

    except Exception as e:
        print(f"Error processing agent request: {str(e)}")
        # Store error message in conversation
        await store_message(
            session_id=request.session_id,
            message_type="ai",
            content="I apologize, but I encountered an error processing your request.",
            data={"error": str(e), "request_id": request.request_id}
        )
        return AgentResponse(success=False)

async def store_message(session_id: str, message_type: str, content: str, data: Optional[Dict] = None):
    """Store a message in PostgreSQL."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO messages (session_id, type, content, data)
            VALUES ($1, $2, $3, $4)
            """,
            session_id, message_type, content, data
        )

if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")