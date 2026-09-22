"use strict";
(() => {
  const key = 'veitch-theme';
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let preference = null;
  try {
    const saved = localStorage.getItem(key);
    if (saved === 'dark' || saved === 'light') preference = saved;
  } catch { /* The switch still works when browser storage is unavailable. */ }

  function apply() {
    const dark = (preference || (system.matches ? 'dark' : 'light')) === 'dark';
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    document.getElementById('theme-toggle')?.setAttribute('aria-pressed', String(dark));
  }
  // Apply before the stylesheet and page content load to avoid a light flash.
  apply();
  system.addEventListener('change', () => { if (!preference) apply(); });
  document.addEventListener('DOMContentLoaded', () => {
    apply();
    document.getElementById('theme-toggle').addEventListener('click', () => {
      preference = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(key, preference); } catch { /* Session-only choice. */ }
      apply();
    });
  });
})();
