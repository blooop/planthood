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
}

module.exports = nextConfig
