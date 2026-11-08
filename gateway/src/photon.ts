// Photon mode (C2–C6): spectrum-ts iMessage <-> brain POST /chat, plus POST /send and GET /health.
// Shared pool numbers are DM-only, so set GATEWAY_FANOUT=1 to relay group replies to all 3 DMs.
import { Spectrum } from "spectrum-ts";
import { imessage } from "spectrum-ts/providers/imessage";
import type { ChatIn, Reply } from "../../contracts/types.js";
import { Gateway, maskHandle, normalizeHandle, roommateFromHandle, type GatewayOpts } from "./shared.js";

export const NOT_IN_HOUSE = "Sorry, this number isn't in the house.";

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
  sender: { readonly id: string; readonly kind?: "agent" } | undefined;
  content: { type: string };
  timestamp: Date;
}

export type PhotonDeps<S extends SpaceLike> = {
  messages: AsyncIterable<readonly [S, MessageLike]>;
  spaceType(space: S): "dm" | "group";
  getSpace(id: string): Promise<S>;
  openDm(handle: string): Promise<S>;
};

const textOf = (m: MessageLike): string | null =>
  m.content.type === "text" && "text" in m.content && typeof m.content.text === "string"
    ? m.content.text
    : null;

export function createPhotonGateway<S extends SpaceLike>(deps: PhotonDeps<S>, opts: GatewayOpts = {}) {
  const cache = new Map<string, S>();
  const remember = (space: S) => (cache.set(space.id, space), space);

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

  async function handle(space: S, message: MessageLike): Promise<void> {
    if (message.direction === "outbound" || message.sender?.kind === "agent") return;
    const text = textOf(message);
    if (text === null) return; // reactions, typing, attachments
    if (!message.sender) return console.warn(`message ${message.id} has no sender; skipped`);
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

    const chatIn: ChatIn = {
      chat_type: chatType,
      sender_handle: handle,
      text,
      message_id: message.id,
      ts: message.timestamp.toISOString(),
    };
    await space.responding(() => gateway.handleInbound(chatIn));
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

  const app = await Spectrum({ projectId, projectSecret, providers: [imessage.config()] });
  const im = imessage(app);
  const { gateway, serve } = createPhotonGateway({
    messages: app.messages,
    spaceType: (space) => imessage(space).type,
    getSpace: (id) => im.space.get(id),
    openDm: (handle) => im.space.create(handle),
  });

  const port = Number(process.env.GATEWAY_PORT ?? 8787);
  const server = gateway.startServer(port);
  const h = gateway.health();
  console.log(
    `gateway photon on :${port}, brain at ${gateway.brainUrl}, fanout ${gateway.forceFanout ? "on" : "off"}, ` +
      `dms registered: ${h.dms_registered.join(", ") || "none"}`,
  );

  process.once("SIGINT", () => {
    server.close();
    void app.stop().finally(() => process.exit(0));
  });
  await serve();
  server.close();
}
