/** Shared gateway core: brain client, spaces, dedupe, deliver/fan-out, HTTP /send+/health. */
import { createServer, type IncomingMessage, type Server } from "node:http";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import type { ChatIn, ChatOut, Reply, Target } from "../../contracts/types.js";

export const ROOMMATES = ["alex", "sam", "jordan"] as const;
export type RoommateId = (typeof ROOMMATES)[number];
export const HOUSE_PREFIX = "🏠 House: ";
export const ONE_SEC = "one sec.";

export type SpacesState = {
  group: string | null;
  dms: Record<string, string>;
};

export type GatewayOpts = {
  brainUrl?: string;
  mode?: "sim" | "photon";
  spacesPath?: string;
  fanout?: boolean;
  deliver?: (reply: Reply) => void | Promise<void>;
  sendToSpace?: (spaceId: string, text: string) => void | Promise<void>;
};

const emptySpaces = (): SpacesState => ({ group: null, dms: {} });

export function loadSpaces(path: string): SpacesState {
  if (!existsSync(path)) return emptySpaces();
  try {
    const raw = JSON.parse(readFileSync(path, "utf8")) as SpacesState;
    return { group: raw.group ?? null, dms: raw.dms ?? {} };
  } catch {
    return emptySpaces();
  }
}

export function saveSpaces(path: string, spaces: SpacesState): void {
  const dir = dirname(path);
  if (dir && dir !== "." && !existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(path, JSON.stringify(spaces, null, 2));
}

export function label(t: Target): string {
  return t.type === "group" ? "[group]" : `[dm:${t.roommate_id}]`;
}

/** Phone -> E.164 (10 digits assume +1); email/other -> trimmed lowercase. */
export function normalizeHandle(handle: string): string {
  const h = handle.trim();
  if (h.includes("@") || h.includes(":")) return h.toLowerCase();
  const digits = h.replace(/\D/g, "");
  if (digits.length < 7) return h.toLowerCase();
  if (h.startsWith("+")) return `+${digits}`;
  return digits.length === 10 ? `+1${digits}` : `+${digits}`;
}

/** For logs: never print a full phone/email, only the last 4 characters. */
export function maskHandle(handle: string): string {
  return `***${handle.slice(-4)}`;
}

export function roommateFromHandle(handle: string): RoommateId | null {
  const lower = handle.toLowerCase();
  const norm = normalizeHandle(handle);
  for (const rid of ROOMMATES) {
    const env = process.env[`${rid.toUpperCase()}_HANDLE`];
    if (env && (env === handle || normalizeHandle(env) === norm)) return rid;
    if (lower === `sim:${rid}` || lower === rid || lower.endsWith(`:${rid}`)) return rid;
  }
  return null;
}

async function readBody(req: IncomingMessage): Promise<string> {
  let data = "";
  for await (const chunk of req) data += chunk;
  return data;
}

export class Gateway {
  brainUrl: string;
  mode: "sim" | "photon";
  spacesPath: string;
  forceFanout: boolean;
  spaces: SpacesState;
  seen = new Set<string>();
  deliveries: Reply[] = [];
  private deliverImpl: (reply: Reply) => Promise<void>;
  private sendToSpace?: (spaceId: string, text: string) => Promise<void>;

  constructor(opts: GatewayOpts = {}) {
    this.brainUrl = opts.brainUrl ?? process.env.BRAIN_URL ?? "http://localhost:8000";
    this.mode = opts.mode ?? ((process.env.GATEWAY_MODE as "sim" | "photon" | undefined) || "sim");
    this.spacesPath = opts.spacesPath ?? process.env.SPACES_PATH ?? "spaces.json";
    this.forceFanout = opts.fanout ?? process.env.GATEWAY_FANOUT === "1";
    this.sendToSpace = opts.sendToSpace
      ? async (id, text) => { await opts.sendToSpace!(id, text); }
      : undefined;
    this.spaces = loadSpaces(this.spacesPath);
    this.deliverImpl = async (reply) => {
      if (opts.deliver) await opts.deliver(reply);
      else console.log(`${label(reply.target)} ${reply.text}`);
      this.deliveries.push(reply);
    };
  }

  persist(): void {
    saveSpaces(this.spacesPath, this.spaces);
  }

  registerGroup(spaceId: string): void {
    this.spaces.group = spaceId;
    this.persist();
  }

  registerDm(roommateId: string, spaceId: string): void {
    this.spaces.dms[roommateId] = spaceId;
    this.persist();
  }

  health(): { ok: true; mode: string; group_registered: boolean; dms_registered: string[] } {
    return {
      ok: true,
      mode: this.mode,
      group_registered: Boolean(this.spaces.group),
      dms_registered: Object.keys(this.spaces.dms).sort(),
    };
  }

  shouldFanoutGroup(): boolean {
    return this.forceFanout || !this.spaces.group;
  }

  async deliver(reply: Reply): Promise<void> {
    if (reply.target.type === "group" && this.shouldFanoutGroup()) {
      // One phone failing (e.g. not allowed by the provider) must not block the others.
      const failed: string[] = [];
      for (const rid of ROOMMATES) {
        try {
          await this.deliverImpl({
            target: { type: "dm", roommate_id: rid },
            text: HOUSE_PREFIX + reply.text,
          });
        } catch (e) {
          failed.push(rid);
          console.error(`house relay to ${rid} failed: ${(e as Error).message}`);
        }
      }
      if (failed.length === ROOMMATES.length) throw new Error("house relay failed for every roommate");
      return;
    }
    if (this.sendToSpace) {
      const spaceId = reply.target.type === "group"
        ? this.spaces.group
        : this.spaces.dms[reply.target.roommate_id];
      if (spaceId) {
        await this.sendToSpace(spaceId, reply.text);
        this.deliveries.push(reply);
        return;
      }
    }
    await this.deliverImpl(reply);
  }

  async brainChat(chatIn: ChatIn): Promise<ChatOut> {
    const res = await fetch(`${this.brainUrl}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(chatIn),
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`${res.status}: ${text}`);
    return JSON.parse(text) as ChatOut;
  }

  async handleInbound(chatIn: ChatIn): Promise<Reply[]> {
    if (this.seen.has(chatIn.message_id)) return [];
    this.seen.add(chatIn.message_id);

    // Sim has no real spaces; photon registers real space ids before calling in.
    if (this.mode === "sim") {
      if (chatIn.chat_type === "group") {
        if (!this.spaces.group) this.registerGroup("sim-group");
      } else {
        const rid = roommateFromHandle(chatIn.sender_handle);
        if (rid && !this.spaces.dms[rid]) this.registerDm(rid, `sim-dm-${rid}`);
      }
    }

    let out: ChatOut | null = null;
    for (let attempt = 1; attempt <= 2 && !out; attempt++) {
      try {
        out = await this.brainChat(chatIn);
      } catch (e) {
        console.error(`brain /chat attempt ${attempt} failed: ${(e as Error).message}`);
      }
    }
    if (out) {
      for (const r of out.replies) await this.deliver(r);
      return out.replies;
    }
    const rid = roommateFromHandle(chatIn.sender_handle) ?? "alex";
    const fallback: Reply = {
      target: chatIn.chat_type === "group" ? { type: "group" } : { type: "dm", roommate_id: rid },
      text: ONE_SEC,
    };
    await this.deliver(fallback);
    return [fallback];
  }

  startServer(port: number, prefix = "(push) "): Server {
    const server = createServer(async (req, res) => {
      if (req.method === "POST" && req.url === "/send") {
        try {
          const reply = JSON.parse(await readBody(req)) as Reply;
          if (!this.sendToSpace && !process.env.GATEWAY_SILENT) {
            console.log(`${prefix}${label(reply.target)} ${reply.text}`);
          }
          await this.deliver(reply);
          res.writeHead(200, { "content-type": "application/json" }).end('{"ok":true}');
        } catch (e) {
          console.error("bad /send body:", e);
          res.writeHead(400).end('{"ok":false}');
        }
        return;
      }
      if (req.method === "GET" && req.url === "/health") {
        res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(this.health()));
        return;
      }
      res.writeHead(404).end();
    });
    server.listen(port);
    return server;
  }
}
