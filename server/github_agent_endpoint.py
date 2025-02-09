import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import asyncpg
import os
from typing import List, Optional, Dict, Any, Union
import logging
import json
from cachetools import TTLCache
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for repository data (TTL of 5 minutes)
repo_cache = TTLCache(maxsize=100, ttl=300)

# Rate limiting settings
RATE_LIMIT_WINDOW = 60  # 1 minute
MAX_REQUESTS_PER_WINDOW = 30
request_timestamps = []

try:
    from github_agent import github_agent, GitHubDeps, GitHubResult, Failed
    from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure pydantic-ai is installed: pip install -r requirements.txt")
    raise

app = FastAPI(title="GitHub Agent API")

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
        logger.info("Successfully connected to database")
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise

class AgentRequest(BaseModel):
    """Request model for the GitHub agent endpoint."""
    query: str
    sessionId: str = Field(alias="session_id")
    requestId: str = Field(alias="request_id")

    class Config:
        populate_by_name = True

class AgentResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    repo_url: Optional[str] = None

def check_rate_limit():
    """Check if we're within rate limits"""
    current_time = time.time()
    # Remove timestamps older than the window
    while request_timestamps and current_time - request_timestamps[0] > RATE_LIMIT_WINDOW:
        request_timestamps.pop(0)
    # Check if we're at the limit
    if len(request_timestamps) >= MAX_REQUESTS_PER_WINDOW:
        return False
    request_timestamps.append(current_time)
    return True

@app.post("/api/github-agent")
async def github_agent_endpoint(request: AgentRequest):
    try:
        logger.info(f"Received request: {request}")
        
        # Check rate limit
        if not check_rate_limit():
            error_msg = "Rate limit exceeded. Please try again in a minute."
            logger.warning(error_msg)
            return AgentResponse(success=False, error=error_msg, message=error_msg)

        # Store user's query
        await store_message(
            session_id=request.sessionId,
            message_type="human",
            content=request.query
        )            

        # Check cache first if it's a repository query
        cache_key = f"{request.query}_{request.githubUrl if hasattr(request, 'githubUrl') else ''}"
        if cache_key in repo_cache:
            logger.info("Returning cached response")
            cached_response = repo_cache[cache_key]
            await store_message(
                session_id=request.sessionId,
                message_type="ai",
                content=cached_response['content'],
                data=json.dumps({
                    "request_id": request.requestId,
                    "repo_url": cached_response.get('repo_url')
                })
            )
            return AgentResponse(
                success=True,
                message=cached_response['content'],
                repo_url=cached_response.get('repo_url')
            )

        # Initialize agent dependencies
        async with httpx.AsyncClient() as client:
            deps = GitHubDeps(
                client=client,
                github_token=os.getenv("GITHUB_TOKEN")
            )

            logger.debug("Running agent with query: %s", request.query)
            # Run the agent
            result = await github_agent.run(
                request.query,
                deps=deps
            )
            logger.debug("Agent result: %s", result)

            # Handle different result types
            if isinstance(result.data, Failed):
                error_msg = f"Agent failed: {result.data.reason}"
                logger.error(error_msg)
                await store_message(
                    session_id=request.sessionId,
                    message_type="ai",
                    content=error_msg,
                    data=json.dumps({
                        "error": error_msg,
                        "request_id": request.requestId
                    })
                )
                return AgentResponse(
                    success=False,
                    error=error_msg,
                    message=error_msg
                )

            # Handle successful result
            response = result.data.content
            repo_url = result.data.repo_url

            # Cache the successful response
            repo_cache[cache_key] = {
                'content': response,
                'repo_url': repo_url
            }

            # Store agent's response
            await store_message(
                session_id=request.sessionId,
                message_type="ai",
                content=response,
                data=json.dumps({
                    "request_id": request.requestId,
                    "repo_url": repo_url
                })
            )

            return AgentResponse(
                success=True, 
                message=response,
                repo_url=repo_url
            )

    except Exception as e:
        logger.error(f"Error processing agent request: {str(e)}", exc_info=True)
        error_msg = "I apologize, but I encountered an error processing your request."
        # Store error message in conversation
        await store_message(
            session_id=request.sessionId,
            message_type="ai",
            content=error_msg,
            data=json.dumps({
                "error": str(e), 
                "request_id": request.requestId
            })
        )
        return AgentResponse(success=False, error=str(e), message=error_msg)

async def store_message(session_id: str, message_type: str, content: str, data: Optional[str] = None):
    """Store a message in PostgreSQL.
    
    Args:
        session_id: The session ID
        message_type: The type of message (human/ai)
        content: The message content
        data: JSON string of additional data
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO messages (session_id, type, content, data)
                VALUES ($1, $2, $3, $4)
                """,
                session_id, message_type, content, data
            )
    except Exception as e:
        logger.error(f"Failed to store message: {str(e)}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint to verify the server is running."""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")