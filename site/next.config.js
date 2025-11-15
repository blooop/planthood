/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  // For GitHub Pages: basePath set to repo name (blooop.github.io/planthood)
  // Comment out if using custom domain
  basePath: '/planthood',
  trailingSlash: true,
  // Skip validation during build to allow empty generateStaticParams
  typescript: {
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: false,
  },
}

module.exports = nextConfig
