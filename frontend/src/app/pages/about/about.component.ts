import { AfterViewInit, Component, ElementRef, NgZone, OnDestroy, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MarqueeComponent } from '../../components/marquee/marquee.component';
import { NextChapterComponent } from '../../components/next-chapter/next-chapter.component';
import { MOTION, gsap, isBrowser, prefersReducedMotion } from '../../animation';

@Component({
  selector: 'app-about',
  standalone: true,
  imports: [CommonModule, RouterLink, MarqueeComponent, NextChapterComponent, ...MOTION],
  template: `
    <!-- Hero -->
    <section class="about-hero">
      <span class="seva-mark" [appParallax]="0.35" aria-hidden="true">सेवा</span>
      <div class="container hero-inner">
        <p class="eyebrow" appReveal>About SevaFund</p>
        <h1 class="display-xl about-title" appSplit="words" [splitOnLoad]="true" [splitDelay]="0.1">
          Seva means <em>selfless service.</em>
        </h1>
        <p class="lede" appReveal [revealDelay]="0.4">
          It is what you do for someone without expecting anything back. SevaFund exists to make
          that kind of giving safe — for strangers, at internet scale.
        </p>
      </div>
    </section>

    <!-- Mission, read along -->
    <section class="section mission">
      <div class="container">
        <p class="eyebrow" appReveal>Our mission</p>
        <p class="mission-text" appScrubText>
          Generosity shouldn’t require blind faith. So we built a place where every fundraiser is
          checked before it asks, every rupee comes with a receipt, and the money for a patient’s
          treatment goes to the hospital that treats them.
        </p>
      </div>
    </section>

    <!-- Principles: stacking cards -->
    <section class="principles" #principlesSection aria-labelledby="principles-title">
      <div class="container">
        <div class="principles-head">
          <p class="eyebrow">What we hold ourselves to</p>
          <h2 id="principles-title" class="display-md" appSplit>Four promises, <em>kept in code.</em></h2>
        </div>

        <ol class="stack">
          <li class="stack-card" *ngFor="let p of principles; let i = index" [attr.data-tone]="p.tone" [style.--i]="i">
            <span class="stack-num" aria-hidden="true">{{ (i + 1).toString().padStart(2, '0') }}</span>
            <div class="stack-body">
              <h3 class="stack-title">{{ p.title }}</h3>
              <p class="stack-text">{{ p.text }}</p>
              <a *ngIf="p.link" [routerLink]="p.link.path" class="text-link">{{ p.link.label }}</a>
            </div>
          </li>
        </ol>
      </div>
    </section>

    <!-- Causes -->
    <section class="causes" aria-label="Causes we support">
      <app-marquee [items]="causes" size="lg" [duration]="40"></app-marquee>
    </section>

    <app-next-chapter
      link="/campaigns"
      number="05"
      title="Find a cause"
      description="Fundraisers open for support right now."
    ></app-next-chapter>
  `,
  styles: [`
    :host { display: block; }

    /* Hero */
    .about-hero {
      position: relative;
      overflow: hidden;
      padding: clamp(72px, 12vw, 168px) 0 clamp(56px, 8vw, 112px);
    }

    .seva-mark {
      position: absolute;
      right: -2vw;
      top: 6%;
      z-index: -1;
      font-family: var(--font-devanagari);
      font-size: clamp(10rem, 34vw, 30rem);
      line-height: 1;
      color: var(--accent);
      opacity: 0.1;
      pointer-events: none;
      user-select: none;
    }

    .about-hero { isolation: isolate; }
    .about-title { margin: 20px 0 28px; max-width: 10ch; }

    /* Mission */
    .mission { background: var(--paper-2); }

    .mission-text {
      margin-top: 28px;
      max-width: 22ch;
      font-family: var(--font-display);
      font-size: clamp(2rem, 5vw, 4.25rem);
      line-height: 1.08;
      letter-spacing: -0.03em;
      color: var(--ink);
    }

    /* Principles */
    .principles { padding: var(--section-y) 0; }
    .principles-head { margin-bottom: clamp(40px, 6vw, 72px); }
    .principles-head h2 { margin-top: 18px; max-width: 12ch; }

    .stack { list-style: none; display: grid; gap: 28px; }

    .stack-card {
      position: sticky;
      top: calc(var(--navbar-height) + 24px + var(--i) * 22px);
      display: grid;
      grid-template-columns: auto 1fr;
      gap: clamp(24px, 5vw, 80px);
      align-items: start;
      min-height: min(50vh, 440px);
      padding: clamp(28px, 5vw, 64px);
      border-radius: var(--radius-2xl);
      border: 1px solid var(--line);
      background: var(--surface);
      box-shadow: var(--shadow-lg);
      transform-origin: center top;
      will-change: transform;
    }

    .stack-card[data-tone='accent'] {
      --ink: var(--on-accent);
      --ink-2: color-mix(in srgb, var(--on-accent) 80%, transparent);
      --accent-ink: var(--on-accent);
      background: var(--accent);
      border-color: var(--accent);
    }

    .stack-card[data-tone='night'] {
      --ink: var(--on-night);
      --ink-2: var(--on-night-2);
      --accent-ink: var(--accent);
      background: var(--night);
      border-color: var(--night);
    }

    .stack-card[data-tone='leaf'] {
      background: var(--leaf-soft);
      border-color: color-mix(in srgb, var(--leaf) 30%, transparent);
      --accent-ink: var(--leaf);
    }

    .stack-num {
      font-family: var(--font-display);
      font-size: clamp(4rem, 10vw, 9rem);
      font-style: italic;
      font-weight: 300;
      line-height: 0.85;
      color: var(--accent-ink);
    }

    .stack-title {
      font-family: var(--font-display);
      font-size: clamp(2rem, 4.5vw, 3.75rem);
      font-weight: 500;
      line-height: 1.02;
      letter-spacing: -0.03em;
      color: var(--ink);
      margin-bottom: 18px;
    }

    .stack-text {
      font-size: clamp(1.05rem, 1.5vw, 1.25rem);
      line-height: 1.6;
      color: var(--ink-2);
      max-width: 32em;
      margin-bottom: 20px;
    }

    .stack-card .text-link { color: var(--ink); }

    /* Causes */
    .causes { padding: clamp(40px, 6vw, 80px) 0; }

    @media (max-width: 640px) {
      .stack-card { grid-template-columns: 1fr; min-height: 0; gap: 12px; }
    }
  `]
})
export class AboutComponent implements AfterViewInit, OnDestroy {
  @ViewChild('principlesSection', { static: true }) principlesRef!: ElementRef<HTMLElement>;

