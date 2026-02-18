/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow images from the backend domain
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.onrender.com',
      },
      {
        protocol: 'http',
        hostname: 'localhost',
      },
    ],
  },
  // NEXT_PUBLIC_* env vars are exposed automatically by Next.js
}

module.exports = nextConfig
