import type { NextConfig } from "next";

// Runs server-side (Vercel's Node runtime / local `next dev`), never in the browser, so
// process.env is safe here without a NEXT_PUBLIC_ prefix. Was hardcoded to
// http://localhost:8000 -- set BACKEND_API_URL on Vercel to the hosted Cloud Run backend
// URL (see docs/migration/03_gcp_cloud_run_vercel_deploy.md); local dev is unaffected,
// still defaults to localhost:8000.
const BACKEND_API_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  experimental: {
    proxyTimeout: 120_000, // 2 min — covers quiz generation (30–60s) and batch analysis
  },
  async rewrites() {
    return [
      { source: "/api/backend/:path*", destination: `${BACKEND_API_URL}/:path*` }
    ];
  }
};

export default nextConfig;
