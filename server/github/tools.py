from typing import List, Optional
from pydantic_ai import RunContext
from .api import GitHubAPI, GitHubAPIError
from .types import GitHubTree, GitHubFile

def format_tree(tree: GitHubTree) -> str:
    """Format repository tree for display."""
    repo = tree.repository
    lines = [
        f"Repository: {repo.nameWithOwner}",
        f"Description: {repo.description or 'No description'}",
        f"Size: {repo.diskUsage / 1024:.1f}MB",
        f"Stars: {repo.stargazerCount}",
        f"Language: {repo.primaryLanguage['name'] if repo.primaryLanguage else 'None'}",
        f"Created: {repo.createdAt}",
        f"Last Updated: {repo.updatedAt}",
        "\nContents:"
    ]
    
    for entry in tree.entries:
        prefix = "📁" if entry.type == "tree" else "📄"
        size = f"({entry.object['byteSize']} bytes)" if entry.type == "blob" and entry.object else ""
        lines.append(f"{prefix} {entry.path} {size}")
        
    return "\n".join(lines)

async def get_repo_info(ctx: RunContext, github_url: str) -> str:
    """Get repository information using GraphQL."""
    api = GitHubAPI(ctx.deps.client, ctx.deps.github_token)
    
    try:
        repo = await api.get_repo_info(github_url)
        return (
            f"Repository: {repo.nameWithOwner}\n"
            f"Description: {repo.description or 'No description'}\n"
            f"Size: {repo.diskUsage / 1024:.1f}MB\n"
            f"Stars: {repo.stargazerCount}\n"
            f"Language: {repo.primaryLanguage['name'] if repo.primaryLanguage else 'None'}\n"
            f"Created: {repo.createdAt}\n"
            f"Last Updated: {repo.updatedAt}"
        )
    except GitHubAPIError as e:
        return str(e)

async def list_contents(ctx: RunContext, github_url: str) -> str:
    """List repository contents using GraphQL."""
    api = GitHubAPI(ctx.deps.client, ctx.deps.github_token)
    
    try:
        tree = await api.get_tree(github_url)
        return format_tree(tree)
    except GitHubAPIError as e:
        return str(e)

async def get_file_content(ctx: RunContext, github_url: str) -> str:
    """Get file content using GraphQL."""
    api = GitHubAPI(ctx.deps.client, ctx.deps.github_token)
    
    try:
        file = await api.get_file_content(github_url)
        if file.isBinary:
            return f"Binary file ({file.byteSize} bytes)"
        return file.text or "Empty file"
    except GitHubAPIError as e:
        return str(e) 