import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { nanoid } from "nanoid";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypePrism from "rehype-prism-plus";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { Send, Loader2, Github, Info, Copy, Check } from "lucide-react";

type Message = {
  id: number;
  type: 'human' | 'ai';
  content: string;
  data?: any;
  created_at: string;
};

function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
      onClick={copy}
    >
      {copied ? (
        <Check className="h-4 w-4" />
      ) : (
        <Copy className="h-4 w-4" />
      )}
    </Button>
  );
}

export default function Chat() {
  const [sessionId] = useState(() => nanoid());
  const [input, setInput] = useState("");
  const { toast } = useToast();
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const [showInstructions, setShowInstructions] = useState(true);

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

  // Auto-scroll effect
  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollElement = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollElement) {
        scrollElement.scrollTop = scrollElement.scrollHeight;
      }
    }
  }, [messages]);

  return (
    <div className="container mx-auto p-4 h-[calc(100vh-2rem)]">
      <Card className="h-full flex flex-col">
        <div className="p-4 border-b flex items-center justify-between bg-primary/5">
          <div className="flex items-center gap-2">
            <Github className="w-5 h-5" />
            <h1 className="text-xl font-semibold">GitHub Agent Chat</h1>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowInstructions(!showInstructions)}
            title={showInstructions ? "Hide Instructions" : "Show Instructions"}
          >
            <Info className="w-5 h-5" />
          </Button>
        </div>

        {showInstructions && (
          <div className="p-4 bg-blue-50 border-b">
            <h2 className="font-semibold mb-2">How to use this chat:</h2>
            <ul className="text-sm text-gray-700 space-y-1">
              <li>• Enter a GitHub repository URL (e.g., https://github.com/username/repo)</li>
              <li>• Ask questions about the repository's code and structure</li>
              <li>• Get help with repository analysis, code review, or bug fixes</li>
              <li>• Use natural language to describe what you want to know</li>
            </ul>
          </div>
        )}

        <ScrollArea className="flex-1 p-4" ref={scrollAreaRef}>
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
                      ? "bg-blue-600 text-white ml-12 md:ml-24"
                      : "bg-gray-100 text-gray-900 mr-12 md:mr-24"
                  }`}
                >
                  <div 
                    className={`prose max-w-none ${
                      msg.type === "human" 
                        ? "prose-invert prose-headings:text-white prose-a:text-blue-200" 
                        : "prose-gray prose-headings:text-gray-900 prose-a:text-blue-600"
                    } prose-headings:mb-2 prose-p:mb-4 prose-p:last:mb-0 prose-ul:my-2 prose-li:my-0
                    prose-a:no-underline prose-a:font-medium hover:prose-a:underline
                    prose-img:rounded-lg prose-img:shadow-md
                    prose-table:border prose-table:border-gray-300
                    prose-th:border prose-th:border-gray-300 prose-th:p-2
                    prose-td:border prose-td:border-gray-300 prose-td:p-2`}
                  >
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex, rehypePrism]}
                      components={{
                        code({ node, inline, className, children, ...props }) {
                          const match = /language-(\w+)/.exec(className || '');
                          const isHuman = msg.type === 'human';
                          
                          if (!inline && match) {
                            const language = match[1];
                            return (
                              <div className="relative group">
                                <SyntaxHighlighter
                                  style={isHuman ? oneDark : oneLight}
                                  language={language}
                                  PreTag="div"
                                  className="rounded-md !my-0"
                                  showLineNumbers={true}
                                  wrapLines={true}
                                  {...props}
                                >
                                  {String(children).replace(/\n$/, '')}
                                </SyntaxHighlighter>
                                <CopyButton code={String(children)} />
                              </div>
                            );
                          }
                          return (
                            <code
                              className={`${className} rounded px-1.5 py-0.5 ${
                                isHuman 
                                  ? "bg-blue-700/30 text-blue-50" 
                                  : "bg-gray-200 text-gray-900"
                              }`}
                              {...props}
                            >
                              {children}
                            </code>
                          );
                        },
                        // Only override specific components that need custom styling
                        a: ({ href, children }) => (
                          <a 
                            href={href} 
                            className="underline-offset-4 hover:opacity-80 break-words" 
                            target="_blank" 
                            rel="noopener noreferrer"
                          >
                            {children}
                          </a>
                        ),
                        table: ({ children }) => (
                          <div className="overflow-x-auto my-4">
                            <table className="min-w-full divide-y divide-gray-300">
                              {children}
                            </table>
                          </div>
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
            placeholder="Enter a GitHub URL or ask a question..."
            disabled={mutation.isPending}
            className="transition-all focus:ring-2 focus:ring-primary/20"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
          />
          <Button 
            type="submit" 
            disabled={mutation.isPending || !input.trim()}
            className="transition-transform active:scale-95 shrink-0"
          >
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