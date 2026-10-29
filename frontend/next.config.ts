import path from "node:path";
import type { NextConfig } from "next";
const config: NextConfig = {
  output: "standalone",
  turbopack: { root: path.resolve(process.cwd()) },
};
export default config;
