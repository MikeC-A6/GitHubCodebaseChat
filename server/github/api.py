import httpx
from typing import Optional, Tuple, Dict, Any, List
import re
from urllib.parse import urlparse

from .types import (
    GitHubRepoInfo, GitHubTree, GitHubFile,
    GraphQLQuery, GraphQLResponse
)

class GitHubAPIError(Exception):
    """Raised when GitHub API requests fail."""
    pass

class GitHubAPI:
    """Client for interacting with GitHub GraphQL API."""
    
    MAX_DEPTH = 3  # Maximum depth for recursive tree queries
    
    def __init__(self, client: httpx.AsyncClient, token: Optional[str] = None):
        self.client = client
        if not token:
            raise GitHubAPIError("GitHub token is required for GraphQL API")
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        
    def _parse_github_url(self, url: str) -> Tuple[str, str, str]:
        """Parse GitHub URL into owner, repo, and path components."""
        url = url.rstrip('/').replace('.git', '')
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        
        if len(path_parts) < 2:
            raise GitHubAPIError("Invalid GitHub URL format")
            
        owner = path_parts[0]
        repo = path_parts[1]
        
        # Handle tree/blob references in path
        remaining_parts = path_parts[2:]
        if remaining_parts and remaining_parts[0] in ('tree', 'blob'):
            remaining_parts = remaining_parts[2:]  # Skip 'tree/branch' or 'blob/branch'
        path = '/'.join(remaining_parts)
        
        return owner, repo, path

    def _build_recursive_tree_query(self, depth: int = 0) -> str:
        """Build a recursive GraphQL query for the tree structure."""
        if depth >= self.MAX_DEPTH:
            return """
                name
                path
                type
                object {
                    ... on Blob {
                        text
                        isBinary
                        byteSize
                    }
                }
            """
            
        return f"""
            name
            path
            type
            object {{
                ... on Blob {{
                    text
                    isBinary
                    byteSize
                }}
                ... on Tree {{
                    entries {{
                        {self._build_recursive_tree_query(depth + 1)}
                    }}
                }}
            }}
        """

    async def _graphql_request(self, query: GraphQLQuery) -> Dict[str, Any]:
        """Make a GraphQL request to GitHub API."""
        try:
            response = await self.client.post(
                'https://api.github.com/graphql',
                headers=self.headers,
                json=query.dict()
            )
            response.raise_for_status()
            result = GraphQLResponse(**response.json())
            
            if result.errors:
                raise GitHubAPIError(f"GraphQL errors: {result.errors}")
                
            if not result.data:
                raise GitHubAPIError("No data returned from GitHub API")
                
            return result.data
            
        except httpx.HTTPError as e:
            raise GitHubAPIError(f"GraphQL request failed: {str(e)}")

    def _flatten_tree_entries(self, entries: List[Dict[str, Any]], base_path: str = "") -> List[Dict[str, Any]]:
        """Flatten nested tree entries into a single list."""
        flattened = []
        for entry in entries:
            path = f"{base_path}/{entry['name']}" if base_path else entry['name']
            entry_copy = entry.copy()
            entry_copy['path'] = path
            
            if entry['type'] == 'tree' and entry.get('object', {}).get('entries'):
                sub_entries = entry['object']['entries']
                flattened.extend(self._flatten_tree_entries(sub_entries, path))
            
            flattened.append(entry_copy)
            
        return flattened
            
    async def get_repo_info(self, github_url: str) -> GitHubRepoInfo:
        """Get repository information using GraphQL."""
        owner, repo, _ = self._parse_github_url(github_url)
        
        query = GraphQLQuery(
            query="""
            query($owner: String!, $name: String!) {
                repository(owner: $owner, name: $name) {
                    name
                    nameWithOwner
                    description
                    diskUsage
                    stargazerCount
                    primaryLanguage {
                        name
                        color
                    }
                    createdAt
                    updatedAt
                    isPrivate
                    url
                }
            }
            """,
            variables={"owner": owner, "name": repo}
        )
        
        data = await self._graphql_request(query)
        if not data.get("repository"):
            raise GitHubAPIError(f"Repository {owner}/{repo} not found")
            
        return GitHubRepoInfo(**data["repository"])
            
    async def get_tree(self, github_url: str) -> GitHubTree:
        """Get repository tree using GraphQL."""
        owner, repo, path = self._parse_github_url(github_url)
        
        # Get both the default branch and recursive tree in a single query
        query = GraphQLQuery(
            query=f"""
            query($owner: String!, $name: String!) {{
                repository(owner: $owner, name: $name) {{
                    name
                    nameWithOwner
                    description
                    diskUsage
                    stargazerCount
                    primaryLanguage {{
                        name
                        color
                    }}
                    createdAt
                    updatedAt
                    isPrivate
                    url
                    defaultBranchRef {{
                        name
                        target {{
                            ... on Commit {{
                                tree {{
                                    entries {{
                                        {self._build_recursive_tree_query()}
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            """,
            variables={"owner": owner, "name": repo}
        )
        
        data = await self._graphql_request(query)
        repo_data = data.get("repository")
        if not repo_data:
            raise GitHubAPIError(f"Repository {owner}/{repo} not found")
            
        branch_ref = repo_data.get("defaultBranchRef")
        if not branch_ref:
            raise GitHubAPIError("Repository has no default branch")
            
        tree_data = branch_ref.get("target", {}).get("tree", {})
        entries = tree_data.get("entries", [])
        
        # Flatten the tree structure
        flattened_entries = self._flatten_tree_entries(entries)
        
        # Filter entries by path if specified
        if path:
            flattened_entries = [
                entry for entry in flattened_entries 
                if entry["path"].startswith(path)
            ]
            if not flattened_entries:
                raise GitHubAPIError(f"Path '{path}' not found in repository")
        
        return GitHubTree(
            entries=flattened_entries,
            repository=GitHubRepoInfo(**{
                k: v for k, v in repo_data.items() 
                if k != "defaultBranchRef"
            })
        )
            
    async def get_file_content(self, github_url: str) -> GitHubFile:
        """Get file content using GraphQL."""
        owner, repo, path = self._parse_github_url(github_url)
        if not path:
            raise GitHubAPIError("No file path specified")
            
        query = GraphQLQuery(
            query="""
            query($owner: String!, $name: String!, $path: String!) {
                repository(owner: $owner, name: $name) {
                    object(expression: $path) {
                        ... on Blob {
                            text
                            isBinary
                            byteSize
                        }
                    }
                }
            }
            """,
            variables={
                "owner": owner,
                "name": repo,
                "path": f"HEAD:{path}"
            }
        )
        
        data = await self._graphql_request(query)
        repo_data = data.get("repository")
        if not repo_data:
            raise GitHubAPIError(f"Repository {owner}/{repo} not found")
            
        blob_data = repo_data.get("object")
        if not blob_data:
            raise GitHubAPIError(f"File '{path}' not found")
            
        return GitHubFile(**blob_data) 