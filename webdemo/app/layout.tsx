import type { ReactNode } from 'react';
import './globals.css';

export const metadata = {
  title: 'id · todo — a website powered by id + idml',
  description:
    'A to-do app whose UI is declared in idml and whose entire state and logic ' +
    'is written in the id language, compiled to WebAssembly.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
