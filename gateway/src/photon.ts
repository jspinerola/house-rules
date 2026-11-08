// Photon mode (C2–C6): spectrum-ts iMessage <-> brain POST /chat, plus POST /send and GET /health.
// Personal agents live in iMessage DMs. The house agent lives in a Telegram group when
// TELEGRAM_BOT_TOKEN is set; without one, GATEWAY_FANOUT=1 relays group replies to all 3 DMs.
import { Spectrum, type Space } from "spectrum-ts";
import { imessage } from "spectrum-ts/providers/imessage";
import { telegram } from "spectrum-ts/providers/telegram";
import type { ChatIn, Reply } from "../../contracts/types.js";
import {
  Gateway,
  maskHandle,
  normalizeHandle,
  ROOMMATES,
  roommateFromHandle,
  type GatewayOpts,
  type RoommateId,
} from "./shared.js";

export const NOT_IN_HOUSE = "Sorry, this number isn't in the house.";
export const TELEGRAM_PRIVATE =
  "I only work in the house group. Your private agent is in your iMessage DMs.";
export const OTHER_HOUSE = "This bot belongs to another house.";

/** Stored space ids for Telegram chats carry this prefix so sends pick the right provider. */
export const TG = "tg:";

/** The slice of a spectrum Space we use, so tests can pass fakes. */
export interface SpaceLike {
  readonly id: string;
  send(text: string): Promise<unknown>;
  responding<T>(fn: () => T | Promise<T>): Promise<T>;
}

/** The slice of a spectrum Message we use. */
export interface MessageLike {
  readonly id: string;
  direction: "inbound" | "outbound";
  platform?: string; // "imessage" | "telegram"; missing means iMessage
  sender: { readonly id: string; readonly kind?: "agent"; readonly handle?: string } | undefined;
  content: { type: string };
  timestamp: Date;
}

export type PhotonDeps<S extends SpaceLike> = {
  messages: AsyncIterable<readonly [S, MessageLike]>;
  spaceType(space: S): "dm" | "group";
  getSpace(id: string): Promise<S>;
  openDm(handle: string): Promise<S>;
};

