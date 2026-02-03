/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable static export for Tauri desktop app
  output: 'export',
  
  reactStrictMode: true,
  
  // Required for static export
  images: {
    unoptimized: true,
  },
  
  // Disable trailing slashes for cleaner URLs
  trailingSlash: false,
  
  webpack: (config) => {
    config.resolve.alias.canvas = false;
    return config;
  },
}

module.exports = nextConfig
