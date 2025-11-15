/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  // For GitHub Pages: set basePath to your repo name if not using custom domain
  // basePath: '/planthood-recipe-site',
  trailingSlash: true,
}

module.exports = nextConfig
