/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${API_URL}/api/:path*`,
      },
      {
        source: "/debug/:path*",
        destination: `${API_URL}/debug/:path*`,
      },
      {
        source: "/metrics",
        destination: `${API_URL}/metrics`,
      },
    ];
  },
};

module.exports = nextConfig;
