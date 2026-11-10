import { AfterViewInit, Component, ElementRef, Input, NgZone, OnDestroy, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { gsap, ScrollTrigger, isBrowser, prefersReducedMotion } from '../../animation/gsap';

/**
 * Endless ticker whose speed (and direction) follows scroll velocity —
 * scroll fast and it races; scroll up and it runs backwards.
 */
@Component({
  selector: 'app-marquee',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="marquee" [class.large]="size === 'lg'">
      <ul class="sr-only"><li *ngFor="let item of items">{{ item }}</li></ul>
      <div class="marquee-track" #track aria-hidden="true">
        <div class="marquee-group" *ngFor="let copy of [0, 1]">
          <ng-container *ngFor="let item of items">
            <span class="marquee-item">{{ item }}</span>
            <span class="marquee-sep">✦</span>
          </ng-container>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; }

    .marquee {
      overflow: hidden;
      border-block: 1px solid var(--line);
      padding: 18px 0;
    }

    .marquee-track {
      display: flex;
      width: max-content;
    }

    .marquee-group {
      display: flex;
      align-items: center;
      flex-shrink: 0;
    }

    .marquee-item {
      font-family: var(--font-display);
      font-size: clamp(1.25rem, 2.2vw, 1.75rem);
      letter-spacing: -0.02em;
      color: var(--ink);
      white-space: nowrap;
    }

    .large .marquee-item {
      font-size: clamp(2.5rem, 7vw, 6rem);
      font-style: italic;
      font-weight: 350;
      letter-spacing: -0.04em;
    }

    .marquee-sep {
      color: var(--accent);
      margin: 0 clamp(18px, 3vw, 40px);
      font-size: 0.9em;
    }

    .large .marquee-sep { font-size: 2rem; }
  `]
})
export class MarqueeComponent implements AfterViewInit, OnDestroy {
  @Input() items: string[] = [];
  @Input() size: 'md' | 'lg' = 'md';
  /** Seconds for one full loop at rest. */
  @Input() duration = 32;

  @ViewChild('track') trackRef!: ElementRef<HTMLElement>;

  private zone = inject(NgZone);
  private ctx?: gsap.Context;

  ngAfterViewInit(): void {
    if (!isBrowser || prefersReducedMotion()) return;

    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        const loop = gsap.to(this.trackRef.nativeElement, {
          xPercent: -50,
          ease: 'none',
          duration: this.duration,
          repeat: -1,
        });
        // Start deep into the loop so it has room to run backwards when scrolling up.
        loop.totalTime(this.duration * 1000);

        let direction = 1;
        ScrollTrigger.create({
          trigger: this.trackRef.nativeElement,
          start: 'top bottom',
          end: 'bottom top',
          onUpdate: (self) => {
            direction = self.direction;
            const boost = gsap.utils.clamp(1, 6, 1 + Math.abs(self.getVelocity()) / 300);
            gsap.to(loop, { timeScale: boost * direction, duration: 0.2, overwrite: true });
            gsap.to(loop, { timeScale: direction, duration: 1.2, delay: 0.2, ease: 'power2.out' });
          },
        });
      });
    });
  }

  ngOnDestroy(): void {
    this.ctx?.revert();
  }
}
