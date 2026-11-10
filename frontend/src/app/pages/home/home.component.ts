import {
  AfterViewInit,
  Component,
  ElementRef,
  NgZone,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { CampaignService } from '../../services/campaign.service';
import { SmoothScrollService } from '../../services/smooth-scroll.service';
import { Campaign } from '../../models/campaign.model';
import { CampaignCardComponent } from '../../components/campaign-card/campaign-card.component';
import { MarqueeComponent } from '../../components/marquee/marquee.component';
import { NextChapterComponent } from '../../components/next-chapter/next-chapter.component';
import { AuditRow, JourneyVisualComponent, JourneyVisualKind } from '../../components/journey-visual/journey-visual.component';
import { MOTION, gsap, ScrollTrigger, isBrowser, prefersReducedMotion } from '../../animation';

/** The verifier's auto-approve threshold (AI_AUTO_APPROVE_SCORE_THRESHOLD on the backend). */
const VERIFIED_SCORE = 80;

interface Chapter {
  num: string;
  kicker: string;
  title: string;
  text: string;
  visual: JourneyVisualKind;
}

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterLink, CampaignCardComponent, MarqueeComponent, NextChapterComponent, JourneyVisualComponent, ...MOTION],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css',
})
export class HomeComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('hero', { static: true }) heroRef!: ElementRef<HTMLElement>;
  @ViewChild('journey', { static: true }) journeyRef!: ElementRef<HTMLElement>;
  @ViewChild('track', { static: true }) trackRef!: ElementRef<HTMLElement>;
  @ViewChild('impact', { static: true }) impactRef!: ElementRef<HTMLElement>;
  @ViewChild('featuredSection', { static: true }) featuredRef!: ElementRef<HTMLElement>;

  private campaignService = inject(CampaignService);
  private smoothScroll = inject(SmoothScrollService);
  private zone = inject(NgZone);

  featured = signal<Campaign[]>([]);
  featuredState = signal<'loading' | 'ready' | 'empty'>('loading');

  readonly trustPoints = [
    '0% platform fee',
    'AI cost benchmarks',
    'Section 80G receipts',
    'Direct hospital NEFT',
    'UPI · RuPay · Netbanking',
    'Human review for flagged cases',
  ];

  readonly chapters: Chapter[] = [
    {
      num: '01',
      kicker: 'The story',
      title: 'A family asks for help — clearly.',
      text: 'The organiser shares the diagnosis, the hospital and the estimate. Our AI story assistant helps them say it plainly and accurately, without exaggeration.',
      visual: 'story',
    },
    {
      num: '02',
      kicker: 'The audit',
      title: 'Every request is checked before it goes live.',
      text: 'The amount is compared with typical Indian hospital costs, the story is screened for scam patterns and the documents are counted. Strong cases go live; borderline ones go to a human moderator.',
      visual: 'audit',
    },
    {
      num: '03',
      kicker: 'The gift',
      title: 'You give in seconds. Every rupee keeps working.',
      text: 'Pay by UPI, RuPay, card or netbanking. SevaFund takes no platform fee, and eligible gifts get a Section 80G receipt the moment the payment clears.',
      visual: 'gift',
    },
    {
      num: '04',
      kicker: 'The settlement',
      title: 'The money goes to the hospital, not a middleman.',
      text: 'For verified medical cases, funds are settled straight to the hospital’s registered account by NEFT/RTGS — and organisers post updates as treatment progresses.',
      visual: 'settle',
    },
  ];

  /** Example audit using the verifier's real weights: 0.30·92 + 0.25·84 + 0.25·100 + 0.20·80 ≈ 90. */
  readonly auditRows: AuditRow[] = [
    { label: 'Cost plausibility', weight: 30, value: 92 },
    { label: 'Specificity', weight: 25, value: 84 },
    { label: 'Red-flag screen', weight: 25, value: 100 },
    { label: 'Documentation', weight: 20, value: 80 },
  ];

  private ctx?: gsap.Context;
  private mm?: gsap.MatchMedia;
  private sub?: Subscription;
  private destroyed = false;

  ngOnInit(): void {
    this.sub = this.campaignService.getCampaigns(1, 3, undefined, undefined, 'trending', VERIFIED_SCORE).subscribe({
      next: (res) => {
        const list = res.campaigns || res.items || [];
        this.featured.set(list);
        this.featuredState.set(list.length ? 'ready' : 'empty');
        this.afterRender(() => this.revealFeatured());
      },
      error: () => {
        this.featuredState.set('empty');
        this.afterRender(() => this.smoothScroll.refresh());
      },
    });
  }

  ngAfterViewInit(): void {
    if (!isBrowser) return;

    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        if (prefersReducedMotion()) return;
        this.playHeroIntro();
        this.scrubHeroExit();
      });

      // Pinned journey (created before anything below it, so trigger order matches page order).
      this.mm = gsap.matchMedia();
      this.mm.add(
        { wide: '(min-width: 900px)', motion: '(prefers-reduced-motion: no-preference)' },
        (context) => {
          const { wide, motion } = context.conditions as { wide: boolean; motion: boolean };
          if (!motion) return undefined;
          return wide ? this.buildHorizontalJourney() : this.buildStackedJourney();
        },
      );

      this.ctx?.add(() => {
        if (!prefersReducedMotion()) this.expandImpactBand();
      });
    });
  }

  /* ------------------------------------------------------------------ */
  /* Hero                                                                */
  /* ------------------------------------------------------------------ */

  private playHeroIntro(): void {
    const q = gsap.utils.selector(this.heroRef.nativeElement);

    gsap.timeline({ delay: 0.1 })
      .from(q('.hero-eyebrow'), { y: 20, autoAlpha: 0, duration: 0.9 })
      .from(q('.hero-lede, .hero-actions'), { y: 28, autoAlpha: 0, stagger: 0.12 }, 0.7)
      .from(q('.receipt'), { y: 140, rotate: 9, autoAlpha: 0, duration: 1.5 }, 0.35)
      .from(q('.receipt-checks li'), { x: -18, autoAlpha: 0, stagger: 0.09, duration: 0.7 }, 1.0)
      .from(q('.score-fill'), { scaleX: 0, duration: 1.6, ease: 'power3.out' }, 1.15)
      .from(q('.stamp'), { scale: 2.6, rotate: -32, autoAlpha: 0, duration: 0.55, ease: 'back.out(2.2)' }, 1.85)
      .from(q('.float-chip'), { scale: 0.7, autoAlpha: 0, stagger: 0.14, duration: 0.9, ease: 'back.out(1.8)' }, 1.4)
      .from(q('.scroll-cue'), { autoAlpha: 0, duration: 1 }, 1.9);
  }

  /** As the hero leaves, copy drifts up and dims while the report tilts away. */
  private scrubHeroExit(): void {
    const hero = this.heroRef.nativeElement;
    const q = gsap.utils.selector(hero);

    gsap.timeline({
      scrollTrigger: { trigger: hero, start: 'top top', end: 'bottom top', scrub: true, refreshPriority: 2 },
    })
      .to(q('.hero-copy'), { yPercent: -16, autoAlpha: 0.2, ease: 'none' }, 0)
      .to(q('.receipt-wrap'), { yPercent: -22, rotate: -7, ease: 'none' }, 0)
      .to(q('.blob-a'), { yPercent: 35, ease: 'none' }, 0)
      .to(q('.blob-b'), { yPercent: -25, ease: 'none' }, 0)
      .to(q('.scroll-cue'), { autoAlpha: 0, ease: 'none', duration: 0.2 }, 0);
  }

  /* ------------------------------------------------------------------ */
  /* "Follow one rupee" journey                                          */
  /* ------------------------------------------------------------------ */

  /** Desktop: pin the section and scroll the chapters sideways. */
  private buildHorizontalJourney(): () => void {
    const section = this.journeyRef.nativeElement;
    const track = this.trackRef.nativeElement;
    const chapters = gsap.utils.toArray<HTMLElement>('.chapter', section);
    const labels = gsap.utils.toArray<HTMLElement>('.rail-label', section);
    const rail = section.querySelector<HTMLElement>('.rail')!;
    const setFill = gsap.quickSetter(section.querySelector('.rail-fill')!, 'scaleX');
    const setCoin = gsap.quickSetter(section.querySelector('.rail-coin')!, 'x', 'px');

    section.classList.add('is-horizontal');
    const distance = () => Math.max(0, track.scrollWidth - document.documentElement.clientWidth);

    const activate = (index: number) => {
      chapters.forEach((ch, i) => ch.classList.toggle('is-active', i === index));
      labels.forEach((l, i) => l.classList.toggle('is-active', i <= index));
    };
    activate(0);

    // Declared up-front: ScrollTrigger renders the tween (firing onUpdate) while it is still being created.
    let scroll: gsap.core.Tween | undefined;
    scroll = gsap.to(track, {
      x: () => -distance(),
      ease: 'none',
      onUpdate: () => {
        const p = scroll?.progress() ?? 0;
        setFill(p);
        setCoin(p * rail.offsetWidth);
      },
      scrollTrigger: {
        trigger: section,
        start: 'top top',
        end: () => `+=${distance()}`,
        pin: true,
        scrub: 0.8,
        anticipatePin: 1,
        invalidateOnRefresh: true,
        refreshPriority: 1,
      },
    });

    // First chapter reveals as the section arrives (it starts on screen).
    this.revealChapter(chapters[0], { trigger: section, start: 'top 55%', toggleActions: 'play none none reverse' });

    chapters.forEach((chapter, i) => {
      ScrollTrigger.create({
        trigger: chapter,
        containerAnimation: scroll,
        start: 'left 55%',
        end: 'right 55%',
        onToggle: (self) => self.isActive && activate(i),
      });
      if (i > 0) {
        this.revealChapter(chapter, {
          trigger: chapter,
          containerAnimation: scroll,
          start: 'left 82%',
          toggleActions: 'play none none reverse',
        });
      }
    });

    return () => section.classList.remove('is-horizontal');
  }

  /** Mobile / narrow: chapters stack vertically and reveal as they arrive. */
  private buildStackedJourney(): undefined {
    gsap.utils.toArray<HTMLElement>('.chapter', this.journeyRef.nativeElement).forEach((chapter) =>
      this.revealChapter(chapter, { trigger: chapter, start: 'top 80%', once: true }),
    );
    return undefined;
  }

  private revealChapter(chapter: HTMLElement, scrollTrigger: ScrollTrigger.Vars): void {
    const tl = gsap.timeline({ scrollTrigger });
    tl.from(chapter.querySelectorAll('[data-anim]'), { y: 48, autoAlpha: 0, stagger: 0.08, duration: 1 })
      .from(chapter.querySelectorAll('.bar-fill'), { scaleX: 0, stagger: 0.1, duration: 1.2, ease: 'power3.out' }, 0.35)
      .from(chapter.querySelectorAll('.flow-node'), { scale: 0.8, autoAlpha: 0, stagger: 0.15, duration: 0.8, ease: 'back.out(2)' }, 0.35);
  }

  /* ------------------------------------------------------------------ */
  /* Impact band & featured                                              */
  /* ------------------------------------------------------------------ */

  /** The dark impact card grows from an inset card to full-bleed as it scrolls in. */
  private expandImpactBand(): void {
    gsap.fromTo(
      this.impactRef.nativeElement.querySelector('.impact-card'),
      { clipPath: 'inset(7% 5% 7% 5% round 40px)' },
      {
        clipPath: 'inset(0% 0% 0% 0% round 0px)',
        ease: 'none',
        scrollTrigger: {
          trigger: this.impactRef.nativeElement,
          start: 'top 90%',
          end: 'top 10%',
          scrub: true,
        },
      },
    );
  }

  private revealFeatured(): void {
    if (!isBrowser || this.destroyed) return;

    if (!prefersReducedMotion()) {
      this.ctx?.add(() => {
        const cards = this.featuredRef.nativeElement.querySelectorAll('.featured-item');
        gsap.set(cards, { autoAlpha: 0, y: 70 });
        ScrollTrigger.batch(cards, {
          start: 'top 90%',
          once: true,
          onEnter: (batch) =>
            gsap.to(batch, {
              autoAlpha: 1,
              y: 0,
              stagger: 0.12,
              duration: 1.2,
              clearProps: 'transform,opacity,visibility',
            }),
        });
      });
    }
    this.smoothScroll.refresh();
  }

  /** Run after Angular has rendered the latest state, outside the zone. */
  private afterRender(fn: () => void): void {
    this.zone.runOutsideAngular(() => setTimeout(() => !this.destroyed && fn(), 0));
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.sub?.unsubscribe();
    this.mm?.revert();
    this.ctx?.revert();
  }
}
