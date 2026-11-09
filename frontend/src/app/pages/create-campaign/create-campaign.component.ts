import { Component, OnInit, OnDestroy, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { RouterModule, Router } from '@angular/router';
import { CampaignService } from '../../services/campaign.service';
import { AiService } from '../../services/ai.service';
import { Subject } from 'rxjs';
import { debounceTime, takeUntil } from 'rxjs/operators';

const CATEGORIES = ['MEDICAL', 'EMERGENCY', 'EDUCATION', 'COMMUNITY', 'MEMORIAL', 'ANIMALS'];

@Component({
  selector: 'app-create-campaign',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="create-page container">
      <!-- Page Header -->
      <div class="create-header">
        <span class="sub-header-pill">Verified Crowdfunding</span>
        <h1>Launch a Verified Fundraiser</h1>
        <p>Our automated AI verification checks medical costs, diagnoses, and hospital bills to fast-track donor trust.</p>
      </div>

      <!-- Step Indicator -->
      <div class="steps-progress-bar">
        <div
          class="step-node"
          *ngFor="let s of steps; let i = index"
          [class.active]="currentStep === i"
          [class.done]="currentStep > i"
        >
          <div class="step-circle">
            <span *ngIf="currentStep <= i">{{ i + 1 }}</span>
            <svg *ngIf="currentStep > i" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </div>
          <span class="step-label">{{ s }}</span>
        </div>
      </div>

      <form (ngSubmit)="submitCampaign()" class="wizard-form">
        <!-- Step 0: Basics -->
        <div class="wizard-panel card" *ngIf="currentStep === 0">
          <div class="panel-header">
            <h2>Basic Information</h2>
            <p>Provide foundational details regarding the cause and required funding goal.</p>
          </div>

          <div class="form-group">
            <label class="form-label">Campaign Title *</label>
            <input
              class="input"
              type="text"
              [(ngModel)]="form.title"
              name="title"
              placeholder="e.g., Support Priya's Chemotherapy Treatment at Tata Memorial Hospital"
              required
            />
          </div>

          <div class="form-group mt-3">
            <label class="form-label">Cause Category *</label>
            <select class="input" [(ngModel)]="form.category" name="category">
              <option *ngFor="let c of categories" [value]="c">{{ c }}</option>
            </select>
          </div>

          <div class="form-row mt-3">
            <div class="form-group">
              <label class="form-label">City</label>
              <input class="input" type="text" [(ngModel)]="form.city" name="city" placeholder="e.g., Mumbai" />
            </div>
            <div class="form-group">
              <label class="form-label">State</label>
              <input class="input" type="text" [(ngModel)]="form.state" name="state" placeholder="e.g., Maharashtra" />
            </div>
          </div>

          <div class="form-group mt-3">
            <label class="form-label">Funding Goal Amount (INR) *</label>
            <input
              class="input font-bold"
              type="number"
              [(ngModel)]="form.goal_amount"
              name="goal_amount"
              placeholder="e.g., 500000"
              min="1000"
              required
            />
            <small class="field-hint" *ngIf="form.goal_amount">{{ formatINR(form.goal_amount) }}</small>
          </div>

          <div class="form-group mt-3">
            <label class="form-label">Target Completion Date</label>
            <input class="input" type="date" [(ngModel)]="form.deadline" name="deadline" />
          </div>

          <div class="form-group mt-3">
            <label class="form-label">Short Summary (max 200 characters) *</label>
            <textarea
              class="input"
              rows="2"
              [(ngModel)]="form.short_description"
              name="short_description"
              placeholder="Brief summary explaining who needs help and why."
              maxlength="200"
              required
            ></textarea>
            <small class="field-hint">{{ form.short_description.length }}/200 characters</small>
          </div>
        </div>

        <!-- Step 1: Story + AI Assistant -->
        <div class="wizard-panel card" *ngIf="currentStep === 1">
          <div class="panel-header">
            <h2>Medical Details & Detailed Narrative</h2>
            <p>Detailed diagnosis and specific cost breakdowns achieve higher AI Trust Scores and faster donor verification.</p>
          </div>

          <!-- Hospital Specific Fields -->
          <div *ngIf="form.category === 'MEDICAL'" class="hospital-subform">
            <div class="form-group">
              <label class="form-label">Hospital or Clinic Name</label>
              <input
                class="input"
                type="text"
                [(ngModel)]="form.hospital_name"
                name="hospital_name"
                placeholder="e.g., AIIMS New Delhi, Apollo Hospital, Tata Memorial Centre"
              />
            </div>

            <div class="form-group mt-3">
              <label class="form-label">Patient Hospital UHID / Registration ID</label>
              <input
                class="input"
                type="text"
                [(ngModel)]="form.hospital_patient_uhid"
                name="hospital_patient_uhid"
                placeholder="Unique Patient UHID issued by hospital records"
              />
            </div>

            <div class="checkbox-stack mt-3">
              <label class="custom-checkbox">
                <input type="checkbox" [(ngModel)]="form.is_80g_tax_exempt" name="is_80g" />
                <span>Issue Section 80G Tax Exemption Certificates for eligible donors</span>
              </label>

              <label class="custom-checkbox">
                <input type="checkbox" [(ngModel)]="form.direct_hospital_transfer" name="direct_hospital" />
                <span>Enable Direct Hospital Settlement (Funds route directly via NEFT/RTGS to hospital billing)</span>
              </label>
            </div>
          </div>

          <!-- Full Narrative -->
          <div class="form-group mt-4">
            <label class="form-label">Complete Fundraiser Narrative *</label>
            <textarea
              class="input story-textarea"
              rows="8"
              [(ngModel)]="form.story"
              name="story"
              (ngModelChange)="onStoryChange($event)"
              placeholder="Explain the patient's condition, diagnosis timeline, doctor's recommendations, breakdown of expenses, and family situation in detail…"
              required
            ></textarea>
          </div>

          <!-- AI Story Assistant Card -->
          <div class="ai-assistant-card">
            <div class="ai-card-top">
              <div class="ai-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="2">
                  <path d="M12 2L14.4 8.6L21 11L14.4 13.4L12 20L9.6 13.4L3 11L9.6 8.6L12 2Z"/>
                </svg>
                <span>AI Narrative Generator</span>
              </div>
              <span class="ai-badge">Instant Medical Structuring</span>
            </div>
            <p class="ai-intro">Need assistance writing? Provide quick bullet points and our AI will draft an authentic narrative.</p>

            <div class="ai-inputs-grid">
              <input
                class="input"
                type="text"
                [(ngModel)]="aiHints.condition"
                name="ai_condition"
                placeholder="Diagnosis (e.g., Acute Lymphoblastic Leukemia)"
              />
              <input
                class="input"
                type="text"
                [(ngModel)]="aiHints.treatment"
                name="ai_treatment"
                placeholder="Treatment Plan (e.g., 6 cycles of chemo + bone marrow transplant)"
              />
              <input
                class="input"
                type="text"
                [(ngModel)]="aiHints.patient"
                name="ai_patient"
                placeholder="Patient Profile (e.g., 9-year-old child from Pune)"
              />
            </div>

            <button
              type="button"
              class="btn btn-secondary ai-generate-btn mt-3"
              (click)="enhanceStory()"
              [disabled]="enhancing()"
            >
              {{ enhancing() ? 'Drafting Story with Clinical Accuracy…' : 'Generate Structured Story' }}
            </button>

            <div class="field-error mt-2" *ngIf="enhanceError()">{{ enhanceError() }}</div>
          </div>
        </div>

        <!-- Step 2: Documents -->
        <div class="wizard-panel card" *ngIf="currentStep === 2">
          <div class="panel-header">
            <h2>Supporting Documentation</h2>
            <p>Upload verification documents. Documented campaigns receive priority AI clearance.</p>
          </div>

          <div class="docs-checklist-grid">
            <div class="doc-guide-item">
              <div class="doc-icon-box">🏥</div>
              <div class="doc-meta">
                <strong>Medical Estimate & Prescription</strong>
                <p>Hospital admission slip, treating physician's cost estimate, pathology report.</p>
              </div>
            </div>
            <div class="doc-guide-item">
              <div class="doc-icon-box">🪪</div>
              <div class="doc-meta">
                <strong>Government ID Proof</strong>
                <p>Aadhaar card or PAN of patient or verified family guardian.</p>
              </div>
            </div>
            <div class="doc-guide-item">
              <div class="doc-icon-box">📸</div>
              <div class="doc-meta">
                <strong>Patient Photo / Hospital Bed Photo</strong>
                <p>Clear, unedited photograph verifying patient identity.</p>
              </div>
            </div>
          </div>

          <div class="form-group mt-4">
            <label class="form-label">Cover Image URL</label>
            <input
              class="input"
              type="url"
              [(ngModel)]="form.cover_image_url"
              name="cover_image_url"
              placeholder="https://example.com/patient-image.jpg"
            />
            <small class="field-hint">Paste direct image URL hosted on hospital or verified drive</small>
          </div>

          <div class="form-row mt-3">
            <div class="form-group">
              <label class="form-label">Organizer Full Name *</label>
              <input
                class="input"
                type="text"
                [(ngModel)]="form.organizer_name"
                name="organizer_name"
                placeholder="Your legal name"
                required
              />
            </div>
            <div class="form-group">
              <label class="form-label">Organizer Mobile Number</label>
              <input
                class="input"
                type="tel"
                [(ngModel)]="form.organizer_phone"
                name="organizer_phone"
                placeholder="+91 98765 43210"
              />
            </div>
          </div>
        </div>

        <!-- Step 3: Review + Live AI Verification -->
        <div class="wizard-panel card" *ngIf="currentStep === 3">
          <div class="panel-header">
            <h2>Review & AI Pre-Flight Audit</h2>
            <p>Our algorithms assess your fundraiser for completeness, clinical plausibility, and benchmark cost fit.</p>
          </div>

          <!-- Summary Box -->
          <div class="review-meta-box">
            <div class="meta-line"><span>Title:</span><strong>{{ form.title }}</strong></div>
            <div class="meta-line"><span>Category:</span><strong>{{ form.category }}</strong></div>
            <div class="meta-line"><span>Funding Goal:</span><strong>₹{{ formatINR(form.goal_amount) }}</strong></div>
            <div class="meta-line" *ngIf="form.hospital_name"><span>Hospital:</span><strong>{{ form.hospital_name }}</strong></div>
            <div class="meta-line" *ngIf="form.is_80g_tax_exempt"><span>80G Tax Exemption:</span><strong class="text-green">Eligible</strong></div>
          </div>

          <!-- Live AI Score Widget -->
          <div class="ai-audit-result-card" *ngIf="!verifying() && liveScore()">
            <div class="audit-card-top">
              <div>
                <span class="audit-tag">Automated Verification Assessment</span>
                <h3 class="audit-decision">{{ liveScore()?.decision }}</h3>
              </div>
              <div
                class="score-number-badge"
                [class.score-green]="(liveScore()?.overall_score || 0) >= 80"
                [class.score-amber]="(liveScore()?.overall_score || 0) >= 50 && (liveScore()?.overall_score || 0) < 80"
                [class.score-red]="(liveScore()?.overall_score || 0) < 50"
              >
                {{ liveScore()?.overall_score | number:'1.0-0' }} / 100
              </div>
            </div>

            <p class="audit-explanation">{{ liveScore()?.explanation }}</p>

            <!-- Dimension Bars -->
            <div class="dim-breakdown" *ngIf="liveScore()?.dimension_scores">
              <div class="dim-stat-row" *ngFor="let dim of getDimensions()">
                <span class="dim-name">{{ dim.label }}</span>
                <div class="dim-track">
                  <div
                    class="dim-fill"
                    [style.width.%]="dim.value"
                    [class.bar-green]="dim.value >= 70"
                    [class.bar-amber]="dim.value >= 40 && dim.value < 70"
                    [class.bar-red]="dim.value < 40"
                  ></div>
                </div>
                <span class="dim-pct">{{ dim.value | number:'1.0-0' }}%</span>
              </div>
            </div>

            <!-- Suggestions -->
            <div class="suggestions-list" *ngIf="liveScore()?.suggestions && liveScore()!.suggestions!.length > 0">
              <strong>Recommendations to Increase Trust:</strong>
              <ul>
                <li *ngFor="let s of liveScore()!.suggestions">{{ s }}</li>
              </ul>
            </div>
          </div>

          <!-- Verifying Progress -->
          <div class="verifying-state" *ngIf="verifying()">
            <div class="verifying-spinner"></div>
            <p>Running benchmark cost models & text authenticity checks…</p>
          </div>

          <button
            type="button"
            class="btn btn-outline btn-sm mt-3"
            (click)="runVerification()"
            [disabled]="verifying()"
          >
            Re-run AI Pre-Check
          </button>
        </div>

        <!-- Wizard Navigation Footer -->
        <div class="wizard-nav-footer">
          <button
            type="button"
            class="btn btn-outline"
            *ngIf="currentStep > 0"
            (click)="prevStep()"
          >
            ← Previous Step
          </button>

          <button
            type="button"
            class="btn btn-primary ml-auto"
            *ngIf="currentStep < 3"
            (click)="nextStep()"
          >
            Continue →
          </button>

          <button
            type="submit"
            class="btn btn-primary ml-auto"
            *ngIf="currentStep === 3"
            [disabled]="submitting()"
          >
            {{ submitting() ? 'Submitting Fundraiser for Audit…' : 'Publish Verified Fundraiser' }}
          </button>
        </div>

        <div class="form-error-toast mt-3" *ngIf="submitError()">{{ submitError() }}</div>
      </form>
    </div>
  `,
  styles: [`
    .create-page {
      max-width: 820px;
      padding: 48px var(--space-5) 80px;
    }

    .create-header {
      margin-bottom: 36px;
    }

    .sub-header-pill {
      font-size: 11.5px;
      font-weight: 700;
      color: var(--primary);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 6px;
      display: inline-block;
    }

    .create-header h1 {
      font-size: clamp(2rem, 3.5vw, 2.6rem);
      font-weight: 800;
      color: var(--slate-900);
      letter-spacing: -0.02em;
      margin-bottom: 8px;
    }

    .create-header p {
      font-size: 15px;
      color: var(--slate-500);
      max-width: 640px;
    }

    /* Steps Progress Bar */
    .steps-progress-bar {
      display: flex;
      margin-bottom: 32px;
      position: relative;
    }

    .step-node {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      position: relative;
      text-align: center;
    }

    .step-node::before {
      content: '';
      position: absolute;
      top: 17px;
      right: -50%;
      width: 100%;
      height: 2px;
      background: var(--slate-200);
      z-index: 0;
    }

    .step-node:last-child::before {
      display: none;
    }

    .step-node.done::before {
      background: var(--secondary);
    }

    .step-circle {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: var(--slate-100);
      border: 2px solid var(--slate-200);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      font-weight: 700;
      color: var(--slate-500);
      z-index: 1;
      margin-bottom: 6px;
      transition: all 0.2s ease;
    }

    .step-node.active .step-circle {
      background: var(--primary);
      border-color: var(--primary);
      color: #FFFFFF;
      box-shadow: 0 0 0 4px var(--primary-light);
    }

    .step-node.done .step-circle {
      background: var(--secondary);
      border-color: var(--secondary);
      color: #FFFFFF;
    }

    .step-label {
      font-size: 12.5px;
      font-weight: 600;
      color: var(--slate-500);
    }

    .step-node.active .step-label {
      color: var(--slate-900);
      font-weight: 700;
    }

    /* Wizard Panel */
    .wizard-panel {
      padding: 36px;
      border-radius: var(--radius-xl);
    }

    .panel-header {
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border-light);
    }

    .panel-header h2 {
      font-size: 20px;
      font-weight: 800;
      color: var(--slate-900);
      margin-bottom: 4px;
    }

    .panel-header p {
      font-size: 13.5px;
      color: var(--slate-500);
    }

    .form-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }

    .field-hint {
      font-size: 12px;
      color: var(--slate-400);
      margin-top: 4px;
      display: block;
    }

    .font-bold {
      font-weight: 700;
    }

    /* Hospital Subform */
    .hospital-subform {
      background: var(--slate-50);
      border: 1px solid var(--border);
      padding: 20px;
      border-radius: var(--radius-lg);
    }

    .checkbox-stack {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .custom-checkbox {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      font-size: 13px;
      color: var(--slate-700);
      cursor: pointer;
      line-height: 1.4;
    }

    .custom-checkbox input {
      margin-top: 2px;
      accent-color: var(--primary);
    }

    .story-textarea {
      font-size: 14.5px;
      line-height: 1.7;
    }

    /* AI Assistant Card */
    .ai-assistant-card {
      background: linear-gradient(135deg, #FAF5FF 0%, #FFF7ED 100%);
      border: 1px solid #E9D5FF;
      border-radius: var(--radius-lg);
      padding: 22px;
      margin-top: 24px;
    }

    .ai-card-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }

    .ai-title {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 14px;
      font-weight: 700;
      color: #6D28D9;
    }

    .ai-badge {
      font-size: 11px;
      font-weight: 700;
      background: #EDE9FE;
      color: #6D28D9;
      padding: 2px 8px;
      border-radius: var(--radius-full);
    }

    .ai-intro {
      font-size: 13px;
      color: var(--slate-600);
      margin-bottom: 14px;
    }

    .ai-inputs-grid {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .ai-generate-btn {
      background: #7C3AED;
      border-color: #7C3AED;
    }

    .ai-generate-btn:hover {
      background: #6D28D9;
      border-color: #6D28D9;
    }

    /* Docs Checklist */
    .docs-checklist-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
      margin-bottom: 20px;
    }

    .doc-guide-item {
      padding: 16px;
      background: var(--slate-50);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      display: flex;
      gap: 10px;
      align-items: flex-start;
    }

    .doc-icon-box {
      font-size: 20px;
    }

    .doc-meta strong {
      font-size: 12.5px;
      color: var(--slate-800);
      display: block;
      margin-bottom: 2px;
    }

    .doc-meta p {
      font-size: 11.5px;
      color: var(--slate-500);
      line-height: 1.4;
    }

    /* Review Meta */
    .review-meta-box {
      background: var(--slate-50);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 16px 20px;
      margin-bottom: 24px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .meta-line {
      display: flex;
      justify-content: space-between;
      font-size: 13.5px;
    }

    .meta-line span {
      color: var(--slate-500);
    }

    /* AI Audit Result Card */
    .ai-audit-result-card {
      background: var(--slate-50);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      padding: 24px;
      margin-bottom: 20px;
    }

    .audit-card-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .audit-tag {
      font-size: 11px;
      font-weight: 700;
      color: var(--slate-400);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .audit-decision {
      font-size: 18px;
      font-weight: 800;
      color: var(--slate-900);
      margin-top: 2px;
    }

    .score-number-badge {
      font-family: var(--font-heading);
      font-size: 20px;
      font-weight: 800;
      padding: 6px 14px;
      border-radius: var(--radius-full);
    }

    .score-green {
      background: var(--success-light);
      color: var(--success);
      border: 1px solid var(--success-border);
    }

    .score-amber {
      background: var(--warning-light);
      color: var(--warning);
      border: 1px solid var(--warning-border);
    }

    .score-red {
      background: var(--danger-light);
      color: var(--danger);
      border: 1px solid var(--danger-border);
    }

    .audit-explanation {
      font-size: 13.5px;
      color: var(--slate-600);
      line-height: 1.5;
      margin-bottom: 18px;
    }

    .dim-breakdown {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-bottom: 18px;
    }

    .dim-stat-row {
      display: grid;
      grid-template-columns: 120px 1fr 40px;
      gap: 12px;
      align-items: center;
      font-size: 12.5px;
    }

    .dim-track {
      height: 6px;
      background: var(--slate-200);
      border-radius: var(--radius-full);
      overflow: hidden;
    }

    .dim-fill {
      height: 100%;
      border-radius: var(--radius-full);
    }

    .bar-green { background: var(--secondary); }
    .bar-amber { background: var(--warning); }
    .bar-red { background: var(--danger); }

    .dim-pct {
      font-weight: 700;
      color: var(--slate-700);
      text-align: right;
    }

    .suggestions-list {
      background: #FFFFFF;
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 14px 18px;
      font-size: 12.5px;
      color: var(--slate-600);
    }

    .suggestions-list ul {
      margin: 6px 0 0 16px;
    }

    .verifying-state {
      text-align: center;
      padding: 32px 0;
    }

    .verifying-spinner {
      width: 36px;
      height: 36px;
      border: 3px solid var(--slate-200);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 10px;
    }

    /* Wizard Navigation */
    .wizard-nav-footer {
      display: flex;
      align-items: center;
      margin-top: 24px;
      gap: 12px;
    }

    .ml-auto {
      margin-left: auto;
    }

    .form-error-toast {
      padding: 10px 14px;
      border-radius: var(--radius-md);
      background: var(--danger-light);
      border: 1px solid var(--danger-border);
      color: var(--danger);
      font-size: 13px;
      text-align: center;
    }

    @media (max-width: 768px) {
      .docs-checklist-grid {
        grid-template-columns: 1fr;
      }
      .form-row {
        grid-template-columns: 1fr;
      }
      .wizard-panel {
        padding: 24px 20px;
      }
    }
  `]
})
export class CreateCampaignComponent implements OnInit, OnDestroy {
  private campaignService = inject(CampaignService);
  private aiService = inject(AiService);
  private router = inject(Router);
  private destroy$ = new Subject<void>();
  private storyChange$ = new Subject<string>();

  steps = ['Basics', 'Medical Details', 'Documents', 'Verification'];
  currentStep = 0;
  categories = CATEGORIES;

  form = {
    title: '', category: 'MEDICAL', city: '', state: '',
    goal_amount: 500000, deadline: '', short_description: '', story: '',
    hospital_name: '', hospital_patient_uhid: '',
    is_80g_tax_exempt: false, direct_hospital_transfer: false,
    cover_image_url: '', organizer_name: '', organizer_phone: '',
  };
  aiHints = { condition: '', treatment: '', patient: '' };

  enhancing = signal(false);
  enhanceError = signal('');
  verifying = signal(false);
  liveScore = signal<any>(null);
  submitting = signal(false);
  submitError = signal('');

  ngOnInit() {
    this.storyChange$.pipe(
      debounceTime(1500),
      takeUntil(this.destroy$)
    ).subscribe(() => {
      if (this.currentStep === 3) this.runVerification();
    });
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }

  onStoryChange(val: string) {
    this.form.story = val;
  }

  enhanceStory() {
    this.enhancing.set(true);
    this.enhanceError.set('');
    this.aiService.enhanceStory({
      title: this.form.title,
      category: this.form.category,
      goal_amount: this.form.goal_amount,
      city: this.form.city,
      state: this.form.state,
      hospital_name: this.form.hospital_name,
      story: this.aiHints.condition + ' ' + this.aiHints.treatment + ' ' + this.aiHints.patient,
    }).subscribe({
      next: (res) => {
        this.form.story = res.enhanced_story;
        this.enhancing.set(false);
      },
      error: (err) => {
        this.enhanceError.set(err?.error?.detail || 'AI unavailable. Please write your story manually.');
        this.enhancing.set(false);
      }
    });
  }

  runVerification() {
    this.verifying.set(true);
    this.aiService.preCheckVerification({
      title: this.form.title,
      category: this.form.category,
      goal_amount: this.form.goal_amount,
      story: this.form.story,
      hospital_name: this.form.hospital_name,
    }).subscribe({
      next: (res) => {
        this.liveScore.set(res);
        this.verifying.set(false);
      },
      error: () => this.verifying.set(false)
    });
  }

  getDimensions(): { label: string; value: number }[] {
    const ds = this.liveScore()?.dimension_scores;
    if (!ds) return [];
    return [
      { label: 'Specificity',    value: ds.specificity_score    || 0 },
      { label: 'Benchmark Fit',  value: ds.benchmark_score      || 0 },
      { label: 'Documentation',  value: ds.documentation_score  || 0 },
      { label: 'Urgency',        value: ds.urgency_score        || 0 },
    ];
  }

  nextStep() {
    if (this.currentStep < 3) {
      this.currentStep++;
      if (this.currentStep === 3) this.runVerification();
    }
  }

  prevStep() {
    if (this.currentStep > 0) this.currentStep--;
  }

  submitCampaign() {
    this.submitting.set(true);
    this.submitError.set('');
    this.campaignService.createCampaign({
      title: this.form.title,
      category: this.form.category,
      short_description: this.form.short_description,
      story: this.form.story,
      goal_amount: this.form.goal_amount,
      deadline: this.form.deadline || undefined,
      city: this.form.city || undefined,
      state: this.form.state || undefined,
      cover_image_url: this.form.cover_image_url || undefined,
      organizer_name: this.form.organizer_name || undefined,
      organizer_phone: this.form.organizer_phone || undefined,
      hospital_name: this.form.hospital_name || undefined,
      hospital_patient_uhid: this.form.hospital_patient_uhid || undefined,
      is_80g_tax_exempt: this.form.is_80g_tax_exempt,
      direct_hospital_transfer: this.form.direct_hospital_transfer,
    }).subscribe({
      next: (c) => {
        this.submitting.set(false);
        this.router.navigate(['/campaigns', c.id]);
      },
      error: (err) => {
        this.submitError.set(err?.error?.detail || 'Submission failed. Please try again.');
        this.submitting.set(false);
      }
    });
  }

  formatINR(amount: number): string {
    if (!amount) return '';
    if (amount >= 10_000_000) return '₹' + (amount / 10_000_000).toFixed(1) + ' Crore';
    if (amount >= 100_000)    return '₹' + (amount / 100_000).toFixed(1) + ' Lakh';
    if (amount >= 1000)       return '₹' + (amount / 1000).toFixed(1) + 'K';
    return '₹' + amount;
  }
}
