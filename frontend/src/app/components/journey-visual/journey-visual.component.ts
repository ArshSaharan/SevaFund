import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export type JourneyVisualKind = 'story' | 'audit' | 'gift' | 'settle';

export interface AuditRow {
  label: string;
  /** Share of the total score, in percent. */
  weight: number;
  value: number;
}

/**
 * Illustrations for the home page's "Follow one rupee" chapters. Decorative —
 * the chapter copy beside each one carries the meaning — so it is aria-hidden.
 * `.bar-fill` and `.flow-node` are animated by the home page's chapter reveal.
 */
@Component({
  selector: 'app-journey-visual',
  standalone: true,
  imports: [CommonModule],
  host: { 'aria-hidden': 'true' },
  template: `
    <ng-container [ngSwitch]="kind">
      <div *ngSwitchCase="'story'" class="vis">
        <div class="doc-head">
          <span class="doc-dots"><i></i><i></i><i></i></span>
          <span>fundraiser-story.txt</span>
        </div>
        <p class="doc-line strong">A 7-year-old has been diagnosed with a hole in the heart (VSD).</p>
        <p class="doc-line">Surgery at a Pune hospital is estimated at ₹3,20,000.</p>
        <span class="skel"></span>
        <span class="skel short"></span>
        <p class="ai-chip">✦ Story assistant · “Add the doctor’s name and the UHID.”</p>
      </div>

      <div *ngSwitchCase="'audit'" class="vis">
        <div class="audit-row" *ngFor="let r of auditRows">
          <span>{{ r.label }} <small>{{ r.weight }}%</small></span>
          <span class="bar"><span class="bar-fill" [style.--v]="r.value / 100"></span></span>
          <span class="audit-val">{{ r.value }}</span>
        </div>
        <div class="audit-total">
          <span>Trust score</span>
          <strong>{{ auditTotal }}</strong>
          <span class="live-pill">Goes live</span>
        </div>
        <p class="note">80+ goes live · 50–79 human review · below 50 needs more proof</p>
      </div>

      <div *ngSwitchCase="'gift'" class="vis">
        <p class="pay-to">Paying fundraiser <strong>#2041</strong></p>
        <p class="pay-amount">₹1,000</p>
        <div class="pay-methods">
          <span class="on">UPI</span><span>RuPay</span><span>Card</span><span>Netbanking</span>
        </div>
        <dl class="pay-lines">
          <div><dt>To the cause</dt><dd>₹1,000</dd></div>
          <div><dt>Platform fee</dt><dd>₹0</dd></div>
        </dl>
        <p class="pay-receipt">✓ 80G receipt emailed</p>
      </div>

      <div *ngSwitchCase="'settle'" class="vis">
        <div class="flow">
          <div class="flow-node">Donors <small>Many small gifts</small></div>
          <span class="flow-line"><i></i></span>
          <div class="flow-node">Verified fundraiser <small>Tracked on SevaFund</small></div>
          <span class="flow-line"><i></i></span>
          <div class="flow-node end">Hospital account <small>NEFT / RTGS</small></div>
        </div>
        <p class="note update"><span class="dot"></span> Update posted · “Surgery done, recovering in the ward.”</p>
      </div>
    </ng-container>
  `,
  styles: [`
    :host { display: block; }

    .vis {
      padding: 22px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 18px;
      font-size: 13px;
      color: var(--ink-2);
    }

    .note { margin-top: 12px; font-size: 11.5px; color: var(--ink-3); }

    /* story */
    .doc-head {
      display: flex;
      align-items: center;
      gap: 12px;
      padding-bottom: 12px;
      margin-bottom: 14px;
      border-bottom: 1px solid var(--line);
      font-family: var(--font-mono);
      font-size: 11.5px;
      color: var(--ink-3);
    }

    .doc-dots { display: flex; gap: 5px; }
    .doc-dots i { width: 8px; height: 8px; border-radius: 50%; background: var(--slate-200); }
    .doc-line { margin-bottom: 8px; line-height: 1.5; }
    .doc-line.strong { color: var(--ink); font-weight: 600; }
    .skel { display: block; height: 8px; margin: 12px 0; border-radius: 4px; background: var(--slate-100); }
    .skel.short { width: 60%; }

    .ai-chip {
      margin-top: 16px;
      padding: 10px 12px;
      border-radius: 12px;
      background: var(--violet-soft);
      border: 1px solid var(--violet-line);
      color: var(--violet);
      font-size: 12.5px;
      font-weight: 600;
    }

    /* audit */
    .audit-row {
      display: grid;
      grid-template-columns: 11.5em 1fr 2.2em;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }

    .audit-row small { color: var(--ink-3); font-size: 11px; }
    .bar { height: 6px; border-radius: var(--radius-full); background: var(--slate-100); overflow: hidden; }

    .bar-fill {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: var(--leaf);
      transform: scaleX(var(--v));
      transform-origin: left;
    }

    .audit-val { text-align: right; font-weight: 700; color: var(--ink); }

    .audit-total {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 18px;
      padding-top: 16px;
      border-top: 1px dashed var(--line);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--ink-3);
    }

    .audit-total strong {
      font-family: var(--font-display);
      font-size: 34px;
      font-weight: 500;
      letter-spacing: -0.02em;
      color: var(--leaf);
    }

    .live-pill {
      margin-left: auto;
      padding: 4px 10px;
      border-radius: var(--radius-full);
      background: var(--leaf-soft);
      color: var(--leaf);
      letter-spacing: 0.06em;
    }

    /* gift */
    .pay-to { color: var(--ink-3); }
    .pay-to strong { color: var(--ink); }

    .pay-amount {
      margin: 6px 0 14px;
      font-family: var(--font-display);
      font-size: 44px;
      line-height: 1;
      letter-spacing: -0.03em;
      color: var(--ink);
    }

    .pay-methods { display: flex; flex-wrap: wrap; gap: 6px; }

    .pay-methods span {
      padding: 5px 11px;
      border: 1px solid var(--line);
      border-radius: var(--radius-full);
      font-size: 12px;
      font-weight: 600;
    }

    .pay-methods .on { background: var(--ink); border-color: var(--ink); color: var(--paper); }
    .pay-lines { margin: 16px 0 12px; border-top: 1px dashed var(--line); }
    .pay-lines div { display: flex; justify-content: space-between; padding: 9px 0; border-bottom: 1px dashed var(--line); }
    .pay-lines dd { font-weight: 700; color: var(--ink); }
    .pay-receipt { font-weight: 600; color: var(--leaf); }

    /* settle */
    .flow { display: grid; justify-items: start; }

    .flow-node {
      display: flex;
      flex-direction: column;
      padding: 10px 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--surface);
      font-weight: 600;
      color: var(--ink);
    }

    .flow-node small { font-weight: 500; font-size: 11.5px; color: var(--ink-3); }
    .flow-node.end { border-color: var(--leaf); background: var(--leaf-soft); }

    .flow-line {
      position: relative;
      width: 2px;
      height: 26px;
      margin-left: 22px;
      background: var(--line);
      overflow: hidden;
    }

    .flow-line i {
      position: absolute;
      left: -2px;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--accent);
      animation: flow 1.6s linear infinite;
    }

    @keyframes flow {
      from { top: -6px; }
      to { top: 100%; }
    }

    .update { display: flex; align-items: center; gap: 10px; margin-top: 16px; font-size: 12px; color: var(--ink-2); }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--leaf); animation: pulse-dot 2s infinite; }

    @media (max-width: 640px) {
      .vis { font-size: 12.5px; }
      .audit-row { grid-template-columns: 8em 1fr 2em; gap: 8px; }
    }
  `]
})
export class JourneyVisualComponent {
  @Input({ required: true }) kind!: JourneyVisualKind;
  @Input() auditRows: AuditRow[] = [];

  /** Weighted total, exactly as the backend verifier combines the sub-scores. */
  get auditTotal(): number {
    return Math.round(this.auditRows.reduce((sum, r) => sum + (r.weight * r.value) / 100, 0));
  }
}
