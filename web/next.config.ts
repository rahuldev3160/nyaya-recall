import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    proxyTimeout: 120_000, // 2 min — covers quiz generation (30–60s) and batch analysis
  },
  async rewrites() {
    return [
      { source: "/api/backend/:path*", destination: "http://localhost:8000/:path*" }
    ];
  }
};

export default nextConfig;
