/** @type {import('next').NextConfig} */
const isStaticExport = process.env.NEXT_STATIC_EXPORT === '1';

const nextConfig = {
  ...(isStaticExport ? { output: 'export' } : {}),
  
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
