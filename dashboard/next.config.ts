import { existsSync } from "node:fs";
import { resolve } from "node:path";
import type { NextConfig } from "next";

// Share the repo-root .env (BRAIN_URL) with the dashboard; loadEnvFile never overrides set vars.
const rootEnv = resolve(process.cwd(), "..", ".env");
if (existsSync(rootEnv)) process.loadEnvFile(rootEnv);

const config: NextConfig = {
  env: {
    NEXT_PUBLIC_BRAIN_URL:
      process.env.NEXT_PUBLIC_BRAIN_URL || process.env.BRAIN_URL || "http://localhost:8000",
  },
};

export default config;
