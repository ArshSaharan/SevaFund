import { AfterViewInit, Component, ElementRef, NgZone, OnDestroy, ViewChild, inject } from '@angular/core';
import { SmoothScrollService } from '../../services/smooth-scroll.service';
import { isBrowser } from '../../animation';

const RADIUS = 21;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/**
 * Appears once the reader is well into a page; its ring fills with reading progress.  Click to glide back up.
 * Updates the DOM directly (outside Angular) so scrolling never triggers change detection.
 */
@Component({
  selector: 'app-back-to-top',
  standalone: true,
  template: `
    <button #btn type="button" class="to-top" aria-label="Back to top" (click)="toTop()">
      <svg class="ring" viewBox="0 0 48 48" aria-hidden="true">
        <circle class="ring-track" cx="24" cy="24" [attr.r]="radius"></circle>
        <circle #ring class="ring-fill" cx="24" cy="24" [attr.r]="radius"
                [attr.stroke-dasharray]="circumference" [attr.stroke-dashoffset]="circumference"></circle>
      </svg>
      <svg class="chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polyline points="18 15 12 9 6 15"></polyline>
      </svg>
    </button>
  `,
  styles: [`
    .to-top {
      position: fixed;
      right: clamp(16px, 3vw, 32px);
      bottom: clamp(16px, 3vw, 32px);
      z-index: 900;
      width: 52px;
      height: 52px;
      display: grid;
      place-items: center;
      border: 1px solid var(--line);
      border-radius: 50%;
      background: var(--glass-bg);
      backdrop-filter: blur(14px) saturate(160%);
      -webkit-backdrop-filter: blur(14px) saturate(160%);
      color: var(--ink);
      box-shadow: var(--shadow-lg);
      cursor: pointer;
      opacity: 0;
      transform: translateY(16px) scale(0.85);
      pointer-events: none;
      transition: opacity 0.4s var(--ease-expo), transform 0.5s var(--ease-expo), box-shadow 0.3s ease;
    }
    .to-top.is-visible { opacity: 1; transform: none; pointer-events: auto; }
    .to-top:hover { box-shadow: var(--shadow-xl), 0 0 0 4px var(--accent-glow); }
    .to-top:hover .chevron { transform: translateY(-2px); }
    .ring { position: absolute; inset: 1px; width: calc(100% - 2px); height: calc(100% - 2px); transform: rotate(-90deg); }
    .ring-track { fill: none; stroke: var(--line); stroke-width: 2; }
    .ring-fill { fill: none; stroke: var(--accent); stroke-width: 2.5; stroke-linecap: round; }
    .chevron { position: relative; transition: transform 0.35s var(--ease-expo); }
    /* Clear the phone donate bar on fundraiser pages */
    :host-context(.has-bottom-bar) .to-top { transition: opacity 0.4s var(--ease-expo), transform 0.5s var(--ease-expo), bottom 0.5s var(--ease-expo); }
    @media (max-width: 992px) { :host-context(.has-bottom-bar) .to-top { bottom: 92px; } }
    @media print { .to-top { display: none; } }
  `],
})
export class BackToTopComponent implements AfterViewInit, OnDestroy {
  @ViewChild('btn', { static: true }) btn!: ElementRef<HTMLButtonElement>;
  @ViewChild('ring', { static: true }) ring!: ElementRef<SVGCircleElement>;
  readonly radius = RADIUS;
  readonly circumference = CIRCUMFERENCE;

  private smoothScroll = inject(SmoothScrollService);
  private zone = inject(NgZone);
  private frame = 0;
  private onScroll = () => {
    cancelAnimationFrame(this.frame);
    this.frame = requestAnimationFrame(() => this.update());
  };

  ngAfterViewInit(): void {
    if (!isBrowser) return;
    this.zone.runOutsideAngular(() => {
      window.addEventListener('scroll', this.onScroll, { passive: true });
      window.addEventListener('resize', this.onScroll, { passive: true });
      this.update();
    });
  }

  private update(): void {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const y = window.scrollY;
    const progress = max > 0 ? Math.min(1, y / max) : 0;
    this.ring.nativeElement.setAttribute('stroke-dashoffset', String(CIRCUMFERENCE * (1 - progress)));
    this.btn.nativeElement.classList.toggle('is-visible', y > window.innerHeight * 0.9);
  }

  toTop(): void {
    this.smoothScroll.scrollTo(0, { duration: 1.6 });
    document.getElementById('main')?.focus({ preventScroll: true });
  }

  ngOnDestroy(): void {
    if (!isBrowser) return;
    cancelAnimationFrame(this.frame);
    window.removeEventListener('scroll', this.onScroll);
    window.removeEventListener('resize', this.onScroll);
  }
}
