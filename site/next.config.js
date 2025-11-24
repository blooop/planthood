const isProd = process.env.NODE_ENV === 'production';
const configuredBasePath = process.env.NEXT_BASE_PATH || process.env.NEXT_PUBLIC_BASE_PATH;
const basePath = configuredBasePath || (isProd ? '/planthood' : undefined);

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  ...(basePath
    ? {
        basePath,
        assetPrefix: `${basePath}/`,
      }
    : {}),
  trailingSlash: true,
  // Skip validation during build to allow empty generateStaticParams
  typescript: {
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: false,
  },
};

module.exports = nextConfig;
