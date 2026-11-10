import { Injectable, signal } from '@angular/core';

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'sevafund-theme';

/**
 * Light / dark theme. The initial theme is applied before first paint by the
 * inline script in index.html; this service keeps it in sync, persists the
 * user's explicit choice, and follows the OS setting until a choice is made.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly theme = signal<Theme>(this.readInitial());

  constructor() {
    if (typeof window === 'undefined') return;

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!this.hasStoredChoice()) this.apply(e.matches ? 'dark' : 'light');
    });
  }

  /**
   * Flip the theme. When the browser supports View Transitions (and motion is
   * allowed) the new theme is revealed as a circle growing from `origin`.
   */
  toggle(origin?: { x: number; y: number }): void {
    const next: Theme = this.theme() === 'dark' ? 'light' : 'dark';
    this.store(next);

    const doc = document as Document & { startViewTransition?: (cb: () => void) => { ready: Promise<void> } };
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!doc.startViewTransition || reduce) {
      this.apply(next);
      return;
    }

    const x = origin?.x ?? window.innerWidth - 40;
    const y = origin?.y ?? 36;
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    const root = document.documentElement;

    root.classList.add('theme-switching');
    const transition = doc.startViewTransition(() => this.apply(next));

    transition.ready
      .then(() =>
        root.animate(
          { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
          { duration: 650, easing: 'cubic-bezier(0.16, 1, 0.3, 1)', pseudoElement: '::view-transition-new(root)' },
        ).finished,
      )
      .catch(() => undefined)
      .finally(() => root.classList.remove('theme-switching'));
  }

  private apply(theme: Theme): void {
    document.documentElement.setAttribute('data-theme', theme);
    this.theme.set(theme);
  }

  private readInitial(): Theme {
    if (typeof document === 'undefined') return 'light';
    return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  private store(theme: Theme): void {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* storage unavailable (private mode) — theme still applies for this visit */
    }
  }

  private hasStoredChoice(): boolean {
    try {
      return !!localStorage.getItem(STORAGE_KEY);
    } catch {
      return false;
    }
  }
}
