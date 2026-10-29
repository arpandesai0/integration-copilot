import { cpSync, existsSync } from "node:fs";

// Next's standalone bundle excludes static assets unless copied explicitly.
cpSync(".next/static", ".next/standalone/.next/static", { recursive: true });
if (existsSync("public")) {
  cpSync("public", ".next/standalone/public", { recursive: true });
}
