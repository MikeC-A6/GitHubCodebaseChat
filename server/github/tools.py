from typing import List, Optional
from pydantic_ai import RunContext
from .api import GitHubAPI, GitHubAPIError
from .types import GitHubTree, GitHubFile

def format_tree(tree: GitHubTree, show_repo_info: bool = True) -> str:
    """Format repository tree for display."""
    lines = []
    
    if show_repo_info:
        repo = tree.repository
        lines.extend([
            f"Repository: {repo.nameWithOwner}",
            f"Description: {repo.description or 'No description'}",
            f"Size: {repo.diskUsage / 1024:.1f}MB",
            f"Stars: {repo.stargazerCount}",
            f"Language: {repo.primaryLanguage['name'] if repo.primaryLanguage else 'None'}",
            f"Created: {repo.createdAt}",
            f"Last Updated: {repo.updatedAt}",
            "\nFiles and Directories:"
        ])
    
    # Group entries by directory
    by_dir = {}
    for entry in tree.entries:
        dir_path = '/'.join(entry.path.split('/')[:-1])
        if dir_path not in by_dir:
            by_dir[dir_path] = []
        by_dir[dir_path].append(entry)
    
    # Format entries by directory
    for dir_path in sorted(by_dir.keys()):
        if dir_path:
            lines.append(f"\n📂 {dir_path}/")
        entries = by_dir[dir_path]
        for entry in sorted(entries, key=lambda e: (e.type != "tree", e.name)):
            prefix = "📁" if entry.type == "tree" else "📄"
            name = entry.path.split('/')[-1]
            size = f"({entry.object['byteSize']} bytes)" if entry.type == "blob" and entry.object else ""
            indent = "  " if dir_path else ""
            lines.append(f"{indent}{prefix} {name} {size}")
        
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

async def analyze_codebase(ctx: RunContext, github_url: str) -> str:
    """Two-phase analysis of a codebase.
    1. Get directory structure
    2. Return formatted structure with key file suggestions
    """
    api = GitHubAPI(ctx.deps.client, ctx.deps.github_token)
    
    try:
        # Phase 1: Get directory structure
        tree = await api.get_tree(github_url)
        
        # Format basic info
        lines = [format_tree(tree, show_repo_info=True)]
        
        # Add suggestions for key files without fetching content
        key_files = []
        for entry in tree.entries:
            if entry.type != "blob":
                continue
                
            name = entry.name.lower()
            path = entry.path.lower()
            
            # Look for important files but don't fetch them yet
            if (name in ("readme.md", "requirements.txt", "setup.py", "pyproject.toml", "package.json", "go.mod") or
                name.endswith(("_agent.py", "_endpoint.py", "main.py", "index.ts", "index.js")) or
                "src/main" in path or
                name == "__init__.py"):
                key_files.append(entry.path)
        
        if key_files:
            lines.append("\nKey files found:")
            for file in sorted(key_files):
                lines.append(f"- {file}")
            lines.append("\nI can fetch the content of any of these files if needed.")
        
        return "\n".join(lines)
    except GitHubAPIError as e:
        return str(e) 