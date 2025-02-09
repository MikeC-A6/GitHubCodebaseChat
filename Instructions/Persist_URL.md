1. Explanation of the Changes
Goal
Add an “Enter Repo URL” input above the chat box.
Whenever a user sends a chat message, your frontend includes the repo URL in the same POST request to your github-agent endpoint.
The Python agent no longer needs to parse a GitHub URL from the chat text. Instead, it extracts it from the request body.
Summary of Steps
Add a new text input for the repo URL in your Chat.tsx page. Store it in React state.
Update the form submission so that every message includes both the user’s question and the repo URL.
Update your TypeScript request models so the server sees url or repoUrl as a separate field.
Update the Python AgentRequest model to have github_url: str | None, pass it to the agent, and remove old logic that tried to parse the URL from the user query text.
(Optional) If your agent still has old references to parsing a URL from the user’s text, remove or adapt them to use the newly provided github_url.
Why This Works
The new URL input ensures you can switch repositories on the fly (by changing the “Repo URL” field) without mixing it into the user’s chat text.
The Python side is simpler: it just takes the URL string from the request body and uses that in tools like get_repo_info(url), list_contents(url), or get_file_content(url).
2. Detailed Implementation Instructions
Below is a high-level checklist, then we show complete file diffs.

A. Frontend (React)
Add URL State
In Chat.tsx, create a new piece of React state:

ts
Copy
const [repoUrl, setRepoUrl] = useState("");
Add a Repo URL Input
Right above your chat’s message list (or wherever convenient), render a new input:

tsx
Copy
<div className="p-4 border-b flex items-center gap-2 bg-primary/5">
  <label className="font-semibold">Repo URL:</label>
  <Input
    value={repoUrl}
    onChange={(e) => setRepoUrl(e.target.value)}
    placeholder="https://github.com/owner/repo"
  />
</div>
This will appear above the chat messages.
Send the Repo URL in the POST Body
In the handleSubmit, when you do your mutation.mutateAsync(...), change it from:

ts
Copy
body: JSON.stringify({
  sessionId,
  query,
  requestId: nanoid()
})
to:

ts
Copy
body: JSON.stringify({
  sessionId,
  query,         // user’s typed chat
  requestId: nanoid(),
  repoUrl        // new field from state
})
This way, your Node server (and ultimately Python) will know which repository to act on.

B. Node/Express Layer
Parse the new repoUrl
In routes.ts or wherever you do:
ts
Copy
app.post('/api/github-agent', async (req, res) => {
  ...
  const body = req.body as {
    sessionId: string;
    query: string;
    requestId: string;
    repoUrl?: string; // add the new field
  };
  ...
});
Forward repoUrl to Python
In the same route, you do:
ts
Copy
const response = await fetch('http://127.0.0.1:8000/api/github-agent', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    session_id: body.sessionId,
    query: body.query,
    request_id: body.requestId,
    github_url: body.repoUrl, // or "repoUrl" -> "github_url"
  }),
});
This ensures the Python side sees it as github_url.
C. Python: AgentRequest & Endpoint
Add github_url to AgentRequest
In github_agent_endpoint.py (or wherever you have AgentRequest), add a field:

py
Copy
class AgentRequest(BaseModel):
    query: str
    sessionId: str = Field(alias="session_id")
    requestId: str = Field(alias="request_id")
    githubUrl: str | None = Field(None, alias="github_url")

    class Config:
        populate_by_name = True
This matches the body fields you’re sending from Node.

Use request.githubUrl
In @app.post("/api/github-agent") (the github_agent_endpoint function), you can do something like:

py
Copy
if request.githubUrl:
    # pass it into the agent’s run call, or append it to the user query
    # for example, you could do:
    final_user_prompt = f"Repository: {request.githubUrl}\n{request.query}"
else:
    final_user_prompt = request.query
result = await github_agent.run(
    final_user_prompt,
    deps=deps
)
Or, if your agent's system prompt or tool usage is designed to accept a separate URL argument, you might store request.githubUrl in the dependencies or pass it as a separate param.

Adjust Tools

If your tools like get_repo_info used to parse the URL from the user’s question, remove that code.
Instead, in the get_repo_info tool, the signature might become:
py
Copy
async def get_repo_info(ctx: RunContext[GitHubDeps], url: str) -> str:
    api = GitHubAPI(ctx.deps.client, ctx.deps.github_token)
    return await api.get_repo_info(url)
Then your agent’s LLM side can call get_repo_info(url=request.githubUrl) as needed, rather than scraping text out of the user’s prompt.
3. Complete Code Files
Below are full files that show all changes in context.

