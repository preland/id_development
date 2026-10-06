import React from 'react';

export default function Link({ href, children, ...props }: { href?: string; children?: React.ReactNode }) {
  return React.createElement('a', { href, ...props }, children);
}
