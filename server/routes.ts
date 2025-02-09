import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { insertMessageSchema } from "@shared/schema";
import { spawn } from "child_process";
import { z } from "zod";
import fetch from "node-fetch";

const createMessageSchema = z.object({
  sessionId: z.string(),
  query: z.string(),
  requestId: z.string()
});

export function registerRoutes(app: Express): Server {
  // Start FastAPI server when Express starts
  const pythonProcess = spawn("python3", ["server/github_agent_endpoint.py"], {
    env: {
      ...process.env,
      PATH: process.env.PATH
    }
  });

  let serverStarted = false;

  pythonProcess.stdout.on('data', (data) => {
    const output = data.toString();
    console.log(`FastAPI: ${output}`);
    if (output.includes("Application startup complete")) {
      serverStarted = true;
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`FastAPI Error: ${data}`);
  });

  pythonProcess.on('error', (error) => {
    console.error('Failed to start FastAPI server:', error);
  });

  // Proxy middleware for FastAPI requests
  app.post('/api/github-agent', async (req, res) => {
    try {
      if (!serverStarted) {
        throw new Error("FastAPI server is not ready yet");
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
      res.status(500).json({ error: "Failed to reach GitHub agent service" });
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