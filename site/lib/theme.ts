export type Theme = 'light' | 'dark';

export function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light';

  const storedTheme = localStorage.getItem('theme');

  // Validate that the stored theme is a valid value
  if (storedTheme === 'light' || storedTheme === 'dark') {
    return storedTheme;
  }

  // Fall back to system preference
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  return prefersDark ? 'dark' : 'light';
}

export function applyTheme(theme: Theme): void {
  if (typeof window === 'undefined') return;

  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
}

export function initTheme(): void {
  if (typeof window === 'undefined') return;

  const theme = getInitialTheme();
  document.documentElement.setAttribute('data-theme', theme);
}

// Script content for blocking theme initialization
export const themeInitScript = `
  (function() {
    const storedTheme = localStorage.getItem('theme');
    const theme = (storedTheme === 'light' || storedTheme === 'dark')
      ? storedTheme
      : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
  })();
`;
