import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { insertMessageSchema } from "@shared/schema";
import { spawn } from "child_process";
import { z } from "zod";
import fetch from "node-fetch";
import path from "path";

const createMessageSchema = z.object({
  sessionId: z.string(),
  query: z.string(),
  requestId: z.string()
});

export function registerRoutes(app: Express): Server {
  // Start FastAPI server when Express starts
  const pythonProcess = spawn("python", ["github_agent_endpoint.py"], {
    env: {
      ...process.env,
      PATH: process.env.PATH
    },
    cwd: path.join(process.cwd(), "server")  // Set working directory to server folder
  });

  let serverStarted = false;
  let startupError: string | null = null;

  pythonProcess.stdout.on('data', (data) => {
    const output = data.toString();
    console.log(`FastAPI: ${output}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    const error = data.toString();
    console.error(`FastAPI Error: ${error}`);
    if (error.includes("ModuleNotFoundError")) {
      startupError = "Python dependencies not installed. Please run: pip install -r requirements.txt";
    } else {
      startupError = error;
    }
  });

  pythonProcess.on('error', (error) => {
    console.error('Failed to start FastAPI server:', error);
    startupError = error.message;
  });

  // Function to check if FastAPI server is ready
  async function checkFastAPIReady(): Promise<boolean> {
    try {
      const response = await fetch('http://127.0.0.1:8000/health');
      if (response.ok) {
        serverStarted = true;
        return true;
      }
    } catch (error) {
      // Server not ready yet
    }
    return false;
  }

  // Proxy middleware for FastAPI requests
  app.post('/api/github-agent', async (req, res) => {
    try {
      // Check if server is ready
      if (!serverStarted) {
        const isReady = await checkFastAPIReady();
        if (!isReady) {
          if (startupError) {
            throw new Error(`FastAPI server failed to start: ${startupError}`);
          }
          throw new Error("FastAPI server is not ready yet. Please wait a moment and try again.");
        }
      }

      const response = await fetch('http://127.0.0.1:8000/api/github-agent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(req.body)
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`FastAPI error: ${errorText}`);
      }

      const data = await response.json();
      res.json(data);
    } catch (error) {
      console.error('FastAPI proxy error:', error);
      res.status(500).json({ 
        error: "Failed to reach GitHub agent service",
        details: error instanceof Error ? error.message : String(error)
      });
    }
  });

  app.get("/api/messages/:sessionId", async (req, res) => {
    try {
      const messages = await storage.getMessagesBySession(req.params.sessionId);
      res.json(messages);
    } catch (error) {
      console.error('Error fetching messages:', error);
      res.status(500).json({ error: "Failed to fetch messages" });
    }
  });

  const httpServer = createServer(app);
  return httpServer;
}