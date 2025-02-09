from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime

class GitHubRepoInfo(BaseModel):
    """Information about a GitHub repository from GraphQL."""
    name: str
    nameWithOwner: str
    description: Optional[str] = None
    diskUsage: int
    stargazerCount: int
    primaryLanguage: Optional[Dict[str, str]] = None
    createdAt: datetime
    updatedAt: datetime
    isPrivate: bool
    url: str

class GitHubTreeEntry(BaseModel):
    """A file or directory in a GitHub repository from GraphQL."""
    name: str
    path: str
    type: Literal["blob", "tree"]
    object: Optional[Dict[str, Any]] = None  # For file content

class GitHubTree(BaseModel):
    """Repository tree response from GraphQL."""
    entries: List[GitHubTreeEntry]
    repository: GitHubRepoInfo

class GitHubFile(BaseModel):
    """File content from GraphQL."""
    text: Optional[str] = None
    isBinary: bool = False
    byteSize: int

class GraphQLQuery(BaseModel):
    """GraphQL query and variables."""
    query: str
    variables: Dict[str, Any]

class GraphQLResponse(BaseModel):
    """GraphQL response with data and errors."""
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[Dict[str, Any]]] = None 