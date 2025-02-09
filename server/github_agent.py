from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, List, Dict
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import shutil
import time
import re
import json

import httpx
import logfire
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIModel
from devtools import debug

load_dotenv()

@dataclass
class GitHubDeps:
    client: httpx.AsyncClient
    github_token: str | None = None

llm = 'google/gemini-2.0-flash-001'
model = OpenAIModel(
    llm,
    base_url = 'https://openrouter.ai/api/v1',
    api_key=os.getenv('OPEN_ROUTER_API_KEY')
)

system_prompt = """
You are a coding expert with access to GitHub to help the user manage their repository and get information from it.

Your only job is to assist with this and you don't answer other questions besides describing what you are able to do.

Don't ask the user before taking an action, just do it. Always make sure you look at the repository with the provided tools before answering the user's question unless you have already.

When answering a question about the repo, always start your answer with the full repo URL in brackets and then give your answer on a newline. Like:

[Using https://github.com/[repo URL from the user]]

Your answer here...
"""

github_agent = Agent(
    model,
    system_prompt=system_prompt,
    deps_type=GitHubDeps,
    retries=2
)

@github_agent.tool
async def get_repo_info(ctx: RunContext[GitHubDeps], github_url: str) -> str:
    """Get repository information using GitHub API.

    Args:
        ctx: The context containing dependencies.
        github_url: The GitHub repository URL.

    Returns:
        str: Repository information as a formatted string.
    """
    match = re.search(r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$', github_url)
    if not match:
        return "Invalid GitHub URL format"

    owner, repo = match.groups()
    headers = {'Authorization': f'token {ctx.deps.github_token}'} if ctx.deps.github_token else {}

    response = await ctx.deps.client.get(
        f'https://api.github.com/repos/{owner}/{repo}',
        headers=headers
    )

    if response.status_code != 200:
        return f"Failed to get repository info: {response.text}"

    data = response.json()
    size_mb = data['size'] / 1024

    return (
        f"Repository: {data['full_name']}\n"
        f"Description: {data['description']}\n"
        f"Size: {size_mb:.1f}MB\n"
        f"Stars: {data['stargazers_count']}\n"
        f"Language: {data['language']}\n"
        f"Created: {data['created_at']}\n"
        f"Last Updated: {data['updated_at']}"
    )