import { Component, ElementRef, NgZone, OnDestroy, OnInit, ViewChild, effect, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { Title } from '@angular/platform-browser';
import { CampaignService } from '../../services/campaign.service';
import { DonationService } from '../../services/donation.service';
import { AuthService } from '../../services/auth.service';
import { Campaign } from '../../models/campaign.model';
import { SmoothScrollService } from '../../services/smooth-scroll.service';
import { CountUpDirective, RevealDirective, SpotlightDirective, celebrate, isBrowser } from '../../animation';

@Component({
  selector: 'app-campaign-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, RevealDirective, CountUpDirective, SpotlightDirective],
  template: `
    <!-- Top Back Breadcrumb Bar -->
    <div class="breadcrumb-strip">
      <div class="container breadcrumb-inner">
        <a routerLink="/campaigns" class="back-nav-btn">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
          <span>All causes</span>
        </a>
      </div>
    </div>

    <!-- Loading State -->
    <div class="loading-state container" *ngIf="loading()">
      <div class="loading-spinner"></div>
      <p>Verifying campaign records & live data…</p>
    </div>

    <!-- Error State -->
    <div class="error-state container card" *ngIf="!loading() && !campaign()">
      <h2>Fundraiser Not Found</h2>
      <p>The campaign you requested may have been fulfilled, moved, or is under compliance audit.</p>
      <a routerLink="/campaigns" class="btn btn-primary mt-3">Browse causes</a>
    </div>

    <!-- Main Detail Layout -->
    <div class="detail-layout container" *ngIf="!loading() && campaign() as c">
      <!-- Left Column: Story, Updates, Supporters -->
      <div class="story-column">
        <!-- Cover Image -->
        <div class="cover-card card" appReveal="clip">
          <img
            [src]="c.cover_image_url || '/assets/default-campaign.jpg'"
            [alt]="c.title"
            class="cover-image"
          />
        </div>

        <!-- Meta Header Strip -->
        <div class="campaign-header-block" appReveal>
          <div class="meta-pills-row">
            <span class="badge badge-primary">{{ c.category }}</span>

            <span
              class="trust-score-pill"
              [class.verified]="((c.ai_trust_score || c.authenticity_score) || 0) >= 80"
              [class.review]="((c.ai_trust_score || c.authenticity_score) || 0) >= 50 && ((c.ai_trust_score || c.authenticity_score) || 0) < 80"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
              <span>{{ ((c.ai_trust_score || c.authenticity_score) || 0) >= 80 ? 'AI Verified Cause' : 'Under Review' }}</span>
            </span>

            <span class="hospital-pill" *ngIf="c.hospital_name">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              </svg>
              {{ c.hospital_name }}
            </span>
          </div>

          <h1 class="campaign-headline">{{ c.title }}</h1>

          <div class="organizer-attribution">
            <div class="organizer-avatar" aria-hidden="true">
              <ng-container *ngIf="c.organizer_name; else organiserIcon">{{ c.organizer_name[0] }}</ng-container>
              <ng-template #organiserIcon>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle>
                </svg>
              </ng-template>
            </div>
            <div class="organizer-meta">
              <span *ngIf="c.organizer_name">Organised by <strong>{{ c.organizer_name }}</strong></span>
              <span *ngIf="!c.organizer_name">Campaign organiser</span>
              <span class="location-txt" *ngIf="c.city || c.state">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle>
                </svg>
                {{ c.city }}{{ c.city && c.state ? ', ' : '' }}{{ c.state }}
              </span>
            </div>
          </div>
        </div>

        <!-- Story Article Body -->
        <div class="story-content card" appReveal>
          <h2 class="subhead">The Patient's Story</h2>
          <div class="story-prose" [innerHTML]="formatStory(c.story)"></div>
        </div>

        <!-- Campaign Updates Section -->
        <div class="updates-card card" *ngIf="c.updates && c.updates.length > 0" appReveal>
          <h3 class="subhead">Verified Updates</h3>
          <div class="update-entry" *ngFor="let u of c.updates">
            <span class="update-date">{{ u.created_at | date:'mediumDate' }}</span>
            <p class="update-text">{{ u.content }}</p>
          </div>
        </div>

        <!-- Recent Supporters List -->
        <div class="donors-card card" appReveal>
          <div class="donors-header">
            <h3 class="subhead">Recent Supporters</h3>
            <span class="donor-total-count">{{ donors().length }} Contributions</span>
          </div>

          <div *ngIf="donors().length === 0" class="no-donors-prompt">
            Be the first supporter to back this cause today.
          </div>

          <div class="donor-list" *ngIf="donors().length > 0" appReveal="up" [revealStagger]="0.07">
            <div class="donor-row" *ngFor="let d of donors(); let i = index">
              <div class="donor-circle" [attr.data-tint]="i % 5">{{ d.donor_name ? d.donor_name[0] : 'S' }}</div>
              <div class="donor-details">
                <div class="donor-name-amount">
                  <strong>{{ d.donor_name || 'Anonymous Supporter' }}</strong>
                  <span class="donor-amount">₹{{ formatINR(d.amount) }}</span>
                </div>
                <p class="donor-blessing" *ngIf="d.message || d.support_message">
                  "{{ d.message || d.support_message }}"
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Sticky Donation Card & AI Trust Panel -->
      <div class="donation-sidebar">
        <div class="sticky-card-wrap" appReveal [revealDelay]="0.15">
          <div class="donate-panel card" #donatePanel>
            <!-- Funding Progress -->
            <div class="progress-hero">
              <div class="raised-number-row">
                <span class="raised-huge">
                  <span [appCountUp]="inrValue(c.current_amount)" [countDecimals]="inrDecimals(c.current_amount)"
                        countPrefix="₹" [countSuffix]="inrUnit(c.current_amount)" [countDuration]="1.8">₹{{ formatINR(c.current_amount) }}</span>
                </span>
                <span class="goal-label">raised of ₹{{ formatINR(c.goal_amount) }} goal</span>
                <span class="percent-badge">
                  <span [appCountUp]="getProgress(c)" countSuffix="%" [countDuration]="1.8">{{ getProgress(c) }}%</span> funded
                </span>
              </div>

              <div class="progress-track-bar" role="progressbar" [attr.aria-valuenow]="getProgress(c)" aria-valuemin="0"
                   aria-valuemax="100" [attr.aria-label]="getProgress(c) + '% funded'">
                <div class="progress-fill-bar" [class.sheen]="getProgress(c) > 0"
                     [style.width.%]="barReady() ? getProgress(c) : 0"></div>
              </div>

              <div class="progress-meta-row">
                <span><strong [appCountUp]="c.donor_count || 0" [countDuration]="1.6">{{ c.donor_count || 0 }}</strong> backers</span>
                <span class="days-chip" [class.is-ongoing]="!c.deadline">{{ daysLabel(c) }}</span>
              </div>
            </div>

            <!-- AI Trust Score Inspection Box -->
            <div class="ai-inspection-box" *ngIf="c.ai_trust_score || c.authenticity_score">
              <div class="ai-box-header">
                <div class="ai-box-title">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="ai-shield" aria-hidden="true">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  </svg>
                  <span>AI Cost Benchmark Score</span>
                </div>
                <span class="ai-score-pill">{{ c.ai_trust_score ?? c.authenticity_score }}/100</span>
              </div>

              <div class="ai-dim-grid" *ngIf="c.ai_dimension_scores">
                <div class="dim-stat">
                  <span class="dim-lbl">Specificity</span>
                  <div class="dim-progress"><div [style.width.%]="c.ai_dimension_scores.specificity_score"></div></div>
                  <span class="dim-val">{{ c.ai_dimension_scores.specificity_score | number:'1.0-0' }}%</span>
                </div>
                <div class="dim-stat">
                  <span class="dim-lbl">Cost Benchmark</span>
                  <div class="dim-progress"><div [style.width.%]="c.ai_dimension_scores.benchmark_score"></div></div>
                  <span class="dim-val">{{ c.ai_dimension_scores.benchmark_score | number:'1.0-0' }}%</span>
                </div>
                <div class="dim-stat">
                  <span class="dim-lbl">Documentation</span>
                  <div class="dim-progress"><div [style.width.%]="c.ai_dimension_scores.documentation_score"></div></div>
                  <span class="dim-val">{{ c.ai_dimension_scores.documentation_score | number:'1.0-0' }}%</span>
                </div>
              </div>
            </div>

            <!-- 80G Tax Exemption Note -->
            <div class="tax-saver-banner" *ngIf="c.is_80g_tax_exempt">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
              </svg>
              <div class="tax-saver-text">
                <strong>Section 80G Tax Exemption Eligible</strong>
                <span>Tax exemption receipt will be issued instantly upon payment.</span>
              </div>
            </div>

            <!-- Donation Form -->
            <form class="donation-form" (ngSubmit)="submitDonation()" *ngIf="!donationSuccess()">
              <label class="form-label">Select Contribution</label>
              <div class="amount-pills">
                <button
                  type="button"
                  class="amt-btn"
                  *ngFor="let amt of quickAmounts"
                  [class.active]="donationAmount === amt"
                  (click)="donationAmount = amt"
                >
                  ₹{{ amt | number }}
                </button>
              </div>

              <div class="custom-amt-input-wrap">
                <span class="currency-prefix">₹</span>
                <input
                  type="number"
                  class="input custom-amt-input"
                  placeholder="Or enter custom amount"
                  [(ngModel)]="donationAmount"
                  name="amount"
                  min="10"
                  required
                />
              </div>

              <!-- Payment: UPI, cards and netbanking are all chosen inside Razorpay Checkout -->
              <div class="secure-checkout mt-3">
                <div class="secure-head">
                  <span class="secure-icon" aria-hidden="true">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                    </svg>
                  </span>
                  <div>
                    <strong>Secure checkout by Razorpay</strong>
                    <span>Choose UPI, a card or netbanking in Razorpay's secure payment window.</span>
                  </div>
                </div>
                <div class="method-chips" aria-label="Accepted payment methods">
                  <span>UPI</span><span>Cards</span><span>Netbanking</span><span>Wallets</span>
                </div>
              </div>

              <!-- Donor Details -->
              <div class="donor-fields-block mt-3">
                <label class="form-label">Donor Information</label>
                <div class="form-fields-grid">
                  <input
                    type="text"
                    class="input"
                    placeholder="Full Name (optional)"
                    [(ngModel)]="donorName"
                    name="donor_name"
                  />
                  <input
                    type="email"
                    class="input"
                    placeholder="Email for 80G receipt"
                    [(ngModel)]="donorEmail"
                    name="donor_email"
                  />
                </div>

                <div class="form-fields-grid mt-2">
                  <input
                    type="tel"
                    class="input"
                    placeholder="Mobile number (10 digits)"
                    [(ngModel)]="donorPhone"
                    name="donor_phone"
                    maxlength="10"
                  />
                  <input
                    *ngIf="c.is_80g_tax_exempt"
                    type="text"
                    class="input"
                    placeholder="PAN Card (for 80G claim)"
                    [(ngModel)]="donorPan"
                    name="donor_pan"
                    style="text-transform:uppercase"
                    maxlength="10"
                  />
                </div>

                <textarea
                  class="input mt-2"
                  placeholder="Words of blessing or support for the patient…"
                  [(ngModel)]="donorMessage"
                  name="message"
                  rows="2"
                ></textarea>

                <label class="anon-checkbox mt-2">
                  <input type="checkbox" [(ngModel)]="isAnonymous" name="is_anonymous" />
                  <span>Make my donation anonymous on the public supporters list</span>
                </label>
              </div>

              <!-- Submit CTA -->
              <button
                type="submit"
                class="btn btn-primary btn-full btn-lg donate-submit-btn mt-4"
                [disabled]="donating() || donationAmount < 10"
              >
                <span class="btn-spinner" *ngIf="donating()" aria-hidden="true"></span>
                <svg *ngIf="!donating()" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                </svg>
                <span>{{ donating() ? 'Opening secure checkout…' : 'Donate ₹' + (donationAmount | number) }}</span>
              </button>

              <div class="error-banner mt-2" *ngIf="donationError()">{{ donationError() }}</div>
            </form>

            <!-- Donation Success / 80G Receipt Confirmation -->
            <div class="receipt-success-state" *ngIf="donationSuccess()" role="status">
              <svg class="success-check" width="64" height="64" viewBox="0 0 52 52" aria-hidden="true">
                <circle class="success-check-ring" cx="26" cy="26" r="24"></circle>
                <path class="success-check-tick" d="M15 27l7 7 15-16"></path>
              </svg>
              <h3>Thank you. Your gift is in.</h3>
              <p class="receipt-thank-msg">
                Your contribution of <strong>₹{{ (receipt()?.amount || donationAmount) | number }}</strong> has been verified and settled to
                <strong>{{ c.beneficiary_name || c.title }}</strong>.
              </p>

              <div class="receipt-audit-box">
                <div class="receipt-row">
                  <span>Transaction Ref</span>
                  <code>{{ receipt()?.transaction_ref || receipt()?.transaction_id }}</code>
                </div>
                <div class="receipt-row" *ngIf="receipt()?.tax_exemption_80g_number">
                  <span>80G Certificate No.</span>
                  <strong class="receipt-tax-code">{{ receipt()?.tax_exemption_80g_number }}</strong>
                </div>
                <div class="receipt-row">
                  <span>Platform Fee</span>
                  <strong class="text-green">₹0.00 (100% Passed Directly)</strong>
                </div>
              </div>

              <div class="receipt-btn-group mt-3">
                <button class="btn btn-outline btn-sm" (click)="printReceipt()">Print 80G Receipt</button>
                <button class="btn btn-primary btn-sm" (click)="donationSuccess.set(false)">Donate Again</button>
              </div>
            </div>
          </div>

          <!-- Share Fundraiser Card -->
          <div class="share-box card mt-4">
            <h4 class="share-title">Amplify This Fundraiser</h4>
            <p class="share-desc">Know someone who could help? Share this fundraiser with them.</p>
            <div class="share-actions-row">
              <button class="btn btn-outline btn-sm share-btn" (click)="shareWhatsApp(c)">
                WhatsApp
              </button>
              <button class="btn btn-outline btn-sm share-btn" (click)="copyLink()">
                Copy Link
              </button>
            </div>
            <p class="copied-indicator mt-2" *ngIf="copied()">Link copied to clipboard ✓</p>
          </div>
        </div>
      </div>

      <!-- Phones: the donation form sits below the story, so keep a way to reach it close at hand -->
      <div class="mobile-donate-bar" [class.is-hidden]="!showDonateBar()">
        <div class="mdb-meta">
          <strong>₹{{ formatINR(c.current_amount) }} <span>raised</span></strong>
          <span class="mdb-track" aria-hidden="true"><span [style.width.%]="getProgress(c)"></span></span>
          <span>{{ getProgress(c) }}% of ₹{{ formatINR(c.goal_amount) }}</span>
        </div>
        <button class="btn btn-primary" type="button" (click)="scrollToDonate()" [attr.tabindex]="showDonateBar() ? null : -1">
          Donate
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19"></line><polyline points="19 12 12 19 5 12"></polyline>
          </svg>
        </button>
      </div>
    </div>
  `,
  styles: [`
    .breadcrumb-strip {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 12px 0;
    }

    .back-nav-btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 13.5px;
      font-weight: 600;
      color: var(--slate-600);
      transition: color 0.15s ease;
    }

    .back-nav-btn:hover {
      color: var(--primary);
    }

    .detail-layout {
      display: grid;
      grid-template-columns: 1fr 400px;
      gap: 36px;
      padding: 32px var(--space-5) 80px;
      align-items: start;
    }

    /* Left Story Column */
    .story-column {
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .cover-card {
      height: 380px;
      border-radius: var(--radius-xl);
      overflow: hidden;
    }

    .cover-image {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 1.4s var(--ease-expo);
    }

    .cover-card:hover .cover-image { transform: scale(1.035); }

    .campaign-header-block {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .meta-pills-row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .trust-score-pill {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 4px 10px;
      border-radius: var(--radius-full);
      font-size: 11.5px;
      font-weight: 700;
    }

    .trust-score-pill.verified {
      background: var(--success-light);
      color: var(--success);
      border: 1px solid var(--success-border);
    }

    .trust-score-pill.review {
      background: var(--warning-light);
      color: var(--warning);
      border: 1px solid var(--warning-border);
    }

    .hospital-pill {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 12px;
      color: var(--secondary);
      font-weight: 600;
    }

    .campaign-headline {
      font-size: clamp(1.8rem, 3vw, 2.5rem);
      font-weight: 600;
      color: var(--slate-900);
      line-height: 1.2;
      letter-spacing: -0.02em;
    }

    .organizer-attribution {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 4px;
    }

    .organizer-avatar {
      width: 36px;
      height: 36px;
      flex-shrink: 0;
      border-radius: 50%;
      background: var(--primary-light);
      color: var(--primary);
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .organizer-meta {
      display: flex;
      flex-direction: column;
      font-size: 13.5px;
      color: var(--slate-600);
    }

    .location-txt {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: var(--slate-500);
    }

    /* Story Card */
    .story-content {
      padding: 32px;
    }

    .subhead {
      font-size: 18px;
      font-weight: 600;
      color: var(--slate-900);
      margin-bottom: 18px;
      letter-spacing: -0.01em;
    }

    .story-prose {
      font-size: 15px;
      line-height: 1.8;
      color: var(--slate-700);
    }

    /* Updates */
    .updates-card {
      padding: 28px;
    }

    .update-entry {
      border-left: 2px solid var(--primary);
      padding-left: 16px;
      margin-bottom: 18px;
    }

    .update-date {
      font-size: 12px;
      font-weight: 700;
      color: var(--slate-400);
      display: block;
      margin-bottom: 4px;
    }

    .update-text {
      font-size: 14px;
      color: var(--slate-700);
      line-height: 1.6;
    }

    /* Supporters */
    .donors-card {
      padding: 28px;
    }

    .donors-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 18px;
    }

    .donors-header .subhead {
      margin-bottom: 0;
    }

    .donor-total-count {
      font-size: 13px;
      font-weight: 600;
      color: var(--slate-500);
    }

    .no-donors-prompt {
      font-size: 14px;
      color: var(--slate-500);
      padding: 20px 0;
    }

    .donor-list {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .donor-row {
      display: flex;
      gap: 12px;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--border-light);
    }

    .donor-row:last-child {
      border-bottom: none;
      padding-bottom: 0;
    }

    .donor-circle {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: var(--primary-light);
      color: var(--primary);
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      font-size: 13px;
    }

    .donor-circle[data-tint="1"] { background: var(--success-light); color: var(--leaf); }
    .donor-circle[data-tint="2"] { background: color-mix(in srgb, var(--violet) 14%, transparent); color: var(--violet); }
    .donor-circle[data-tint="3"] { background: color-mix(in srgb, #FFB547 22%, transparent); color: var(--accent-ink); }
    .donor-circle[data-tint="4"] { background: var(--slate-100); color: var(--ink-2); }

    .donor-details {
      flex: 1;
    }

    .donor-name-amount {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 14px;
    }

    .donor-amount {
      font-family: var(--font-heading);
      font-weight: 700;
      color: var(--primary);
    }

    .donor-blessing {
      font-size: 12.5px;
      font-style: italic;
      color: var(--slate-500);
      margin-top: 2px;
    }

    /* Sidebar / Sticky Card */
    .donation-sidebar {
      position: sticky;
      top: 90px;
    }

    .donate-panel {
      position: relative;
      padding: 28px;
      overflow: hidden;
    }

    /* A thin saffron-to-leaf rule along the top of the panel */
    .donate-panel::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, var(--accent), #FFB547 55%, var(--leaf));
    }

    .progress-hero {
      margin-bottom: 20px;
    }

    .raised-number-row {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      margin-bottom: 14px;
    }

    .raised-huge {
      font-family: var(--font-heading);
      font-size: 34px;
      font-variant-numeric: tabular-nums;
      font-weight: 600;
      color: var(--slate-900);
      letter-spacing: -0.02em;
      line-height: 1.1;
    }

    .goal-label {
      font-size: 13px;
      color: var(--slate-500);
      margin-top: 4px;
    }

    .percent-badge {
      margin-top: 10px;
      padding: 3px 10px;
      border-radius: var(--radius-full);
      background: var(--primary-light);
      color: var(--accent-ink);
      font-size: 12px;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
    }

    .progress-track-bar {
      width: 100%;
      height: 10px;
      background: var(--slate-200);
      border-radius: var(--radius-full);
      overflow: hidden;
      margin-bottom: 8px;
    }

    .progress-fill-bar {
      height: 100%;
      background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 55%, var(--leaf)));
      border-radius: var(--radius-full);
      transition: width 1.8s var(--ease-expo);
      max-width: 100%;
    }

    .progress-meta-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 4px;
      font-size: 13px;
      color: var(--slate-600);
    }

    .days-chip {
      padding: 3px 10px;
      border-radius: var(--radius-full);
      background: var(--slate-100);
      color: var(--ink-2);
      font-size: 12px;
      font-weight: 600;
    }

    .days-chip.is-ongoing {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--success-light);
      color: var(--leaf);
    }

    .days-chip.is-ongoing::before {
      content: '';
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: currentColor;
      animation: pulse-dot 2s infinite;
    }

    /* AI Inspection Box */
    .ai-inspection-box {
      background: var(--slate-50);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 14px;
      margin-bottom: 18px;
    }

    .ai-box-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }

    .ai-shield { color: var(--leaf); }

    .ai-box-title {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12.5px;
      font-weight: 700;
      color: var(--slate-800);
    }

    .ai-score-pill {
      font-size: 11.5px;
      font-weight: 700;
      background: var(--secondary-light);
      color: var(--secondary);
      padding: 2px 8px;
      border-radius: var(--radius-full);
    }

    .ai-dim-grid {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .dim-stat {
      display: grid;
      grid-template-columns: 90px 1fr 34px;
      gap: 8px;
      align-items: center;
      font-size: 11.5px;
    }

    .dim-lbl {
      color: var(--slate-500);
    }

    .dim-progress {
      height: 4px;
      background: var(--slate-200);
      border-radius: var(--radius-full);
      overflow: hidden;
    }

    .dim-progress div {
      height: 100%;
      background: var(--secondary);
    }

    .dim-val {
      font-weight: 700;
      color: var(--slate-700);
      text-align: right;
    }

    /* Tax Saver */
    .tax-saver-banner {
      display: flex;
      gap: 10px;
      background: var(--violet-soft);
      border: 1px solid var(--violet-line);
      color: var(--violet);
      padding: 12px;
      border-radius: var(--radius-md);
      margin-bottom: 20px;
      align-items: flex-start;
    }

    .tax-saver-text {
      display: flex;
      flex-direction: column;
      font-size: 12px;
      color: var(--violet);
      line-height: 1.4;
    }

    /* Form */
    .amount-pills {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-bottom: 10px;
    }

    .amt-btn {
      padding: 8px 10px;
      border-radius: var(--radius-md);
      border: 1.5px solid var(--border);
      background: var(--surface);
      font-size: 13.5px;
      font-weight: 700;
      color: var(--slate-700);
      cursor: pointer;
      font-variant-numeric: tabular-nums;
      transition: border-color 0.2s ease, background-color 0.2s ease, color 0.2s ease,
                  transform 0.35s var(--ease-spring), box-shadow 0.3s var(--ease-expo);
    }

    .amt-btn:hover {
      border-color: var(--slate-300);
      background: var(--slate-50);
      transform: translateY(-2px);
    }

    .amt-btn:active { transform: scale(0.95); transition-duration: 0.1s; }

    .amt-btn.active {
      border-color: var(--primary);
      background: var(--primary-light);
      color: var(--primary);
      box-shadow: 0 6px 16px -8px var(--accent-glow);
    }

    .custom-amt-input-wrap {
      position: relative;
    }

    .currency-prefix {
      position: absolute;
      left: 14px;
      top: 50%;
      transform: translateY(-50%);
      font-weight: 700;
      color: var(--slate-400);
      font-size: 15px;
    }

    .custom-amt-input {
      padding-left: 30px;
      font-size: 15px;
      font-weight: 700;
    }

    /* Secure checkout */
    .secure-checkout {
      padding: 14px;
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      background: var(--slate-50);
    }

    .secure-head {
      display: flex;
      gap: 12px;
      align-items: flex-start;
    }

    .secure-head strong {
      display: block;
      font-size: 13.5px;
      color: var(--ink);
    }

    .secure-head span:not(.secure-icon) {
      display: block;
      margin-top: 2px;
      font-size: 12px;
      line-height: 1.5;
      color: var(--slate-500);
    }

    .secure-icon {
      display: grid;
      place-items: center;
      flex-shrink: 0;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: var(--success-light);
      color: var(--leaf);
    }

    .method-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 12px;
    }

    .method-chips span {
      padding: 3px 9px;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      background: var(--surface);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.02em;
      color: var(--ink-2);
    }

    .form-fields-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .anon-checkbox {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--slate-600);
      cursor: pointer;
    }

    .donate-submit-btn {
      width: 100%;
    }

    .btn-spinner {
      width: 16px;
      height: 16px;
      border: 2px solid currentColor;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
    }

    /* Receipt */
    .receipt-success-state {
      text-align: center;
      padding: 20px 0;
      animation: fadeInUp 0.6s var(--ease-expo);
    }

    /* Animated check: the ring draws, then the tick */
    .success-check {
      display: block;
      margin: 0 auto 14px;
    }

    .success-check-ring {
      fill: var(--success-light);
      stroke: var(--leaf);
      stroke-width: 2.5;
      stroke-dasharray: 151;
      stroke-dashoffset: 151;
      transform: rotate(-90deg);
      transform-origin: center;
      animation: draw-stroke 0.8s var(--ease-expo) 0.1s forwards;
    }

    .success-check-tick {
      fill: none;
      stroke: var(--leaf);
      stroke-width: 3.5;
      stroke-linecap: round;
      stroke-linejoin: round;
      stroke-dasharray: 36;
      stroke-dashoffset: 36;
      animation: draw-stroke 0.5s var(--ease-expo) 0.65s forwards;
    }

    @keyframes draw-stroke { to { stroke-dashoffset: 0; } }

    .receipt-audit-box {
      background: var(--slate-50);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 12px;
      margin: 16px 0;
      text-align: left;
    }

    .receipt-row {
      display: flex;
      justify-content: space-between;
      font-size: 12.5px;
      padding: 4px 0;
    }

    .receipt-btn-group {
      display: flex;
      gap: 8px;
      justify-content: center;
    }

    .error-banner {
      padding: 8px 12px;
      border-radius: var(--radius-md);
      background: var(--danger-light);
      border: 1px solid var(--danger-border);
      font-size: 12px;
      color: var(--danger);
      text-align: center;
    }

    /* Share */
    .share-box {
      padding: 20px;
    }

    .share-title {
      font-size: 14px;
      font-weight: 700;
      margin-bottom: 4px;
    }

    .share-desc {
      font-size: 12.5px;
      color: var(--slate-500);
      margin-bottom: 12px;
    }

    .share-actions-row {
      display: flex;
      gap: 8px;
    }

    .share-btn {
      flex: 1;
    }

    .copied-indicator {
      font-size: 12px;
      color: var(--secondary);
      font-weight: 600;
    }

    .loading-state, .error-state {
      text-align: center;
      padding: 80px 20px;
    }

    .loading-spinner {
      width: 40px;
      height: 40px;
      border: 3px solid var(--slate-200);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 16px;
    }

    .mobile-donate-bar { display: none; }

    @media (max-width: 992px) {
      .detail-layout {
        grid-template-columns: 1fr;
      }
      .donation-sidebar {
        position: static;
      }

      .mobile-donate-bar {
        position: fixed;
        left: 12px;
        right: 12px;
        bottom: calc(12px + env(safe-area-inset-bottom, 0px));
        z-index: 850;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 14px;
        padding: 10px 10px 10px 20px;
        border: 1px solid var(--line);
        border-radius: var(--radius-full);
        background: var(--glass-bg);
        backdrop-filter: blur(16px) saturate(160%);
        -webkit-backdrop-filter: blur(16px) saturate(160%);
        box-shadow: var(--shadow-xl);
        transition: transform 0.55s var(--ease-expo), opacity 0.3s ease, visibility 0s;
      }

      .mobile-donate-bar.is-hidden {
        transform: translateY(140%);
        opacity: 0;
        visibility: hidden;
        pointer-events: none;
        transition: transform 0.55s var(--ease-expo), opacity 0.3s ease, visibility 0s 0.55s;
      }
    }

    .mdb-meta {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 0;
      flex: 1;
      line-height: 1.15;
    }

    .mdb-meta strong {
      font-family: var(--font-heading);
      font-size: 18px;
      color: var(--ink);
    }

    .mdb-meta strong span { font-family: var(--font-body); font-size: 12px; font-weight: 500; color: var(--ink-3); }
    .mdb-meta > span:last-child { font-size: 11.5px; color: var(--ink-3); }

    .mdb-track {
      display: block;
      height: 4px;
      max-width: 160px;
      border-radius: var(--radius-full);
      background: var(--slate-200);
      overflow: hidden;
    }

    .mdb-track span {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 55%, var(--leaf)));
    }
  `]
})
export class CampaignDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private campaignService = inject(CampaignService);
  private donationService = inject(DonationService);
  public authService = inject(AuthService);
  private titleService = inject(Title);
  private smoothScroll = inject(SmoothScrollService);
  private zone = inject(NgZone);

  campaign = signal<Campaign | null>(null);
  loading = signal(true);
  donors = signal<any[]>([]);

  donationAmount = 500;
  paymentMethod = 'RAZORPAY';
  upiId = '';
  donorName = '';
  donorEmail = '';
  donorPhone = '';
  donorMessage = '';
  donorPan = '';
  isAnonymous = false;

  donatePanel?: ElementRef<HTMLElement>;
  /** True while the donation form is still further down the page (drives the phone donate bar). */
  showDonateBar = signal(false);
  private panelObserver?: IntersectionObserver;

  @ViewChild('donatePanel') set donatePanelRef(ref: ElementRef<HTMLElement> | undefined) {
    this.donatePanel = ref;
    this.panelObserver?.disconnect();
    if (!ref || !isBrowser || typeof IntersectionObserver === 'undefined') return;
    this.zone.runOutsideAngular(() => {
      this.panelObserver = new IntersectionObserver(([entry]) => {
        const below = !entry.isIntersecting && entry.boundingClientRect.top > 0;
        if (below !== this.showDonateBar()) this.zone.run(() => this.showDonateBar.set(below));
      }, { threshold: 0.05 });
      this.panelObserver.observe(ref.nativeElement);
    });
  }
  /** The funding bar grows in shortly after the page appears. */
  barReady = signal(false);

  donating = signal(false);
  donationSuccess = signal(false);
  donationError = signal('');
  receipt = signal<any>(null);
  copied = signal(false);

  quickAmounts = [300, 500, 1000, 2500, 5000, 10000];

  constructor() {
    // A small celebration when a gift goes through (skipped for reduced motion inside celebrate()).
    effect(() => {
      if (!this.donationSuccess()) return;
      this.zone.runOutsideAngular(() => setTimeout(() => celebrate(this.donatePanel?.nativeElement ?? null), 80));
    });
    // Lets the back-to-top button sit above the phone donate bar.
    effect(() => {
      if (isBrowser) document.documentElement.classList.toggle('has-bottom-bar', this.showDonateBar());
    });
  }

  ngOnDestroy(): void {
    this.panelObserver?.disconnect();
    if (isBrowser) document.documentElement.classList.remove('has-bottom-bar');
  }

  scrollToDonate(): void {
    const panel = this.donatePanel?.nativeElement;
    if (!panel) return;
    this.smoothScroll.scrollTo(panel, { offset: -90, duration: 1.2 });
    panel.querySelector<HTMLElement>('.amt-btn.active, .amt-btn')?.focus({ preventScroll: true });
  }

  ngOnInit() {
    const user = this.authService.currentUser();
    if (user) {
      if (user.full_name) this.donorName = user.full_name;
      if (user.email) this.donorEmail = user.email;
      if (user.phone_number) this.donorPhone = user.phone_number.replace('+91', '').trim();
    }

    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.campaignService.getCampaign(+id).subscribe({
        next: (c) => {
          this.campaign.set(c);
          this.loading.set(false);
          this.titleService.setTitle(`${c.title} · SevaFund India`);
          this.loadDonors(+id);
          this.zone.runOutsideAngular(() => setTimeout(() => this.zone.run(() => this.barReady.set(true)), 350));
          // Page height changed: re-measure scroll triggers (footer, reveals).
          this.zone.runOutsideAngular(() => setTimeout(() => this.smoothScroll.refresh(), 0));
        },
        error: () => this.loading.set(false)
      });
    }
  }

  loadDonors(id: number) {
    this.donationService.getCampaignDonations(id).subscribe({
      next: (res) => {
        const list = Array.isArray(res) ? res : (res.donations || res.items || []);
        this.donors.set(list);
      },
      error: () => {}
    });
  }

  submitDonation() {
    const c = this.campaign();
    if (!c || this.donationAmount < 10) return;
    this.donationError.set('');

    // UPI, cards and netbanking are all completed inside Razorpay Checkout. The server records the donation only
    // after it verifies the Razorpay payment (signature, order, amount and captured status).
    const rzp = (window as any).Razorpay;
    if (!rzp) {
      this.donationError.set('Online payment is unavailable right now (Razorpay Checkout could not load). No payment was taken.');
      return;
    }
    this.donating.set(true);

    this.donationService.createGatewayOrder(c.id, this.donationAmount).subscribe({
      next: (order) => {
        const options: any = {
          key: order.key_id,
          amount: order.amount,
          currency: order.currency,
          name: 'SevaFund India',
          description: `Contribution for ${c.beneficiary_name || c.title}`,
          order_id: order.order_id,
          prefill: {
            name: this.donorName || 'Kind Supporter',
            email: this.donorEmail || undefined,
            contact: this.donorPhone ? (this.donorPhone.startsWith('+91') ? this.donorPhone : `+91${this.donorPhone}`) : undefined
          },
          theme: { color: '#F26B1D' },
          handler: (response: any) => {
            if (!response?.razorpay_order_id || !response?.razorpay_payment_id || !response?.razorpay_signature) {
              this.donating.set(false);
              this.donationError.set('The payment could not be confirmed. If money was debited, it will be reconciled by Razorpay.');
              return;
            }
            this.completeDonation({
              gateway_order_id: response.razorpay_order_id,
              gateway_payment_id: response.razorpay_payment_id,
              gateway_signature: response.razorpay_signature
            });
          },
          modal: {
            ondismiss: () => {
              this.donating.set(false);
            }
          }
        };

        try {
          const rzpInstance = new rzp(options);
          rzpInstance.open();
        } catch (e) {
          this.donating.set(false);
          this.donationError.set('Could not open Razorpay Checkout. No payment was taken.');
        }
      },
      error: (err) => {
        this.donating.set(false);
        this.donationError.set(err?.error?.detail || 'Online payments are unavailable right now. No payment was taken.');
      }
    });
  }

  completeDonation(gatewayData: { gateway_order_id: string; gateway_payment_id: string; gateway_signature: string }) {
    const c = this.campaign();
    if (!c) return;

    this.donationService.donate(c.id, {
      amount: this.donationAmount,
      payment_method: this.paymentMethod,
      upi_id: this.upiId || undefined,
      donor_name: this.donorName || 'Kind Supporter',
      donor_email: this.donorEmail || undefined,
      donor_phone: this.donorPhone || undefined,
      donor_pan: this.donorPan || undefined,
      message: this.donorMessage || undefined,
      support_message: this.donorMessage || undefined,
      is_anonymous: this.isAnonymous,
      gateway_order_id: gatewayData.gateway_order_id,
      gateway_payment_id: gatewayData.gateway_payment_id,
      gateway_signature: gatewayData.gateway_signature
    }).subscribe({
      next: (res) => {
        this.receipt.set(res);
        this.donationSuccess.set(true);
        this.donating.set(false);

        this.campaign.update(camp => {
          if (!camp) return null;
          return {
            ...camp,
            current_amount: camp.current_amount + this.donationAmount,
            donor_count: (camp.donor_count || 0) + 1
          };
        });

        const newDonor = {
          donor_name: this.isAnonymous ? 'Anonymous Supporter' : (this.donorName || 'Kind Supporter'),
          amount: this.donationAmount,
          message: this.donorMessage,
          created_at: new Date().toISOString()
        };
        this.donors.update(prev => [newDonor, ...prev]);
      },
      error: (err) => {
        this.donationError.set(err?.error?.detail || 'Donation failed. Please try again.');
        this.donating.set(false);
      }
    });
  }

  printReceipt() {
    window.print();
  }

  getProgress(c: Campaign): number {
    if (!c.goal_amount) return 0;
    return Math.min(100, Math.round((c.current_amount / c.goal_amount) * 100));
  }

  /** "Ongoing" when there is no deadline (never "0 days remaining"). */
  daysLabel(c: Campaign): string {
    if (!c.deadline) return 'Ongoing';
    const days = this.getDaysLeft(c);
    if (days === 0) return 'Ended';
    return days === 1 ? '1 day left' : `${days} days left`;
  }

  /** formatINR split into number, decimals and unit, so the total can count up as ₹8.4L. */
  inrValue(amount: number): number {
    if (!amount) return 0;
    if (amount >= 10_000_000) return +(amount / 10_000_000).toFixed(1);
    if (amount >= 100_000) return +(amount / 100_000).toFixed(1);
    if (amount >= 1000) return +(amount / 1000).toFixed(1);
    return amount;
  }

  inrDecimals(amount: number): number {
    return amount >= 1000 ? 1 : 0;
  }

  inrUnit(amount: number): string {
    if (amount >= 10_000_000) return 'Cr';
    if (amount >= 100_000) return 'L';
    if (amount >= 1000) return 'K';
    return '';
  }

  getDaysLeft(c: Campaign): number {
    if (!c.deadline) return 0;
    const diff = new Date(c.deadline).getTime() - Date.now();
    return Math.max(0, Math.ceil(diff / 86400000));
  }

  formatINR(amount: number): string {
    if (!amount) return '0';
    if (amount >= 10_000_000) return (amount / 10_000_000).toFixed(1) + 'Cr';
    if (amount >= 100_000)    return (amount / 100_000).toFixed(1) + 'L';
    if (amount >= 1000)       return (amount / 1000).toFixed(1) + 'K';
    return amount.toString();
  }

  formatStory(story: string): string {
    return (story || '').replace(/\n/g, '<br>');
  }

  shareWhatsApp(c: Campaign) {
    const url = window.location.href;
    const text = encodeURIComponent(`Please support this verified cause: "${c.title}" — ${url}`);
    window.open(`https://wa.me/?text=${text}`, '_blank');
  }

  copyLink() {
    navigator.clipboard.writeText(window.location.href).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    });
  }
}
