import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { insertMessageSchema } from "@shared/schema";
import { spawn } from "child_process";
import { z } from "zod";

const createMessageSchema = z.object({
  sessionId: z.string(),
  query: z.string(),
  requestId: z.string()
});

export function registerRoutes(app: Express): Server {
  app.post("/api/chat", async (req, res) => {
    try {
      const body = createMessageSchema.parse(req.body);

      // Store user message
      await storage.createMessage({
        sessionId: body.sessionId,
        type: "human",
        content: body.query,
        data: null
      });

      // Call Python agent
      const pythonProcess = spawn("python3", ["server/github_agent_endpoint.py"], {
        env: {
          ...process.env,
          QUERY: body.query,
          SESSION_ID: body.sessionId,
          REQUEST_ID: body.requestId
        }
      });

      pythonProcess.on("close", async (code) => {
        if (code !== 0) {
          await storage.createMessage({
            sessionId: body.sessionId,
            type: "ai",
            content: "Sorry, I encountered an error processing your request.",
            data: { error: true }
          });
          res.status(500).json({ error: "Agent process failed" });
          return;
        }
        res.json({ success: true });
      });

    } catch (error) {
      res.status(400).json({ error: "Invalid request" });
    }
  });

  app.get("/api/messages/:sessionId", async (req, res) => {
    try {
      const messages = await storage.getMessagesBySession(req.params.sessionId);
      res.json(messages);
    } catch (error) {
      res.status(500).json({ error: "Failed to fetch messages" });
    }
  });

  const httpServer = createServer(app);
  return httpServer;
}
