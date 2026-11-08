// Gateway entry: GATEWAY_MODE=sim (terminal REPL) | photon (spectrum-ts iMessage).
const mode = process.env.GATEWAY_MODE ?? "sim";

if (mode === "sim") {
  const { run } = await import("./sim.js");
  await run();
} else if (mode === "photon") {
  const { run } = await import("./photon.js");
  await run();
} else {
  console.error(`Unknown GATEWAY_MODE=${mode}; expected sim or photon.`);
  process.exit(1);
}
