(() => {
  const key = 'manzanita-theme';
  const stored = localStorage.getItem(key);
  const theme = stored === 'light' || stored === 'dark'
    ? stored
    : (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.dataset.theme = theme;
})();
