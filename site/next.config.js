const isProd = process.env.NODE_ENV === 'production';
const configuredBasePath = process.env.NEXT_BASE_PATH || process.env.NEXT_PUBLIC_BASE_PATH;
let basePath = configuredBasePath || (isProd ? '/planthood' : undefined);

if (basePath) {
  const normalized = basePath.replace(/\/+$/, '');
  basePath = normalized === '' ? undefined : normalized;
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  ...(basePath
    ? (() => {
        const normalizedBasePath = basePath;
        return {
          basePath: normalizedBasePath,
          assetPrefix: `${normalizedBasePath}/`,
        };
      })()
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
