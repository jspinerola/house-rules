// Gateway entry: GATEWAY_MODE=sim (terminal REPL) | photon (lands in C2/C3).
const mode = process.env.GATEWAY_MODE ?? "sim";

if (mode === "sim") {
  const { run } = await import("./sim.js");
  await run();
} else if (mode === "photon") {
  console.error("GATEWAY_MODE=photon is not implemented yet (C2/C3). Use GATEWAY_MODE=sim.");
  process.exit(1);
} else {
  console.error(`Unknown GATEWAY_MODE=${mode}; expected sim or photon.`);
  process.exit(1);
}
