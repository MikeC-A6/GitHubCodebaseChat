from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Union
import logging
from dotenv import load_dotenv

import httpx
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic import BaseModel, Field

from github import (
    get_repo_info, list_contents, get_file_content, analyze_codebase,
    GitHubAPI, GitHubAPIError
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress LogFire warning
os.environ['LOGFIRE_IGNORE_NO_CONFIG'] = '1'

load_dotenv()

@dataclass
class GitHubDeps:
    client: httpx.AsyncClient
    github_token: str | None = None

class Failed(BaseModel):
    """Used when the agent fails to process the request."""
    reason: str

class GitHubResult(BaseModel):
    """Result type for GitHub agent responses."""
    content: str = Field(description="The response to return to the user")
    repo_url: str | None = Field(None, description="The GitHub repository URL being referenced")

system_prompt = """
You are a coding expert with access to GitHub to help the user manage their repository and get information from it.

Your capabilities include:
1. Getting repository information (size, description, stars, etc.)
2. Listing contents of repositories and directories
3. Reading file contents
4. Analyzing entire codebases (recommended for initial exploration)

When exploring a codebase:
1. First use analyze_codebase to get an overview and identify key files
2. Then use get_file_content only for specific files that are relevant
3. Don't try to read every file - focus on the most important ones

When answering questions about repositories:
1. Integrate repository URLs and file paths naturally into your responses
2. Provide clear context about what you're examining
3. Present information in a conversational way that flows naturally

Don't ask the user before taking an action, just do it. Always make sure you look at the repository with the provided tools before answering the user's question.
"""

# Initialize the model with proper configuration
model = OpenAIModel(
    model_name='gpt-4o-mini',
    api_key=os.getenv('OPENAI_API_KEY')
)

# Initialize the agent with proper result type handling
github_agent = Agent[GitHubDeps, Union[GitHubResult, Failed]](
    model=model,
    system_prompt=system_prompt,
    deps_type=GitHubDeps,
    result_type=Union[GitHubResult, Failed]  # type: ignore
)

# Register the tools with the agent
github_agent.tool(get_repo_info)
github_agent.tool(list_contents)
github_agent.tool(get_file_content)
github_agent.tool(analyze_codebase)