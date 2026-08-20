import type { ReactNode } from 'react';
import './globals.css';

export const metadata = {
  title: 'id · flappy — a game powered by id + idml',
  description:
    'A Flappy Bird clone whose entire state, physics and artwork come from ' +
    'the id language, and whose UI is declared in idml.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