// Shared pool has no group chat: a DM starting with #house / #group / @house speaks to the house.
const HOUSE_TAG = /^\s*(?:#house|#group|@house)\b[\s:,]*/i;

/** Map a Telegram sender to a roommate via ALEX_/SAM_/JORDAN_TELEGRAM (numeric id or @username). */
export function roommateFromTelegram(sender: { id: string; handle?: string }): RoommateId | null {
  const username = sender.handle?.toLowerCase();
  for (const rid of ROOMMATES) {
    const want = process.env[`${rid.toUpperCase()}_TELEGRAM`]?.trim().toLowerCase();
    if (!want) continue;
    if (want === sender.id || (username && want.replace(/^@/, "") === username)) return rid;
  }
  return null;
}

/** The handle the brain knows this roommate by (fixtures default to sim:<id>). */
const brainHandle = (rid: RoommateId): string =>
  process.env[`${rid.toUpperCase()}_HANDLE`]?.trim() || `sim:${rid}`;

const textOf = (m: MessageLike): string | null =>
  m.content.type === "text" && "text" in m.content && typeof m.content.text === "string"
    ? m.content.text
    : null;

export function createPhotonGateway<S extends SpaceLike>(deps: PhotonDeps<S>, opts: GatewayOpts = {}) {
  const cache = new Map<string, S>(); // keyed by stored space id (tg:-prefixed for Telegram)
  const remember = (space: S, key = space.id) => (cache.set(key, space), space);
  const hinted = new Set<string>(); // Telegram senders / groups already told why they're ignored

  const sendToSpace = async (spaceId: string, text: string) => {
    const space = cache.get(spaceId) ?? remember(await deps.getSpace(spaceId));
    await space.send(text);
  };

  // Gateway routes fan-out legs and DMs without a registered space here.
  const deliver = async (reply: Reply) => {
    if (reply.target.type === "group") {
      console.warn("group reply has no group space; set GATEWAY_FANOUT=1");
      return;
    }
    const rid = reply.target.roommate_id;
    let spaceId = gateway.spaces.dms[rid];
    if (!spaceId) {
      const handle = process.env[`${rid.toUpperCase()}_HANDLE`];
      if (!handle) {
        console.warn(`dm not registered: ${rid}, ask them to text hi`);
        return;
      }
      try {
        const space = remember(await deps.openDm(normalizeHandle(handle)));
        gateway.registerDm(rid, space.id);
        spaceId = space.id;
      } catch (e) {
        console.warn(`dm not registered: ${rid}, ask them to text hi (${(e as Error).message})`);
        return;
      }
    }
    await sendToSpace(spaceId, reply.text);
  };

  const gateway = new Gateway({
    mode: "photon",
    spacesPath: process.env.SPACES_PATH ?? "spaces.photon.json",
    ...opts,
    sendToSpace,
    deliver,
  });

  // Typing is best effort: some recipients (SMS / no iMessage) reject it.
  async function respond(space: S, rid: RoommateId, chatIn: ChatIn): Promise<void> {
    let started = false;
    const work = async () => {
      started = true;
      await gateway.handleInbound(chatIn);
    };
    try {
      await space.responding(work);
    } catch (e) {
      if (started) throw e;
      console.warn(`typing unavailable for ${rid} (${(e as Error).message}); replying without it`);
      await work();
    }
  }

  // Telegram: the house group only. Private chats with the bot point people to iMessage.
  async function handleTelegram(space: S, message: MessageLike, text: string): Promise<void> {
    const sender = message.sender!;
    const key = `${TG}${space.id}`;
    const messageId = `${key}:${message.id}`; // Telegram message ids are only unique per chat
    if (gateway.seen.has(messageId)) return;
    remember(space, key);

    const once = async (hintKey: string, reply: string) => {
      gateway.seen.add(messageId);
      if (hinted.has(hintKey)) return;
      hinted.add(hintKey);
      await space.send(reply);
    };
    if (!space.id.startsWith("-")) return once(`private:${space.id}`, TELEGRAM_PRIVATE);
    if (gateway.spaces.group && gateway.spaces.group !== key) {
      console.warn(`telegram group ${space.id} is not the house group; ignored`);
      return once(`group:${space.id}`, OTHER_HOUSE);
    }
    const rid = roommateFromTelegram(sender);
    if (!rid) {
      const who = sender.handle ? `@${sender.handle}` : "you";
      console.warn(`unknown telegram sender ${sender.id}; set ALEX_/SAM_/JORDAN_TELEGRAM`);
      return once(`sender:${sender.id}`,
        `I don't know ${who} yet (Telegram id ${sender.id}). Add it as ALEX_TELEGRAM, SAM_TELEGRAM or JORDAN_TELEGRAM.`);
    }
    if (!gateway.spaces.group) {
      gateway.registerGroup(key);
      console.log(`registered house group: telegram ${space.id}`);
    }
    await respond(space, rid, {
      chat_type: "group",
      sender_handle: brainHandle(rid),
      text: text.replace(HOUSE_TAG, ""),
      message_id: messageId,
      ts: message.timestamp.toISOString(),
    });
  }

  async function handle(space: S, message: MessageLike): Promise<void> {
    if (message.direction === "outbound" || message.sender?.kind === "agent") return;
    const text = textOf(message);
    if (text === null) return; // reactions, typing, attachments
    if (!message.sender) return console.warn(`message ${message.id} has no sender; skipped`);
    if (message.platform === "telegram") return handleTelegram(space, message, text);
    if (message.platform && message.platform !== "imessage") return;
    if (gateway.seen.has(message.id)) return;

    remember(space);
    const handle = normalizeHandle(message.sender.id);
    const rid = roommateFromHandle(handle);
    if (!rid) {
      gateway.seen.add(message.id);
      console.warn(`unknown sender ${maskHandle(handle)}; not forwarded`);
      await space.send(NOT_IN_HOUSE);
      return;
    }

    const chatType = deps.spaceType(space);
    if (chatType === "group") {
      if (!gateway.spaces.group) gateway.registerGroup(space.id);
    } else if (gateway.spaces.dms[rid] !== space.id) {
      gateway.registerDm(rid, space.id);
      console.log(`registered dm: ${rid} (${maskHandle(handle)})`);
    }

    const toHouse = chatType === "dm" && HOUSE_TAG.test(text);
    const chatIn: ChatIn = {
      chat_type: toHouse ? "group" : chatType,
      sender_handle: handle,
      text: toHouse ? text.replace(HOUSE_TAG, "") : text,
      message_id: message.id,
      ts: message.timestamp.toISOString(),
    };
    await respond(space, rid, chatIn);
  }

  async function serve(): Promise<void> {
    for await (const [space, message] of deps.messages) {
      try {
        await handle(space, message);
      } catch (e) {
        console.error(`failed to handle message ${message.id}: ${(e as Error).message}`);
      }
    }
  }

  return { gateway, serve };
}

export async function run(): Promise<void> {
  const projectId = process.env.SPECTRUM_PROJECT_ID;
  const projectSecret = process.env.SPECTRUM_PROJECT_SECRET || process.env.SPECTRUM_SECRET;
  const missing = [
    !projectId && "SPECTRUM_PROJECT_ID",
    !projectSecret && "SPECTRUM_PROJECT_SECRET",
  ].filter(Boolean);
  if (!projectId || !projectSecret) {
    throw new Error(`GATEWAY_MODE=photon needs ${missing.join(" and ")} (set in the repo-root .env)`);
  }

  const { deps, stop, providers } = await connect(projectId, projectSecret, process.env.TELEGRAM_BOT_TOKEN?.trim());
  const { gateway, serve } = createPhotonGateway(deps);

  const port = Number(process.env.GATEWAY_PORT ?? 8787);
  const server = gateway.startServer(port);
  const h = gateway.health();
  console.log(
    `gateway photon on :${port}, brain at ${gateway.brainUrl}, fanout ${gateway.forceFanout ? "on" : "off"}, ` +
      `dms registered: ${h.dms_registered.join(", ") || "none"}, providers: ${providers.join(", ")}, ` +
      `house group: ${gateway.spaces.group?.startsWith(TG) ? "telegram" : h.group_registered ? "imessage" : "none"}`,
  );

  process.once("SIGINT", () => {
    server.close();
    void stop().finally(() => process.exit(0));
  });
  await serve();
  server.close();
}

type Connection = { deps: PhotonDeps<Space>; stop(): Promise<void>; providers: string[] };

/** Start Spectrum with iMessage, plus Telegram when a bot token is set. Never logs secrets. */
async function connect(projectId: string, projectSecret: string, botToken?: string): Promise<Connection> {
  if (botToken) {
    const app = await Spectrum({
      projectId,
      projectSecret,
      providers: [imessage.config(), telegram.config({ botToken })],
    });
    const im = imessage(app);
    const tg = telegram(app);
    return {
      deps: {
        messages: app.messages,
        spaceType: (space) => imessage(space).type,
        getSpace: (id) => (id.startsWith(TG) ? tg.space.get(id.slice(TG.length)) : im.space.get(id)),
        openDm: (handle) => im.space.create(handle),
      },
      stop: () => app.stop(),
      providers: ["imessage", "telegram"],
    };
  }
  const app = await Spectrum({ projectId, projectSecret, providers: [imessage.config()] });
  const im = imessage(app);
  return {
    deps: {
      messages: app.messages,
      spaceType: (space) => imessage(space).type,
      getSpace: (id) => im.space.get(id),
      openDm: (handle) => im.space.create(handle),
    },
    stop: () => app.stop(),
    providers: ["imessage"],
  };
}