  private zone = inject(NgZone);
  private ctx?: gsap.Context;

  readonly principles = [
    {
      title: 'No cut, ever.',
      text: 'SevaFund charges a 0% platform fee. We do not take a percentage of what you give.',
      tone: 'surface',
    },
    {
      title: 'Verify before you ask.',
      text: 'Every fundraiser is scored by our verifier on cost, specificity, red flags and documents — and borderline cases are reviewed by a person.',
      tone: 'accent',
      link: { path: '/trust', label: 'How the score works' },
    },
    {
      title: 'Money follows the patient.',
      text: 'For verified medical cases, funds are settled directly with the hospital’s registered account, not passed through an individual.',
      tone: 'night',
    },
    {
      title: 'A receipt for every rupee.',
      text: 'Instant payment confirmations, Section 80G certificates where eligible, and updates from organisers as treatment progresses.',
      tone: 'leaf',
      link: { path: '/campaigns', label: 'See it on a live fundraiser' },
    },
  ];

  readonly causes = ['Medical', 'Emergency', 'Education', 'Community', 'Memorial', 'Animals'];

  ngAfterViewInit(): void {
    if (!isBrowser || prefersReducedMotion()) return;

    const section = this.principlesRef.nativeElement;
    const cards = gsap.utils.toArray<HTMLElement>('.stack-card', section);

    // As each card slides over the previous one, the one underneath recedes.
    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        cards.slice(0, -1).forEach((card, i) => {
          gsap.to(card, {
            scale: 0.9 + i * 0.02,
            filter: 'brightness(0.92)',
            ease: 'none',
            scrollTrigger: {
              trigger: cards[i + 1],
              start: 'top bottom',
              end: 'top 30%',
              scrub: true,
            },
          });
        });
      }, section);
    });
  }

  ngOnDestroy(): void {
    this.ctx?.revert();
  }
}
