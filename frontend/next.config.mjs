const apiBase = process.env.NEXT_PUBLIC_API_URL?.trim() || '/api'
const proxyTarget = (process.env.SCHISM_API_PROXY_TARGET || 'http://localhost:8000').replace(/\/$/, '')
const useLocalApiProxy = process.env.NODE_ENV === 'development' && apiBase.startsWith('/')

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    if (!useLocalApiProxy) {
      return []
    }

    return [
      {
        source: '/api/:path*',
        destination: `${proxyTarget}/api/:path*`,
      },
    ]
  },
}

export default nextConfig
