import { AfterViewInit, Component, ElementRef, NgZone, OnDestroy, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NextChapterComponent } from '../../components/next-chapter/next-chapter.component';
import { MOTION, gsap, ScrollTrigger, isBrowser, prefersReducedMotion } from '../../animation';

interface Dimension {
  label: string;
  /** Share of the total score, in percent. */
  weight: number;
  /** Example sub-score used in the illustration (0–100). */
  example: number;
  question: string;
  text: string;
  signals: string[];
}

interface Band {
  min: number;
  range: string;
  label: string;
  tone: 'reject' | 'info' | 'review' | 'live';
}

/**
 * Mirrors app/services/ai_verifier.py: four weighted sub-scores and the
 * decision bands (AUTO_APPROVE ≥ 80, FLAG_FOR_REVIEW ≥ 50, NEEDS_MORE_INFO ≥ 35, else REJECT).
 */
@Component({
  selector: 'app-trust',
  standalone: true,
  imports: [CommonModule, NextChapterComponent, ...MOTION],
  templateUrl: './trust.component.html',
  styleUrl: './trust.component.css',
})
export class TrustComponent implements AfterViewInit, OnDestroy {
  @ViewChild('story', { static: true }) storyRef!: ElementRef<HTMLElement>;
  @ViewChild('scoreNum', { static: true }) scoreRef!: ElementRef<HTMLElement>;
  @ViewChild('status', { static: true }) statusRef!: ElementRef<HTMLElement>;
  @ViewChild('bandsEl', { static: true }) bandsRef!: ElementRef<HTMLElement>;

  private zone = inject(NgZone);
  private ctx?: gsap.Context;

  readonly dimensions: Dimension[] = [
    {
      label: 'Cost plausibility',
      weight: 30,
      example: 92,
      question: 'Is the amount realistic for this treatment?',
      text: 'The verifier recognises the procedure in the story and compares the goal with typical costs at Indian hospitals. Requests well above the benchmark need a hospital estimate signed by the medical superintendent.',
      signals: ['Treatment detected from the story', 'Goal compared with Indian hospital benchmarks', 'Elevated and excessive amounts flagged'],
    },
    {
      label: 'Specificity',
      weight: 25,
      example: 84,
      question: 'Could someone actually check this?',
      text: 'Real cases name real places. The verifier looks for the hospital, the treating doctor, the city, clinical terms and billing records such as a UHID or an estimate letter.',
      signals: ['Named hospital or clinic', 'Treating doctor or specialist', 'UHID, estimate letter or discharge summary', 'Itemised costs in rupees'],
    },
    {
      label: 'Red-flag screen',
      weight: 25,
      example: 100,
      question: 'Does it read like a scam?',
      text: 'Every story is screened for patterns common in fraud. If the fundraiser is for someone else, the patient must be named, too.',
      signals: ['Requests to pay a personal UPI or GPay number', 'Crypto, hawala or gift-card payments', 'Miracle-cure claims', 'Lottery and prize-money language', 'Talk of forged bills or stamps'],
    },
    {
      label: 'Documentation',
      weight: 20,
      example: 80,
      question: 'Is there paper behind it?',
      text: 'Each supporting document raises the score. A fundraiser with no documents at all starts from a low documentation score.',
      signals: ['Hospital estimate on letterhead', 'Discharge summary', 'Government ID'],
    },
  ];

  readonly bands: Band[] = [
    { min: 0, range: '<35', label: 'Rejected', tone: 'reject' },
    { min: 35, range: '35–49', label: 'More proof', tone: 'info' },
    { min: 50, range: '50–79', label: 'Human review', tone: 'review' },
    { min: 80, range: '80+', label: 'Goes live', tone: 'live' },
  ];

  readonly safeguards = [
    { title: 'A human in the loop', text: 'Fundraisers that land between 50 and 79 are reviewed by a moderator, who can approve, ask for more information, or reject.' },
    { title: 'An audit trail', text: 'Every moderator decision is written to an audit log with the reason and the before-and-after status.' },
    { title: 'Money to the hospital', text: 'Verified medical funds are settled to the hospital’s registered account by NEFT/RTGS — not to a personal account.' },
    { title: 'Checkout by Razorpay', text: 'UPI, RuPay, card and netbanking payments run through Razorpay’s checkout.' },
    { title: '80G receipts', text: 'Eligible fundraisers issue a Section 80G receipt with a certificate number as soon as the payment is confirmed.' },
    { title: 'Updates you can follow', text: 'Organisers post updates as treatment progresses, so supporters see what their money did.' },
  ];

  /** Weighted total of the example sub-scores (≈ 90). */
  readonly exampleScore = Math.round(this.dimensions.reduce((s, d) => s + (d.weight * d.example) / 100, 0));

  bandFor(score: number): Band {
    return [...this.bands].reverse().find((b) => score >= b.min) ?? this.bands[0];
  }

  ngAfterViewInit(): void {
    if (!isBrowser || prefersReducedMotion()) return;

    const story = this.storyRef.nativeElement;
    const scoreEl = this.scoreRef.nativeElement;
    const statusEl = this.statusRef.nativeElement;
    const bandsEl = this.bandsRef.nativeElement;
    const rows = gsap.utils.toArray<HTMLElement>('.report-row', story);
    const fills = rows.map((r) => r.querySelector('.row-fill'));
    const steps = gsap.utils.toArray<HTMLElement>('.story-step', story);
    const progress = this.dimensions.map(() => ({ p: 0 }));

    // Recompute the live score from how far each dimension has "filled".
    const render = () => {
      const score = this.dimensions.reduce((sum, d, i) => sum + (d.weight * d.example * progress[i].p) / 100, 0);
      const band = this.bandFor(score);
      scoreEl.textContent = String(Math.round(score));
      // Stay neutral while the first checks are still filling in; then name the band.
      const building = score < 35;
      statusEl.textContent = building ? 'Scoring…' : band.label;
      statusEl.dataset['tone'] = building ? '' : band.tone;
      bandsEl.style.setProperty('--score', score.toFixed(2));
    };

    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        gsap.set(fills, { scaleX: 0 });
        render();

        this.dimensions.forEach((d, i) => {
          const step = steps[i];
          const scrollTrigger = { trigger: step, start: 'top 78%', end: 'center 45%', scrub: 0.5 };
          gsap.to(progress[i], { p: 1, ease: 'none', onUpdate: render, scrollTrigger });
          gsap.to(fills[i], { scaleX: d.example / 100, ease: 'none', scrollTrigger });

          ScrollTrigger.create({
            trigger: step,
            start: 'top 60%',
            end: 'bottom 60%',
            toggleClass: { targets: [rows[i], step], className: 'is-active' },
          });
        });

        const decision = steps[this.dimensions.length];
        ScrollTrigger.create({
          trigger: decision,
          start: 'top 60%',
          end: 'bottom 40%',
          toggleClass: { targets: [story.querySelector('.report')!, decision], className: 'is-decided' },
        });
      }, story);
    });
  }

  ngOnDestroy(): void {
    this.ctx?.revert();
  }
}
