import React from 'react';
import { createRoot } from 'react-dom/client';
import { ConfigProvider, useConfigContext } from 'idml/src/renderer/ConfigProvider';
import { ConfigRenderer } from 'idml/src/renderer/ConfigRenderer';

declare global {
  interface Window {
    __mount: (config: unknown, dark: boolean) => void;
    __mounted: boolean;
  }
}

function Mode({ dark }: { dark: boolean }): null {
  const { setDarkMode } = useConfigContext();
  React.useEffect(() => {
    setDarkMode(dark);
  }, [dark, setDarkMode]);
  return null;
}

window.__mounted = false;
window.__mount = (config, dark) => {
  const el = document.getElementById('app') as HTMLElement;
  const root = createRoot(el);
  root.render(
    <ConfigProvider config={config as never} methods={[]} components={[]}>
      <Mode dark={dark} />
      <ConfigRenderer page="/" />
    </ConfigProvider>
  );
  requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(() => { window.__mounted = true; })));
};
