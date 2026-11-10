import { AfterViewInit, Component, ElementRef, NgZone, OnDestroy, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { NextChapterComponent } from '../../components/next-chapter/next-chapter.component';
import { MOTION, gsap, ScrollTrigger, isBrowser, prefersReducedMotion } from '../../animation';

interface Step {
  title: string;
  text: string;
  tags: string[];
  link?: { path: string; label: string };
}

@Component({
  selector: 'app-how-it-works',
  standalone: true,
  imports: [CommonModule, RouterLink, NextChapterComponent, ...MOTION],
  templateUrl: './how-it-works.component.html',
  styleUrl: './how-it-works.component.css',
})
export class HowItWorksComponent implements AfterViewInit, OnDestroy {
  @ViewChild('timeline', { static: true }) timelineRef!: ElementRef<HTMLElement>;

  private zone = inject(NgZone);
  private ctx?: gsap.Context;

  readonly steps: Step[] = [
    {
      title: 'Start a fundraiser',
      text: 'Add the patient, the hospital, the city and the amount needed in a short guided form.',
      tags: ['Patient & beneficiary', 'Hospital & city', 'Goal amount'],
      link: { path: '/create', label: 'Open the form' },
    },
    {
      title: 'Tell the story — with help',
      text: 'Our AI story assistant turns medical details into a clear, honest story, and points out what is missing, like the doctor’s name or the UHID.',
      tags: ['AI drafting', 'Missing-detail prompts'],
    },
    {
      title: 'Attach the proof',
      text: 'Upload the hospital estimate on letterhead, a discharge summary or a prescription. Every document strengthens the case.',
      tags: ['Estimate letter', 'Discharge summary', 'Govt ID'],
    },
    {
      title: 'AI verification',
      text: 'The verifier scores cost plausibility, specificity, red-flag screening and documentation. 80 and above goes live; 50–79 goes to a human moderator; lower scores must add proof or are rejected.',
      tags: ['4 weighted checks', 'Human review'],
      link: { path: '/trust', label: 'See the scoring' },
    },
    {
      title: 'Donors give',
      text: 'Supporters pay by UPI, RuPay, card or netbanking through Razorpay. There is no platform fee, and eligible fundraisers issue 80G receipts instantly.',
      tags: ['UPI', '0% platform fee', 'Section 80G'],
    },
    {
      title: 'Settlement & updates',
      text: 'For verified medical cases, payouts go straight to the hospital’s registered account by NEFT/RTGS. Organisers post updates so donors can follow the outcome.',
      tags: ['Direct to hospital', 'Progress updates'],
    },
  ];

  readonly donorPoints = [
    'See the trust score and its breakdown on every fundraiser',
    'Pay with UPI, RuPay, card or netbanking',
    'Get an instant 80G receipt where eligible',
    'Give anonymously if you prefer',
  ];

  readonly organiserPoints = [
    'A guided setup with an AI story assistant',
    'Know what is missing before you publish',
    'Zero platform fee on what you raise',
    'Funds settled directly with the hospital',
  ];

  readonly faqs = [
    {
      q: 'Does SevaFund charge a fee?',
      a: 'No. SevaFund charges a 0% platform fee — your receipt shows the platform fee as ₹0.',
    },
    {
      q: 'What does the AI actually check?',
      a: 'Four things: whether the amount is plausible for the treatment against typical Indian hospital costs, how specific the request is (hospital, doctor, city, UHID), whether the story contains known scam patterns, and how many supporting documents are attached.',
    },
    {
      q: 'Who reviews borderline fundraisers?',
      a: 'Fundraisers scoring 50–79 are flagged for a human moderator, who can approve them, ask the organiser for more information, or reject them.',
    },
    {
      q: 'Will I get a tax receipt?',
      a: 'Fundraisers marked 80G-eligible issue a Section 80G receipt as soon as your payment is confirmed. Add your PAN at checkout to claim the deduction.',
    },
    {
      q: 'Can I donate anonymously?',
      a: 'Yes. Tick the anonymity option at checkout and your name will not appear on the public supporters list.',
    },
    {
      q: 'Where does the money go?',
      a: 'For verified medical fundraisers, funds are settled directly to the hospital’s registered account by NEFT/RTGS rather than to an individual.',
    },
  ];

  ngAfterViewInit(): void {
    if (!isBrowser || prefersReducedMotion()) return;

    const timeline = this.timelineRef.nativeElement;

    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        // The spine draws itself as you read down the steps.
        gsap.fromTo(
          timeline.querySelector('.spine-fill'),
          { scaleY: 0 },
          {
            scaleY: 1,
            ease: 'none',
            scrollTrigger: { trigger: timeline, start: 'top 62%', end: 'bottom 62%', scrub: 0.4 },
          },
        );

        // Each node lights up as the line reaches it.
        gsap.utils.toArray<HTMLElement>('.step', timeline).forEach((step) => {
          ScrollTrigger.create({
            trigger: step,
            start: 'top 62%',
            toggleClass: { targets: step, className: 'is-reached' },
          });
        });
      }, timeline);
    });
  }

  ngOnDestroy(): void {
    this.ctx?.revert();
  }
}
