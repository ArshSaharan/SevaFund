import { AfterViewInit, Component, ElementRef, NgZone, OnDestroy, ViewChild, inject } from '@angular/core';
import { NgIf } from '@angular/common';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map } from 'rxjs';
import { RevealDirective, SplitTextDirective, gsap, isBrowser, prefersReducedMotion } from '../../animation';

@Component({
  selector: 'app-footer',
  standalone: true,
  imports: [NgIf, RouterLink, RevealDirective, SplitTextDirective],
  template: `
    <footer class="footer">
      <!-- Closing statement (hidden where the visitor is already acting) -->
      <div class="container footer-cta" *ngIf="showCta()">
        <p class="eyebrow">The last chapter is yours</p>
        <h2 class="display-lg cta-title" appSplit>
          Give with your <em>eyes&nbsp;open.</em>
        </h2>
        <div class="cta-row" appReveal [revealDelay]="0.2">
          <a routerLink="/campaigns" class="btn btn-primary btn-lg">
            Explore verified causes
            <svg class="arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
              <line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </a>
          <a routerLink="/create" class="btn btn-ghost-night btn-lg">Start a fundraiser</a>
        </div>
      </div>

      <!-- Directory -->
      <div class="container footer-grid" appReveal [revealStagger]="0.08">
        <div class="footer-col brand-col">
          <p class="brand-desc">
            AI-audited medical and emergency crowdfunding for India — zero platform fee,
            receipts for every rupee, and direct hospital settlement.
          </p>
          <span class="national-tag">Built for Indian healthcare access</span>
        </div>

        <nav class="footer-col" aria-label="Causes">
          <h3 class="col-title">Causes</h3>
          <ul class="col-links">
            <li><a routerLink="/campaigns" [queryParams]="{ category: 'MEDICAL' }">Medical treatment</a></li>
            <li><a routerLink="/campaigns" [queryParams]="{ category: 'EMERGENCY' }">Accident &amp; ICU emergency</a></li>
            <li><a routerLink="/campaigns" [queryParams]="{ category: 'EDUCATION' }">Education grants</a></li>
            <li><a routerLink="/campaigns" [queryParams]="{ category: 'COMMUNITY' }">Community</a></li>
            <li><a routerLink="/campaigns" [queryParams]="{ category: 'ANIMALS' }">Animal rescue &amp; care</a></li>
          </ul>
        </nav>

        <nav class="footer-col" aria-label="Platform">
          <h3 class="col-title">Platform</h3>
          <ul class="col-links">
            <li><a routerLink="/how-it-works">How it works</a></li>
            <li><a routerLink="/trust">Trust &amp; safety</a></li>
            <li><a routerLink="/about">About SevaFund</a></li>
            <li><a routerLink="/create">Start a fundraiser</a></li>
            <li><a routerLink="/admin">Moderator portal</a></li>
          </ul>
        </nav>

        <div class="footer-col">
          <h3 class="col-title">Pay with</h3>
          <div class="payment-badges-row">
            <span class="pay-chip">UPI</span>
            <span class="pay-chip">GPay</span>
            <span class="pay-chip">PhonePe</span>
            <span class="pay-chip">Paytm</span>
            <span class="pay-chip">RuPay</span>
            <span class="pay-chip">Netbanking</span>
          </div>
          <p class="payments-desc">Section 80G receipts issued instantly for eligible fundraisers.</p>
        </div>
      </div>

      <!-- Bottom bar -->
      <div class="container footer-bottom">
        <p>© 2026 SevaFund India Technologies Private Limited</p>
        <p class="legal">Terms · Privacy · AML / KYC · 80G compliance</p>
      </div>

      <!-- Oversized wordmark -->
      <div class="wordmark-wrap" aria-hidden="true">
        <span class="wordmark" #wordmark>SevaFund</span>
      </div>
    </footer>
  `,
  styles: [`
    .footer {
      position: relative;
      background: var(--night);
      color: var(--on-night-2);
      overflow: hidden;
      --ink: var(--on-night);
    }

    /* Hairlines inset to the content edges (not the container's padding box) */
    .footer-cta,
    .footer-bottom {
      background: linear-gradient(var(--night-line), var(--night-line)) no-repeat;
      background-size: calc(100% - 2 * var(--gutter)) 1px;
    }

    .footer-cta {
      padding-top: clamp(88px, 12vw, 160px);
      padding-bottom: clamp(56px, 8vw, 96px);
      background-position: center bottom;
    }

    .footer-cta .eyebrow { color: var(--accent); }

    .cta-title {
      color: var(--on-night);
      margin: 20px 0 36px;
      max-width: 12ch;
    }

    .cta-title em { color: var(--accent); }

    .cta-row {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }

    .btn-ghost-night {
      color: var(--on-night);
      border-color: var(--night-line);
      background: transparent;
    }

    .btn-ghost-night:hover {
      border-color: var(--on-night-2);
      background: rgba(255, 244, 230, 0.05);
    }

    .footer-grid {
      display: grid;
      grid-template-columns: 1.4fr 1fr 1fr 1.1fr;
      gap: 40px;
      padding-top: 64px;
      padding-bottom: 56px;
    }

    .brand-desc {
      font-size: 15px;
      line-height: 1.65;
      color: var(--on-night-2);
      max-width: 34ch;
      margin-bottom: 20px;
    }

    .national-tag {
      display: inline-flex;
      padding: 6px 12px;
      border: 1px solid var(--night-line);
      border-radius: var(--radius-full);
      font-size: 12px;
      color: var(--on-night);
    }

    .col-title {
      font-size: 12px;
      font-weight: 600;
      color: var(--on-night);
      text-transform: uppercase;
      letter-spacing: 0.14em;
      margin-bottom: 18px;
    }

    .col-links {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .col-links a {
      font-size: 14.5px;
      color: var(--on-night-2);
      transition: color 0.2s ease, padding-left 0.35s var(--ease-expo);
    }

    .col-links a:hover {
      color: var(--accent);
      padding-left: 4px;
    }

    .payment-badges-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 14px;
    }

    .pay-chip {
      padding: 4px 10px;
      border: 1px solid var(--night-line);
      border-radius: var(--radius-full);
      font-size: 12px;
      font-weight: 600;
      color: var(--on-night);
    }

    .payments-desc {
      font-size: 13px;
      line-height: 1.55;
    }

    .footer-bottom {
      display: flex;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
      padding-top: 24px;
      padding-bottom: 24px;
      background-position: center top;
      font-size: 12.5px;
    }

    .wordmark-wrap {
      overflow: hidden;
      line-height: 0.78;
      margin-top: 8px;
    }

    .wordmark {
      display: block;
      font-family: var(--font-display);
      font-weight: 600;
      font-size: 23.5vw;
      letter-spacing: -0.06em;
      text-align: center;
      color: transparent;
      background: linear-gradient(180deg, rgba(255, 244, 230, 0.14) 0%, rgba(255, 244, 230, 0.02) 85%);
      -webkit-background-clip: text;
      background-clip: text;
      white-space: nowrap;
      user-select: none;
    }

    @media (max-width: 960px) {
      .footer-grid { grid-template-columns: 1fr 1fr; }
      .brand-col { grid-column: span 2; }
    }

    @media (max-width: 560px) {
      .footer-grid { grid-template-columns: 1fr; }
      .brand-col { grid-column: span 1; }
      .footer-bottom { flex-direction: column; }
    }
  `]
})
export class FooterComponent implements AfterViewInit, OnDestroy {
  @ViewChild('wordmark') wordmarkRef!: ElementRef<HTMLElement>;

  private zone = inject(NgZone);
  private router = inject(Router);
  private ctx?: gsap.Context;

  /** No "start a fundraiser" pitch on the pages where you are already doing it. */
  readonly showCta = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map((e) => !/^\/(create|admin)\b/.test(e.urlAfterRedirects)),
    ),
    { initialValue: true },
  );

  ngAfterViewInit(): void {
    if (!isBrowser || prefersReducedMotion()) return;

    // The wordmark rises out of the page edge as the reader reaches the very end.
    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        gsap.fromTo(
          this.wordmarkRef.nativeElement,
          { yPercent: 60 },
          {
            yPercent: 0,
            ease: 'none',
            scrollTrigger: {
              trigger: this.wordmarkRef.nativeElement,
              start: 'top bottom',
              end: 'clamp(bottom bottom)',
              scrub: true,
            },
          },
        );
      });
    });
  }

  ngOnDestroy(): void {
    this.ctx?.revert();
  }
}
