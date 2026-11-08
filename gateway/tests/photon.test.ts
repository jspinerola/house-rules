// Photon mode against a fake spectrum app (async iterator of [space, message]) and a fake brain.
import { after, before, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { AddressInfo } from "node:net";
import type { Server } from "node:http";
import type { ChatOut } from "../../contracts/types.js";
import { createPhotonGateway, NOT_IN_HOUSE, type MessageLike, type SpaceLike } from "../src/photon.js";
import { HOUSE_PREFIX, ONE_SEC } from "../src/shared.js";
import { startFakeBrain } from "./fake-brain.js";

const PHONES = { alex: "+15550000001", sam: "+15550000002", jordan: "+15550000003" } as const;
type Rid = keyof typeof PHONES;

class FakeSpace implements SpaceLike {
  sent: string[] = [];
  respondingCalls = 0;
  constructor(readonly id: string, readonly type: "dm" | "group" = "dm") {}
  async send(text: string) {
    this.sent.push(text);
  }
  async responding<T>(fn: () => T | Promise<T>): Promise<T> {
    this.respondingCalls++;
    return fn();
  }
}

let n = 0;
const msg = (from: string, text: string, extra: Partial<MessageLike> = {}): MessageLike => ({
  id: `m-${++n}`,
  direction: "inbound",
  sender: { id: from },
  content: { type: "text", text } as MessageLike["content"],
  timestamp: new Date("2026-11-28T12:00:00Z"),
  ...extra,
});

async function* stream(items: [FakeSpace, MessageLike][]) {
  for (const it of items) yield it;
}

// Brain behavior per test; calls are recorded by the fake brain.
let respond: (body: unknown) => ChatOut | Promise<ChatOut> = () => ({ replies: [] });
let brain: { server: Server; url: string; calls: unknown[] };

before(async () => {
  for (const [rid, phone] of Object.entries(PHONES)) process.env[`${rid.toUpperCase()}_HANDLE`] = phone;
  brain = await startFakeBrain(0, (b) => respond(b));
  brain.url = `http://127.0.0.1:${(brain.server.address() as AddressInfo).port}`;
});
after(() => brain.server.close());
beforeEach(() => {
  brain.calls.length = 0;
  respond = () => ({ replies: [] });
});

function setup(items: [FakeSpace, MessageLike][], opened: FakeSpace[] = []) {
  const spacesPath = join(mkdtempSync(join(tmpdir(), "gw-photon-")), "spaces.json");
  const known = new Map(items.map(([s]) => [s.id, s]));
  const openDmCalls: string[] = [];
  const { gateway, serve } = createPhotonGateway<FakeSpace>(
    {
      messages: stream(items),
      spaceType: (s) => s.type,
      getSpace: async (id) => {
        const s = known.get(id);
        if (!s) throw new Error(`no space ${id}`);
        return s;
      },
      openDm: async (handle) => {
        openDmCalls.push(handle);
        const s = opened.shift();
        if (!s) throw new Error("cannot open dm");
        return s;
      },
    },
    { brainUrl: brain.url, spacesPath, fanout: true },
  );
  return { gateway, serve, spacesPath, openDmCalls };
}

const dms = () => Object.fromEntries((Object.keys(PHONES) as Rid[]).map((r) => [r, new FakeSpace(`dm-${r}`)])) as Record<Rid, FakeSpace>;

test("own and agent messages are ignored", async () => {
  const s = new FakeSpace("dm-alex");
  const { gateway, serve } = setup([
    [s, msg(PHONES.alex, "hi", { direction: "outbound" })],
    [s, msg(PHONES.alex, "hi", { sender: { id: "+15559999999", kind: "agent" } })],
  ]);
  await serve();
  assert.equal(brain.calls.length, 0);
  assert.deepEqual(s.sent, []);
  assert.deepEqual(gateway.health().dms_registered, []);
});

test("unknown sender is told politely and nothing reaches the brain", async () => {
  const s = new FakeSpace("dm-stranger");
  const { gateway, serve } = setup([[s, msg("+15557770000", "hi")]]);
  await serve();
  assert.equal(brain.calls.length, 0);
  assert.deepEqual(s.sent, [NOT_IN_HOUSE]);
  assert.deepEqual(gateway.health().dms_registered, []);
});

test("first DM registers the space, persists it, and posts ChatIn under typing", async () => {
  const s = new FakeSpace("any;-;+15550000001");
  respond = () => ({ replies: [{ target: { type: "dm", roommate_id: "alex" }, text: "hey alex" }] });
  // Formatted number still maps to alex via E.164 normalization.
  const { gateway, serve, spacesPath } = setup([[s, msg("+1 (555) 000-0001", "hi")]]);
  await serve();
  assert.deepEqual(gateway.health().dms_registered, ["alex"]);
  assert.equal(JSON.parse(readFileSync(spacesPath, "utf8")).dms.alex, s.id);
  assert.equal(brain.calls.length, 1);
  const chatIn = brain.calls[0] as Record<string, string>;
  assert.equal(chatIn.chat_type, "dm");
  assert.equal(chatIn.sender_handle, PHONES.alex);
  assert.equal(chatIn.text, "hi");
  assert.equal(s.respondingCalls, 1);
  assert.deepEqual(s.sent, ["hey alex"]);
});

test("group reply fans out to all 3 DMs with the House prefix", async () => {
  const d = dms();
  respond = (b) =>
    (b as { text: string }).text === "rent's due"
      ? { replies: [{ target: { type: "group" }, text: "Rent is $800 each." }] }
      : { replies: [] };
  const { serve } = setup([
    [d.alex, msg(PHONES.alex, "hi")],
    [d.sam, msg(PHONES.sam, "hi")],
    [d.jordan, msg(PHONES.jordan, "hi")],
    [d.alex, msg(PHONES.alex, "rent's due")],
  ]);
  await serve();
  for (const r of Object.keys(PHONES) as Rid[]) {
    assert.deepEqual(d[r].sent, [`${HOUSE_PREFIX}Rent is $800 each.`], r);
  }
});

test("same message id is handled once", async () => {
  const s = new FakeSpace("dm-alex");
  const m = msg(PHONES.alex, "yes");
  const { serve } = setup([[s, m], [s, { ...m }]]);
  await serve();
  assert.equal(brain.calls.length, 1);
});

test("brain is retried once before the one-sec fallback", async () => {
  let fails = 1;
  respond = () => {
    if (fails-- > 0) throw new Error("down");
    return { replies: [{ target: { type: "dm", roommate_id: "sam" }, text: "ok" }] };
  };
  const s1 = new FakeSpace("dm-sam");
  await setup([[s1, msg(PHONES.sam, "hi")]]).serve();
  assert.equal(brain.calls.length, 2);
  assert.deepEqual(s1.sent, ["ok"]);

  brain.calls.length = 0;
  respond = () => {
    throw new Error("down");
  };
  const s2 = new FakeSpace("dm-sam");
  await setup([[s2, msg(PHONES.sam, "hi")]]).serve();
  assert.equal(brain.calls.length, 2);
  assert.deepEqual(s2.sent, [ONE_SEC]);
});

test("DM to an unregistered roommate opens a DM to their handle", async () => {
  const alex = new FakeSpace("dm-alex");
  const jordanNew = new FakeSpace("dm-jordan-new");
  respond = () => ({ replies: [{ target: { type: "dm", roommate_id: "jordan" }, text: "psst" }] });
  const { gateway, serve, openDmCalls } = setup([[alex, msg(PHONES.alex, "nudge jordan")]], [jordanNew]);
  await serve();
  assert.deepEqual(openDmCalls, [PHONES.jordan]);
  assert.deepEqual(jordanNew.sent, ["psst"]);
  assert.equal(gateway.spaces.dms.jordan, jordanNew.id);
});

test("POST /send pushes a group message to registered DMs", async () => {
  const d = dms();
  const { gateway, serve } = setup([
    [d.alex, msg(PHONES.alex, "hi")],
    [d.sam, msg(PHONES.sam, "hi")],
    [d.jordan, msg(PHONES.jordan, "hi")],
  ]);
  await serve();
  const server = gateway.startServer(0);
  await new Promise((r) => server.once("listening", r));
  const url = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  const res = await fetch(`${url}/send`, {
    method: "POST",
    body: JSON.stringify({ target: { type: "group" }, text: "Rent executed." }),
  });
  assert.equal(res.status, 200);
  const health = (await (await fetch(`${url}/health`)).json()) as { dms_registered: string[] };
  server.close();
  assert.deepEqual(health.dms_registered, ["alex", "jordan", "sam"]);
  for (const r of Object.keys(PHONES) as Rid[]) assert.deepEqual(d[r].sent, [`${HOUSE_PREFIX}Rent executed.`]);
});
