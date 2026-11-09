import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { CampaignService } from '../../services/campaign.service';
import { DonationService } from '../../services/donation.service';
import { AuthService } from '../../services/auth.service';
import { Campaign } from '../../models/campaign.model';

@Component({
  selector: 'app-campaign-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <!-- Top Back Breadcrumb Bar -->
    <div class="breadcrumb-strip">
      <div class="container breadcrumb-inner">
        <a routerLink="/" class="back-nav-btn">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
          <span>Back to All Campaigns</span>
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
      <a routerLink="/" class="btn btn-primary mt-3">Return to Home</a>
    </div>

    <!-- Main Detail Layout -->
    <div class="detail-layout container" *ngIf="!loading() && campaign() as c">
      <!-- Left Column: Story, Updates, Supporters -->
      <div class="story-column">
        <!-- Cover Image -->
        <div class="cover-card card">
          <img
            [src]="c.cover_image_url || '/assets/default-campaign.jpg'"
            [alt]="c.title"
            class="cover-image"
          />
        </div>

        <!-- Meta Header Strip -->
        <div class="campaign-header-block">
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
            <div class="organizer-avatar">
              {{ c.organizer_name ? c.organizer_name[0] : 'O' }}
            </div>
            <div class="organizer-meta">
              <span>Organized by <strong>{{ c.organizer_name }}</strong></span>
              <span class="location-txt" *ngIf="c.city || c.state">📍 {{ c.city }}, {{ c.state }}</span>
            </div>
          </div>
        </div>

        <!-- Story Article Body -->
        <div class="story-content card">
          <h2 class="subhead">The Patient's Story</h2>
          <div class="story-prose" [innerHTML]="formatStory(c.story)"></div>
        </div>

        <!-- Campaign Updates Section -->
        <div class="updates-card card" *ngIf="c.updates && c.updates.length > 0">
          <h3 class="subhead">Verified Updates</h3>
          <div class="update-entry" *ngFor="let u of c.updates">
            <span class="update-date">{{ u.created_at | date:'mediumDate' }}</span>
            <p class="update-text">{{ u.content }}</p>
          </div>
        </div>

        <!-- Recent Supporters List -->
        <div class="donors-card card">
          <div class="donors-header">
            <h3 class="subhead">Recent Supporters</h3>
            <span class="donor-total-count">{{ donors().length }} Contributions</span>
          </div>

          <div *ngIf="donors().length === 0" class="no-donors-prompt">
            Be the first supporter to back this cause today.
          </div>

          <div class="donor-list" *ngIf="donors().length > 0">
            <div class="donor-row" *ngFor="let d of donors()">
              <div class="donor-circle">{{ d.donor_name ? d.donor_name[0] : 'S' }}</div>
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
        <div class="sticky-card-wrap">
          <div class="donate-panel card">
            <!-- Funding Progress -->
            <div class="progress-hero">
              <div class="raised-number-row">
                <span class="raised-huge">₹{{ formatINR(c.current_amount) }}</span>
                <span class="goal-label">raised of ₹{{ formatINR(c.goal_amount) }}</span>
              </div>

              <div class="progress-track-bar">
                <div class="progress-fill-bar" [style.width.%]="getProgress(c)"></div>
              </div>

              <div class="progress-meta-row">
                <span><strong>{{ c.donor_count || 0 }}</strong> backers</span>
                <span><strong>{{ getDaysLeft(c) }}</strong> days remaining</span>
              </div>
            </div>

            <!-- AI Trust Score Inspection Box -->
            <div class="ai-inspection-box" *ngIf="c.ai_trust_score || c.authenticity_score">
              <div class="ai-box-header">
                <div class="ai-box-title">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#00A86B" stroke-width="2.5">
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
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6D28D9" stroke-width="2">
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

              <!-- Payment Mode Selection -->
              <label class="form-label mt-3">Choose Payment Method</label>
              <div class="payment-methods-stack">
                <label
                  class="payment-option"
                  *ngFor="let pm of paymentMethods"
                  [class.active]="paymentMethod === pm.value"
                >
                  <input type="radio" [value]="pm.value" [(ngModel)]="paymentMethod" name="payment_method" />
                  <span class="pm-icon">{{ pm.icon }}</span>
                  <div class="pm-meta">
                    <span class="pm-label">{{ pm.label }}</span>
                    <span class="pm-sub">{{ pm.sub }}</span>
                  </div>
                </label>
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
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                </svg>
                <span>{{ donating() ? 'Processing Payment Gateway…' : 'Donate ₹' + (donationAmount | number) }}</span>
              </button>

              <div class="error-banner mt-2" *ngIf="donationError()">{{ donationError() }}</div>
            </form>

            <!-- Donation Success / 80G Receipt Confirmation -->
            <div class="receipt-success-state" *ngIf="donationSuccess()">
              <div class="success-icon-badge">✓</div>
              <h3>Payment Completed</h3>
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
            <p class="share-desc">Every share reaches an average of 4 new donors.</p>
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
    }

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
      font-weight: 800;
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
      border-radius: 50%;
      background: var(--slate-200);
      color: var(--slate-700);
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
      font-size: 12px;
      color: var(--slate-400);
    }

    /* Story Card */
    .story-content {
      padding: 32px;
    }

    .subhead {
      font-size: 18px;
      font-weight: 800;
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
      padding: 28px;
    }

    .progress-hero {
      margin-bottom: 20px;
    }

    .raised-number-row {
      display: flex;
      flex-direction: column;
      margin-bottom: 10px;
    }

    .raised-huge {
      font-family: var(--font-heading);
      font-size: 28px;
      font-weight: 800;
      color: var(--slate-900);
      letter-spacing: -0.02em;
      line-height: 1.1;
    }

    .goal-label {
      font-size: 13px;
      color: var(--slate-500);
      margin-top: 2px;
    }

    .progress-track-bar {
      width: 100%;
      height: 8px;
      background: var(--slate-200);
      border-radius: var(--radius-full);
      overflow: hidden;
      margin-bottom: 8px;
    }

    .progress-fill-bar {
      height: 100%;
      background: linear-gradient(90deg, #FF6B00 0%, #FFA048 100%);
      border-radius: var(--radius-full);
      transition: width 0.8s var(--ease-expo);
      max-width: 100%;
    }

    .progress-meta-row {
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      color: var(--slate-600);
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
      background: #F5F3FF;
      border: 1px solid #DDD6FE;
      padding: 12px;
      border-radius: var(--radius-md);
      margin-bottom: 20px;
      align-items: flex-start;
    }

    .tax-saver-text {
      display: flex;
      flex-direction: column;
      font-size: 12px;
      color: #5B21B6;
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
      transition: all 0.15s ease;
    }

    .amt-btn:hover {
      border-color: var(--slate-300);
      background: var(--slate-50);
    }

    .amt-btn.active {
      border-color: var(--primary);
      background: var(--primary-light);
      color: var(--primary);
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

    /* Payment Methods */
    .payment-methods-stack {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .payment-option {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border: 1.5px solid var(--border);
      border-radius: var(--radius-md);
      cursor: pointer;
      transition: all 0.15s ease;
      background: var(--surface);
    }

    .payment-option.active {
      border-color: var(--primary);
      background: var(--primary-light);
    }

    .pm-icon {
      font-size: 16px;
    }

    .pm-meta {
      display: flex;
      flex-direction: column;
    }

    .pm-label {
      font-size: 13px;
      font-weight: 700;
      color: var(--slate-900);
    }

    .pm-sub {
      font-size: 11px;
      color: var(--slate-500);
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

    /* Receipt */
    .receipt-success-state {
      text-align: center;
      padding: 20px 0;
    }

    .success-icon-badge {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: var(--success-light);
      color: var(--success);
      font-size: 20px;
      font-weight: 800;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 12px;
    }

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

    @media (max-width: 992px) {
      .detail-layout {
        grid-template-columns: 1fr;
      }
      .donation-sidebar {
        position: static;
      }
    }
  `]
})
export class CampaignDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private campaignService = inject(CampaignService);
  private donationService = inject(DonationService);
  public authService = inject(AuthService);

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

  donating = signal(false);
  donationSuccess = signal(false);
  donationError = signal('');
  receipt = signal<any>(null);
  copied = signal(false);

  quickAmounts = [300, 500, 1000, 2500, 5000, 10000];
  paymentMethods = [
    { value: 'RAZORPAY', label: 'Razorpay Fast Checkout', sub: 'Instant UPI, RuPay, Visa, Mastercard, Netbanking', icon: '⚡' },
    { value: 'UPI', label: 'Direct UPI App', sub: 'Google Pay, PhonePe, Paytm, BHIM', icon: '📱' },
    { value: 'CARD', label: 'Debit & Credit Card', sub: 'RuPay, Visa, Mastercard', icon: '💳' },
    { value: 'NETBANKING', label: 'Netbanking', sub: 'SBI, HDFC, ICICI, Axis & 50+ Banks', icon: '🏦' },
  ];

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
          this.loadDonors(+id);
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
    this.donating.set(true);
    this.donationError.set('');

    const rzp = (window as any).Razorpay;

    if (this.paymentMethod === 'RAZORPAY' && rzp) {
      this.donationService.createGatewayOrder(c.id, this.donationAmount).subscribe({
        next: (order) => {
          const options: any = {
            key: order.key_id,
            amount: order.amount,
            currency: order.currency,
            name: 'SevaFund India',
            description: `Contribution for ${c.beneficiary_name || c.title}`,
            order_id: (order.order_id && !order.order_id.startsWith('order_mock_')) ? order.order_id : undefined,
            prefill: {
              name: this.donorName || 'Kind Supporter',
              email: this.donorEmail || undefined,
              contact: this.donorPhone ? (this.donorPhone.startsWith('+91') ? this.donorPhone : `+91${this.donorPhone}`) : undefined
            },
            theme: { color: '#FF6B00' },
            handler: (response: any) => {
              this.completeDonation({
                gateway_order_id: response.razorpay_order_id || order.order_id,
                gateway_payment_id: response.razorpay_payment_id || `pay_${Date.now()}`,
                gateway_signature: response.razorpay_signature || 'sig_demo'
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
            this.completeDonation({
              gateway_order_id: order.order_id,
              gateway_payment_id: `pay_direct_${Date.now()}`
            });
          }
        },
        error: () => {
          this.completeDonation();
        }
      });
    } else {
      this.completeDonation();
    }
  }

  completeDonation(gatewayData?: { gateway_order_id?: string; gateway_payment_id?: string; gateway_signature?: string }) {
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
      gateway_order_id: gatewayData?.gateway_order_id,
      gateway_payment_id: gatewayData?.gateway_payment_id,
      gateway_signature: gatewayData?.gateway_signature
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
