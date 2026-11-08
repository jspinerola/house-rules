// Sim mode: a terminal REPL that posts ChatIn to the brain, plus POST /send that prints.
//   @alex yes                      DM from alex
//   #group can we afford a couch?  group message from the last @ sender (default alex)
//   @sam #group hi                 group message from sam
//   /reset  /trigger rent_due  /advance 2026-12-16  /state  /quit
import { createServer, type IncomingMessage } from "node:http";
import { createInterface } from "node:readline";
import type { ChatIn, ChatOut, Reply, Target } from "../../contracts/types.js";

const BRAIN_URL = process.env.BRAIN_URL ?? "http://localhost:8000";
const PORT = Number(process.env.GATEWAY_PORT ?? 8787);
const ROOMMATES = ["alex", "sam", "jordan"];

const label = (t: Target) => (t.type === "group" ? "[group]" : `[dm:${t.roommate_id}]`);
const print = (r: Reply, prefix = "") => console.log(`${prefix}${label(r.target)} ${r.text}`);

async function brain(method: "GET" | "POST", path: string, body?: unknown): Promise<unknown> {
  const res = await fetch(`${BRAIN_URL}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status}: ${text}`);
  return JSON.parse(text);
}

async function readBody(req: IncomingMessage): Promise<string> {
  let data = "";
  for await (const chunk of req) data += chunk;
  return data;
}

function startServer() {
  const server = createServer(async (req, res) => {
    if (req.method === "POST" && req.url === "/send") {
      try {
        const reply = JSON.parse(await readBody(req)) as Reply;
        print(reply, "(push) ");
        res.writeHead(200, { "content-type": "application/json" }).end('{"ok":true}');
      } catch (e) {
        console.error("bad /send body:", e);
        res.writeHead(400).end('{"ok":false}');
      }
      return;
    }
    if (req.method === "GET" && req.url === "/health") {
      const body = { ok: true, mode: "sim", group_registered: true, dms_registered: ROOMMATES };
      res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(body));
      return;
    }
    res.writeHead(404).end();
  });
  server.listen(PORT, () => console.log(`gateway sim on :${PORT}, brain at ${BRAIN_URL}`));
  return server;
}

let msgCount = 0;
let lastSender = "alex";

async function handleLine(line: string): Promise<boolean> {
  const input = line.trim();
  if (!input) return true;
  if (input === "/quit") return false;
  if (input === "/reset") return console.log(await brain("POST", "/demo/reset")), true;
  if (input.startsWith("/trigger ")) {
    return console.log(await brain("POST", "/demo/trigger", { event: input.slice(9).trim() })), true;
  }
  if (input.startsWith("/advance ")) {
    return console.log(JSON.stringify(await brain("POST", "/demo/advance", { to: input.slice(9).trim() }))), true;
  }
  if (input === "/state") return console.log(JSON.stringify(await brain("GET", "/state"), null, 1)), true;

  const m = input.match(/^(?:@(\w+)\s+)?(#group\s+)?(.*)$/s);
  const who = m?.[1]?.toLowerCase();
  const isGroup = Boolean(m?.[2]) || !who;
  const text = (m?.[3] ?? "").trim();
  if (who && !ROOMMATES.includes(who)) {
    console.log(`unknown roommate @${who}; use ${ROOMMATES.map((r) => "@" + r).join(" ")}`);
    return true;
  }
  if (!who && !m?.[2]) {
    console.log("start with @alex, @sam, @jordan, #group, or a /command");
    return true;
  }
  const sender = who ?? lastSender;
  lastSender = sender;
  const chatIn: ChatIn = {
    chat_type: isGroup ? "group" : "dm",
    sender_handle: `sim:${sender}`,
    text,
    message_id: `sim-${Date.now()}-${++msgCount}`,
    ts: new Date().toISOString(),
  };
  const out = (await brain("POST", "/chat", chatIn)) as ChatOut;
  for (const r of out.replies) print(r);
  return true;
}

export async function run(): Promise<void> {
  const server = startServer();
  const rl = createInterface({ input: process.stdin, terminal: process.stdin.isTTY });
  if (process.stdin.isTTY) rl.setPrompt("> "), rl.prompt();
  for await (const line of rl) {
    let keepGoing = true;
    try {
      keepGoing = await handleLine(line);
    } catch (e) {
      console.error(`one sec, I'm restarting. (${(e as Error).message})`);
    }
    if (!keepGoing) break;
    if (process.stdin.isTTY) rl.prompt();
  }
  rl.close();
  server.close();
}
