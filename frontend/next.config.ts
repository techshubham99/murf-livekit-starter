import type { NextConfig } from 'next';
import path from 'node:path';

const nextConfig: NextConfig = {
  eslint: {
    // These warnings come from upstream LiveKit/AI UI components, not our code.
    ignoreDuringBuilds: true,
  },
  turbopack: {
    // Keep Turbopack scoped to this pnpm project instead of a parent lockfile.
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