<details> <summary><strong>chat.tsx (client/src/pages/chat.tsx)</strong></summary>
tsx
Copy
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { nanoid } from "nanoid";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { Send, Loader2, Github } from "lucide-react";

type Message = {
  id: number;
  type: "human" | "ai";
  content: string;
  data?: any;
  created_at: string;
};

export default function Chat() {
  const [sessionId] = useState(() => nanoid());
  const [input, setInput] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const { toast } = useToast();

  // fetch messages
  const { data: messages = [], isLoading } = useQuery<Message[]>({
    queryKey: [`/api/messages/${sessionId}`],
    refetchInterval: 1000,
  });

  // mutation to send chat
  const mutation = useMutation({
    mutationFn: async (query: string) => {
      const res = await fetch("/api/github-agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId,       // same as before
          query,           // user question
          requestId: nanoid(),
          repoUrl,         // <-- new field
        }),
      });
      if (!res.ok) throw new Error("Failed to send message");
      return res.json();
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to send message",
      });
    },
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    try {
      await mutation.mutateAsync(input);
      setInput("");
    } catch (error) {
      console.error("Failed to send message:", error);
    }
  };

  return (
    <div className="container max-w-4xl mx-auto p-4">
      <Card className="h-[80vh] flex flex-col">
        {/* 
          NEW REPO URL SECTION 
          This sits at the top, letting the user change the repo URL. 
        */}
        <div className="p-4 border-b flex items-center gap-2 bg-primary/5">
          <Github className="w-5 h-5" />
          <h1 className="text-lg font-semibold">GitHub Agent Chat</h1>
        </div>

        {/* 
          Repo URL input
        */}
        <div className="p-4 border-b flex items-center gap-2">
          <label className="font-medium">Repo URL:</label>
          <Input
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
          />
        </div>

        <ScrollArea className="flex-1 p-4">
          {isLoading ? (
            <div className="flex justify-center p-4">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`p-4 rounded-lg ${
                    msg.type === "human"
                      ? "bg-primary text-primary-foreground ml-12"
                      : "bg-muted mr-12"
                  }`}
                >
                  {msg.content}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Chat form (unchanged except for the new state) */}
        <form onSubmit={handleSubmit} className="p-4 border-t flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about the repo or anything else..."
            disabled={mutation.isPending}
          />
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </form>
      </Card>
    </div>
  );
}
</details> <details> <summary><strong>routes.ts (server/routes.ts)</strong></summary>
ts
Copy
import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { spawn } from "child_process";
import { z } from "zod";
import fetch from "node-fetch";
import path from "path";

const createMessageSchema = z.object({
  sessionId: z.string(),
  query: z.string(),
  requestId: z.string(),
  repoUrl: z.string().optional(), // <--- new field
});

export function registerRoutes(app: Express): Server {
  // Start the Python process
  const pythonProcess = spawn("python", ["github_agent_endpoint.py"], {
    env: {
      ...process.env,
      PATH: process.env.PATH,
    },
    cwd: path.join(process.cwd(), "server"),
  });

  // just logging
  pythonProcess.stdout.on("data", (data) => {
    console.log(`FastAPI: ${data.toString()}`);
  });

  pythonProcess.stderr.on("data", (data) => {
    console.error(`FastAPI Error: ${data.toString()}`);
  });

  pythonProcess.on("error", (error) => {
    console.error("Failed to start FastAPI server:", error);
  });

  // naive check if started
  let serverStarted = false;
  let startupError: string | null = null;

  async function checkFastAPIReady(): Promise<boolean> {
    try {
      const response = await fetch("http://127.0.0.1:8000/health");
      if (response.ok) {
        serverStarted = true;
        return true;
      }
    } catch {
      // not ready
    }
    return false;
  }

  // Our main proxy route
  app.post("/api/github-agent", async (req, res) => {
    try {
      if (!serverStarted) {
        const isReady = await checkFastAPIReady();
        if (!isReady) {
          if (startupError) {
            throw new Error(`FastAPI server failed to start: ${startupError}`);
          }
          throw new Error("FastAPI server is not ready yet. Please wait...");
        }
      }
      // parse + validate
      const parseResult = createMessageSchema.safeParse(req.body);
      if (!parseResult.success) {
        return res
          .status(400)
          .json({ error: "Invalid request body", issues: parseResult.error });
      }

      // forward to python
      const { sessionId, query, requestId, repoUrl } = parseResult.data;
      const response = await fetch("http://127.0.0.1:8000/api/github-agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          query,
          request_id: requestId,
          github_url: repoUrl, // <--- pass this
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`FastAPI error: ${errorText}`);
      }

      const data = await response.json();
      res.json(data);
    } catch (error) {
      console.error("FastAPI proxy error:", error);
      res.status(500).json({
        error: "Failed to reach GitHub agent service",
        details: String(error),
      });
    }
  });

  // existing GET route for messages
  app.get("/api/messages/:sessionId", async (req, res) => {
    try {
      const messages = await storage.getMessagesBySession(req.params.sessionId);
      res.json(messages);
    } catch (error) {
      console.error("Error fetching messages:", error);
      res.status(500).json({ error: "Failed to fetch messages" });
    }
  });

  const httpServer = createServer(app);
  return httpServer;
}
</details> <details> <summary><strong>github_agent_endpoint.py (Python FastAPI)</strong></summary>
python
Copy
import asyncio
import os
import logging
import json
import asyncpg
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from github_agent import github_agent, GitHubDeps, GitHubResult, Failed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GitHub Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    query: str
    sessionId: str = Field(alias="session_id")
    requestId: str = Field(alias="request_id")
    # New field for the URL
    githubUrl: Optional[str] = Field(None, alias="github_url")

    class Config:
        populate_by_name = True

class AgentResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    repo_url: Optional[str] = None

@app.post("/api/github-agent")
async def github_agent_endpoint(request: AgentRequest):
    """
    Receives { query, sessionId, requestId, githubUrl } from Node,
    calls the pydantic-ai agent, and stores messages in DB.
    """
    try:
        logger.info(f"Received request: {request}")
        # store user's query
        await store_message(
            session_id=request.sessionId,
            message_type="human",
            content=request.query
        )

        # set up agent deps
        async with httpx.AsyncClient() as client:
            deps = GitHubDeps(
                client=client,
                github_token=os.getenv("GITHUB_TOKEN")
            )

            # If we want the agent to have "repo_url" inside the final prompt:
            # or we can literally pass it into the model’s run call
            final_prompt = request.query
            if request.githubUrl:
                final_prompt = f"[Repo: {request.githubUrl}]\n{request.query}"

            # run agent
            result = await github_agent.run(
                final_prompt,
                deps=deps
            )
            logger.debug(f"Agent result: {result}")

            if isinstance(result.data, Failed):
                error_msg = f"Agent failed: {result.data.reason}"
                logger.error(error_msg)
                await store_message(
                    session_id=request.sessionId,
                    message_type="ai",
                    content=error_msg,
                    data=json.dumps({"error": error_msg, "request_id": request.requestId})
                )
                return AgentResponse(success=False, error=error_msg, message=error_msg)

            # success
            response = result.data.content
            repo_url = result.data.repo_url  # might be None

            await store_message(
                session_id=request.sessionId,
                message_type="ai",
                content=response,
                data=json.dumps({
                    "request_id": request.requestId,
                    "repo_url": repo_url
                })
            )
            return AgentResponse(success=True, message=response, repo_url=repo_url)

    except Exception as e:
        logger.error(f"Error processing agent request: {str(e)}", exc_info=True)
        error_msg = "I encountered an error processing your request."
        await store_message(
            session_id=request.sessionId,
            message_type="ai",
            content=error_msg,
            data=json.dumps({"error": str(e), "request_id": request.requestId})
        )
        return AgentResponse(success=False, error=str(e), message=error_msg)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

async def store_message(session_id: str, message_type: str, content: str, data: Optional[str] = None):
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


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
</details>
4. Testing & Validation
Startup
Run npm run dev (or your normal dev command) which starts your Node server.
Ensure your Python environment is installed with pip install -r requirements.txt, so the github_agent_endpoint.py can run.
Open the web page at your Repl or local dev environment.
Enter a URL in the “Repo URL” box, e.g. https://github.com/pydantic/pydantic.
Type a question about it: “How many stars does it have?”
The Node server logs will show the POST /api/github-agent, sending JSON with repoUrl.
The Python logs will show that AgentRequest.githubUrl was populated.
If everything is correct, your old logic of “parsing the URL from the user’s message” is no longer needed; the agent simply sees repoUrl from the request.

5. Summary
Key difference: The user no longer has to type https://github.com/owner/repo in the same text as their question.
We have separated:
The “question” (or chat text) in query
The “repository URL” in githubUrl
This should fix the repeated issues of losing the correct URL or messing up the text parse.
If you keep your agent’s system prompt references to “Check github_url,” you can easily incorporate that into your function calls or dynamic prompts.

That’s it! You now have a clear, separate text input for the GitHub repository URL, which flows end-to-end (React → Node → Python agent).