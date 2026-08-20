/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // idml ships as a built package, but it's a local file: dependency, so let
  // Next transpile it alongside app code (handles its 'use client' modules and
  // next/link import cleanly).
  transpilePackages: ['idml'],
};

export default nextConfig;
