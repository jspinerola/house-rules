// Telegram house group + iMessage personal DMs, against a fake spectrum stream and a fake brain.
import { after, before, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { AddressInfo } from "node:net";
import type { Server } from "node:http";
import type { ChatOut } from "../../contracts/types.js";
import {
  createPhotonGateway,
  OTHER_HOUSE,
  TELEGRAM_PRIVATE,
  TG,
  type MessageLike,
  type SpaceLike,
} from "../src/photon.js";
import { HOUSE_PREFIX } from "../src/shared.js";
import { startFakeBrain } from "./fake-brain.js";

const PHONES = { alex: "+15550000001", sam: "+15550000002", jordan: "+15550000003" } as const;
const TG_IDS = { alex: "111", sam: "222", jordan: "333" } as const;
type Rid = keyof typeof PHONES;
const RIDS = Object.keys(PHONES) as Rid[];
const HOUSE_CHAT = "-100500";

class FakeSpace implements SpaceLike {
  sent: string[] = [];
  constructor(readonly id: string, readonly type: "dm" | "group" = "dm") {}
  async send(text: string) {
    this.sent.push(text);
  }
  async responding<T>(fn: () => T | Promise<T>): Promise<T> {
    return fn();
  }
}

const ts = new Date("2026-11-28T12:00:00Z");
let n = 0;
const imsg = (from: string, text: string): MessageLike => ({
  id: `im-${++n}`,
  direction: "inbound",
  platform: "imessage",
  sender: { id: from },
  content: { type: "text", text } as MessageLike["content"],
  timestamp: ts,
});
const tmsg = (fromId: string, text: string, id = String(++n), handle?: string): MessageLike => ({
  id,
  direction: "inbound",
  platform: "telegram",
  sender: { id: fromId, ...(handle ? { handle } : {}) },
  content: { type: "text", text } as MessageLike["content"],
  timestamp: ts,
});

async function* stream(items: [FakeSpace, MessageLike][]) {
  for (const it of items) yield it;
}

let respond: (body: unknown) => ChatOut | Promise<ChatOut> = () => ({ replies: [] });
let brain: { server: Server; url: string; calls: unknown[] };

before(async () => {
  for (const r of RIDS) {
    process.env[`${r.toUpperCase()}_HANDLE`] = PHONES[r];
    process.env[`${r.toUpperCase()}_TELEGRAM`] = TG_IDS[r];
  }
  process.env.SAM_TELEGRAM = "@SamUser"; // usernames work too, case-insensitive
  brain = await startFakeBrain(0, (b) => respond(b));
  brain.url = `http://127.0.0.1:${(brain.server.address() as AddressInfo).port}`;
});
after(() => brain.server.close());
beforeEach(() => {
  brain.calls.length = 0;
  respond = () => ({ replies: [] });
});

function setup(items: [FakeSpace, MessageLike][]) {
  const spacesPath = join(mkdtempSync(join(tmpdir(), "gw-tg-")), "spaces.json");
  // Stored ids: iMessage raw, Telegram tg:-prefixed (mirrors run()'s getSpace).
  const known = new Map(items.map(([s, m]) => [m.platform === "telegram" ? TG + s.id : s.id, s]));
  const { gateway, serve } = createPhotonGateway<FakeSpace>(
    {
      messages: stream(items),
      spaceType: (s) => s.type,
      getSpace: async (id) => {
        const s = known.get(id);
        if (!s) throw new Error(`no space ${id}`);
        return s;
      },
      openDm: async () => {
        throw new Error("cannot open dm");
      },
    },
    { brainUrl: brain.url, spacesPath, fanout: false },
  );
  return { gateway, serve };
}

const imDms = () =>
  Object.fromEntries(RIDS.map((r) => [r, new FakeSpace(`any;-;${PHONES[r]}`)])) as Record<Rid, FakeSpace>;
const hiAll = (d: Record<Rid, FakeSpace>): [FakeSpace, MessageLike][] => RIDS.map((r) => [d[r], imsg(PHONES[r], "hi")]);

test("telegram group message reaches the brain as a group message from the roommate's phone", async () => {
  const group = new FakeSpace(HOUSE_CHAT);
  const { gateway, serve } = setup([[group, tmsg(TG_IDS.alex, "rent's due soon", "7")]]);
  await serve();
  assert.equal(gateway.spaces.group, TG + HOUSE_CHAT);
  const chatIn = brain.calls[0] as Record<string, string>;
  assert.deepEqual(
    [chatIn.chat_type, chatIn.sender_handle, chatIn.text, chatIn.message_id],
    ["group", PHONES.alex, "rent's due soon", `${TG}${HOUSE_CHAT}:7`],
  );
});

test("house replies go only to the telegram group; personal replies go to iMessage", async () => {
  const d = imDms();
  const group = new FakeSpace(HOUSE_CHAT);
  respond = (b) =>
    (b as { text: string }).text === "rent's due soon"
      ? {
          replies: [
            { target: { type: "group" }, text: "Rent is $800 each." },
            { target: { type: "dm", roommate_id: "jordan" }, text: "Xander fronts your share." },
          ],
        }
      : { replies: [] };
  const { serve } = setup([...hiAll(d), [group, tmsg(TG_IDS.alex, "rent's due soon")]]);
  await serve();
  assert.deepEqual(group.sent, ["Rent is $800 each."]);
  assert.deepEqual(d.jordan.sent, ["Xander fronts your share."]);
  for (const r of RIDS) assert.ok(!d[r].sent.some((t) => t.startsWith(HOUSE_PREFIX)), `${r} got a relay copy`);
});

test("POST /send group pushes land in the telegram group", async () => {
  const d = imDms();
  const group = new FakeSpace(HOUSE_CHAT);
  const { gateway, serve } = setup([...hiAll(d), [group, tmsg(TG_IDS.alex, "hi")]]);
  await serve();
  await gateway.deliver({ target: { type: "group" }, text: "Rent executed." });
  assert.deepEqual(group.sent, ["Rent executed."]);
  assert.equal(d.alex.sent.length, 0);
});

test("telegram username mapping works", async () => {
  const group = new FakeSpace(HOUSE_CHAT);
  const { serve } = setup([[group, tmsg("999", "yes", undefined, "samuser")]]);
  await serve();
  assert.equal((brain.calls[0] as Record<string, string>).sender_handle, PHONES.sam);
});

test("unknown telegram sender gets one setup hint and nothing reaches the brain", async () => {
  const group = new FakeSpace(HOUSE_CHAT);
  const { serve } = setup([
    [group, tmsg("424242", "hi", undefined, "stranger")],
    [group, tmsg("424242", "hello?", undefined, "stranger")],
  ]);
  await serve();
  assert.equal(brain.calls.length, 0);
  assert.equal(group.sent.length, 1);
  assert.match(group.sent[0], /@stranger.*424242/);
});

test("private telegram chat with the bot points to iMessage", async () => {
  const priv = new FakeSpace(TG_IDS.alex);
  const { gateway, serve } = setup([[priv, tmsg(TG_IDS.alex, "what's my balance?")]]);
  await serve();
  assert.equal(brain.calls.length, 0);
  assert.deepEqual(priv.sent, [TELEGRAM_PRIVATE]);
  assert.equal(gateway.spaces.group, null);
});

test("a second telegram group is ignored once the house group is registered", async () => {
  const house = new FakeSpace(HOUSE_CHAT);
  const other = new FakeSpace("-100999");
  const { gateway, serve } = setup([
    [house, tmsg(TG_IDS.alex, "hi")],
    [other, tmsg(TG_IDS.alex, "rent's due")],
  ]);
  await serve();
  assert.equal(brain.calls.length, 1);
  assert.equal(gateway.spaces.group, TG + HOUSE_CHAT);
  assert.deepEqual(other.sent, [OTHER_HOUSE]);
});

test("telegram message ids are namespaced per chat; true duplicates are dropped", async () => {
  const house = new FakeSpace(HOUSE_CHAT);
  const { serve } = setup([
    [house, tmsg(TG_IDS.alex, "hi", "5")],
    [house, tmsg(TG_IDS.alex, "hi", "5")], // redelivery
    [new FakeSpace(`any;-;${PHONES.alex}`), { ...imsg(PHONES.alex, "hi"), id: "5" }], // iMessage id "5" is distinct
  ]);
  await serve();
  assert.equal(brain.calls.length, 2);
});

test("with no telegram group yet, group replies still relay to iMessage DMs", async () => {
  const d = imDms();
  respond = (b) =>
    (b as { text: string }).text === "rent's due"
      ? { replies: [{ target: { type: "group" }, text: "Rent is due." }] }
      : { replies: [] };
  const { serve } = setup([...hiAll(d), [d.alex, imsg(PHONES.alex, "#house rent's due")]]);
  await serve();
  for (const r of RIDS) assert.deepEqual(d[r].sent, [`${HOUSE_PREFIX}Rent is due.`]);
});
