"""GitHub API integration for the agent."""

from .api import GitHubAPI, GitHubAPIError
from .types import (
    GitHubRepoInfo, GitHubTreeEntry, GitHubTree,
    GitHubFile, GraphQLQuery, GraphQLResponse
)
from .tools import get_repo_info, list_contents, get_file_content, analyze_codebase

__all__ = [
    # API classes
    'GitHubAPI',
    'GitHubAPIError',
    
    # Type definitions
    'GitHubRepoInfo',
    'GitHubTreeEntry',
    'GitHubTree',
    'GitHubFile',
    'GraphQLQuery',
    'GraphQLResponse',
    
    # Tool functions
    'get_repo_info',
    'list_contents',
    'get_file_content',
    'analyze_codebase',
] 