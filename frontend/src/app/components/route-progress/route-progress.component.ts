import { Component, DestroyRef, NgZone, inject, signal } from '@angular/core';
import { NavigationCancel, NavigationEnd, NavigationError, NavigationStart, Router } from '@angular/router';

/**
 * A slim saffron bar across the top of the window while a page loads (pages are lazy-loaded chunks).
 * It eases towards ~85% while waiting, then completes and fades.
 */
@Component({
  selector: 'app-route-progress',
  standalone: true,
  template: `<div class="route-progress" [class.is-active]="active()" [class.is-done]="done()"
                  [style.transform]="'scaleX(' + progress() + ')'" aria-hidden="true"></div>`,
  styles: [`
    .route-progress {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 2.5px;
      z-index: 2000;
      transform-origin: 0 50%;
      transform: scaleX(0);
      opacity: 0;
      background: linear-gradient(90deg, var(--accent), #FFB547 60%, var(--leaf));
      box-shadow: 0 0 12px var(--accent-glow), 0 0 4px var(--accent-glow);
      transition: transform 0.6s var(--ease-expo), opacity 0.4s ease 0.15s;
      pointer-events: none;
    }
    .route-progress.is-active { opacity: 1; transition: transform 0.6s var(--ease-expo), opacity 0.1s ease; }
    .route-progress.is-done { opacity: 0; }
    @media (prefers-reduced-motion: reduce) { .route-progress { transition: opacity 0.2s ease; } }
  `],
})
export class RouteProgressComponent {
  active = signal(false);
  done = signal(false);
  progress = signal(0);

  private router = inject(Router);
  private zone = inject(NgZone);
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    const sub = this.router.events.subscribe((e) => {
      if (e instanceof NavigationStart) this.start();
      else if (e instanceof NavigationEnd || e instanceof NavigationCancel || e instanceof NavigationError) this.finish();
    });
    inject(DestroyRef).onDestroy(() => {
      sub.unsubscribe();
      this.stopTimer();
    });
  }

  private start(): void {
    this.stopTimer();
    this.done.set(false);
    this.active.set(true);
    this.progress.set(0.12);
    this.zone.runOutsideAngular(() => {
      this.timer = setInterval(() => {
        this.zone.run(() => this.progress.update((p) => p + (0.85 - p) * 0.18));
      }, 160);
    });
  }

  private finish(): void {
    if (!this.active()) return;
    this.stopTimer();
    this.progress.set(1);
    this.zone.runOutsideAngular(() =>
      setTimeout(() => this.zone.run(() => {
        this.done.set(true);
        this.active.set(false);
        setTimeout(() => this.zone.run(() => !this.active() && this.progress.set(0)), 450);
      }), 260),
    );
  }

  private stopTimer(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }
}
