import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { nanoid } from "nanoid";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown/lib/ast-to-react";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import rehypeHighlight from "rehype-highlight";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { Send, Loader2, Github } from "lucide-react";

type Message = {
  id: number;
  type: 'human' | 'ai';
  content: string;
  data?: any;
  created_at: string;
};

export default function Chat() {
  const [sessionId] = useState(() => nanoid());
  const [input, setInput] = useState("");
  const { toast } = useToast();

  const { data: messages = [], isLoading } = useQuery<Message[]>({
    queryKey: [`/api/messages/${sessionId}`],
    refetchInterval: 1000
  });

  const mutation = useMutation({
    mutationFn: async (query: string) => {
      const res = await fetch("/api/github-agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId,
          query,
          requestId: nanoid()
        })
      });
      if (!res.ok) throw new Error("Failed to send message");
      return res.json();
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to send message"
      });
    }
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
        <div className="p-4 border-b flex items-center gap-2 bg-primary/5">
          <Github className="w-5 h-5" />
          <h1 className="text-xl font-semibold">GitHub Agent Chat</h1>
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
                      ? "bg-blue-600 text-white ml-12"
                      : "bg-gray-100 text-gray-900 mr-12"
                  }`}
                >
                  <div className={`prose max-w-none ${
                    msg.type === "human" 
                      ? "prose-invert prose-pre:bg-blue-700/50 prose-pre:border-blue-500 prose-code:bg-blue-700/30" 
                      : "prose-gray prose-pre:bg-gray-200 prose-pre:border-gray-300 prose-code:bg-gray-200"
                  } prose-pre:my-0 prose-pre:border`}>
                    <ReactMarkdown
                      rehypePlugins={[rehypeRaw, rehypeSanitize, rehypeHighlight]}
                      components={{
                        code: ({ className, children, ...props }: Components['code']) => {
                          const match = /language-(\w+)/.exec(className || '');
                          const isHuman = props.node?.position?.start.line === 1; // Hack to determine message type
                          return !props.inline && match ? (
                            <div className="relative">
                              <pre className={`${className} rounded p-4 ${
                                isHuman 
                                  ? "!bg-blue-700/50 border-blue-500" 
                                  : "!bg-gray-200 border-gray-300"
                              }`}>
                                <code className={`${className} ${isHuman ? "text-blue-50" : "text-gray-900"}`} {...props}>
                                  {children}
                                </code>
                              </pre>
                            </div>
                          ) : (
                            <code className={`${className} rounded px-1.5 py-0.5 ${
                              isHuman 
                                ? "bg-blue-700/30 text-blue-50" 
                                : "bg-gray-200 text-gray-900"
                            }`} {...props}>
                              {children}
                            </code>
                          );
                        },
                        p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
                        ul: ({ children }) => (
                          <ul className="list-disc list-inside mb-4 last:mb-0">{children}</ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal list-inside mb-4 last:mb-0">{children}</ol>
                        ),
                        li: ({ children }) => <li className="mb-1 last:mb-0">{children}</li>,
                        a: ({ href, children }) => (
                          <a 
                            href={href} 
                            className="underline hover:opacity-80" 
                            target="_blank" 
                            rel="noopener noreferrer"
                          >
                            {children}
                          </a>
                        ),
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>

        <form onSubmit={handleSubmit} className="p-4 border-t flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about a GitHub repository..."
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