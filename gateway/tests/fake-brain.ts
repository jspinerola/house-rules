/** Minimal fake brain: POST /chat → canned ChatOut (REQUIREMENTS M12). */
import { createServer, type Server } from "node:http";
import type { ChatOut } from "../../contracts/types.js";

export function startFakeBrain(
  port: number,
  respond: (body: unknown) => ChatOut | Promise<ChatOut>,
): Promise<{ server: Server; url: string; calls: unknown[] }> {
  const calls: unknown[] = [];
  const server = createServer(async (req, res) => {
    if (req.method === "POST" && req.url === "/chat") {
      let data = "";
      for await (const chunk of req) data += chunk;
      const body = JSON.parse(data || "{}");
      calls.push(body);
      try {
        const out = await respond(body);
        res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(out));
      } catch {
        res.writeHead(500).end("brain down");
      }
      return;
    }
    res.writeHead(404).end();
  });
  return new Promise((resolve) => {
    server.listen(port, "127.0.0.1", () => {
      resolve({ server, url: `http://127.0.0.1:${port}`, calls });
    });
  });
}
