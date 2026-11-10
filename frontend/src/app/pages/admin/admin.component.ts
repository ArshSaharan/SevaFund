import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { CampaignService } from '../../services/campaign.service';
import { DonationService } from '../../services/donation.service';
import { AuthService } from '../../services/auth.service';
import { Campaign, AdminDonationItem, AdminDonationsSummary } from '../../models/campaign.model';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="admin-page container">
      <!-- Admin Top Header -->
      <div class="admin-header-strip">
        <div>
          <span class="sub-header-pill">Institutional Oversight</span>
          <h1 class="portal-heading">Trust & Safety Moderation Portal</h1>
          <p class="portal-desc">
            Auditing, decision logs, and payment reconciliation. Only verified platform administrators can authorize disbursements.
          </p>
        </div>

        <div class="admin-user-pill" *ngIf="authService.isAdmin()">
          <div class="admin-avatar">A</div>
          <div class="admin-meta">
            <strong>{{ authService.currentUser()?.full_name }}</strong>
            <span class="admin-role">Platform Moderator</span>
          </div>
          <button class="btn btn-ghost btn-sm" (click)="authService.logout()">Sign Out</button>
        </div>
      </div>

      <!-- Auth Required Gate -->
      <div class="admin-gate-card card" *ngIf="!authService.isAdmin()">
        <div class="gate-icon-circle">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
          </svg>
        </div>
        <h2>Moderator Credentials Required</h2>
        <p class="gate-desc">
          Under platform security policy, campaign verification queues and donation ledgers are restricted to authorized administrators.
        </p>

        <form (ngSubmit)="loginAsAdmin()" class="gate-form">
          <div class="form-group">
            <label class="form-label">Moderator Email</label>
            <input
              type="email"
              class="input"
              [(ngModel)]="loginEmail"
              name="email"
              required
              placeholder="admin@crowdfund-trust.in"
            />
          </div>
          <div class="form-group mt-3">
            <label class="form-label">Password</label>
            <input
              type="password"
              class="input"
              [(ngModel)]="loginPassword"
              name="password"
              required
              placeholder="••••••••"
            />
          </div>
          <button type="submit" class="btn btn-primary btn-full mt-4" [disabled]="loginLoading()">
            {{ loginLoading() ? 'Authenticating…' : 'Sign In to Moderation Portal' }}
          </button>
          <div class="error-banner mt-3" *ngIf="loginError()">{{ loginError() }}</div>
        </form>

        <div class="demo-access-box mt-4">
          <span>Demo / Quick Access:</span>
          <button class="btn btn-outline btn-sm quick-access-btn" (click)="quickLoginAdmin()">
            Fill & Sign In as Lead Moderator
          </button>
        </div>
      </div>

      <!-- Admin Portal Workspace -->
      <div *ngIf="authService.isAdmin()" class="portal-workspace">
        <!-- Moderation Stats Bar -->
        <div class="stats-overview-grid">
          <div class="metric-card card">
            <span class="m-val warning">{{ pendingCampaigns.length }}</span>
            <span class="m-lbl">Pending Audit</span>
          </div>
          <div class="metric-card card">
            <span class="m-val danger">{{ flaggedCampaigns.length }}</span>
            <span class="m-lbl">Flagged by AI</span>
          </div>
          <div class="metric-card card">
            <span class="m-val">{{ allCampaigns().length }}</span>
            <span class="m-lbl">Total in Queue</span>
          </div>
          <div class="metric-card card clickable-stat" (click)="setTab('donations')">
            <span class="m-val success">₹{{ formatINR(donationSummary()?.total_amount_raised || 0) }}</span>
            <span class="m-lbl">{{ donationSummary()?.total_donations_count || 0 }} Ledger Records</span>
          </div>
          <div class="metric-card card clickable-stat" (click)="activeTab = 'audit_logs'">
            <span class="m-val">📜</span>
            <span class="m-lbl">Immutable Audit Log</span>
          </div>
        </div>

        <!-- Filter Tabs -->
        <div class="tabs-toolbar">
          <button
            class="filter-pill"
            *ngFor="let tab of tabs"
            [class.active]="activeTab === tab.value"
            (click)="setTab(tab.value)"
          >
            {{ tab.label }}
          </button>
        </div>

        <!-- Audit Logs View -->
        <div class="audit-trail-card card" *ngIf="activeTab === 'audit_logs'">
          <div class="card-header-row">
            <div>
              <h3>Immutable Decision Audit Log</h3>
              <p class="card-subhead">Every moderator decision is permanently timestamped for institutional compliance.</p>
            </div>
          </div>

          <div class="loading-state" *ngIf="loadingAuditLogs()">
            <div class="loading-spinner"></div>
            <p>Fetching ledger records…</p>
          </div>

          <div class="table-responsive" *ngIf="!loadingAuditLogs() && auditLogs().length > 0">
            <table class="portal-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>Campaign ID</th>
                  <th>State Shift</th>
                  <th>Moderator Note</th>
                  <th>IP Address</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let log of auditLogs()">
                  <td>{{ log.created_at | date:'medium' }}</td>
                  <td>
                    <span class="status-chip chip-info">{{ log.action }}</span>
                  </td>
                  <td>#{{ log.target_id }}</td>
                  <td>{{ log.previous_status }} → <strong>{{ log.new_status }}</strong></td>
                  <td>{{ log.reason || '-' }}</td>
                  <td><code>{{ log.ip_address || '127.0.0.1' }}</code></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="empty-state" *ngIf="!loadingAuditLogs() && auditLogs().length === 0">
            <p>No audit trail entries recorded yet.</p>
          </div>
        </div>

        <!-- Donations & Payment Ledger View -->
        <div class="donations-ledger-card card" *ngIf="activeTab === 'donations'">
          <div class="ledger-header-row">
            <div>
              <h3>Direct Fund Settlement Ledger</h3>
              <p class="card-subhead">Real-time ledger of all donations, gateway reference IDs, and direct hospital recipients.</p>
            </div>

            <div class="ledger-stats-cluster" *ngIf="donationSummary() as sum">
              <div class="cluster-stat">
                <span>Collected</span>
                <strong>₹{{ sum.total_amount_raised | number:'1.2-2' }}</strong>
              </div>
              <div class="cluster-stat highlight">
                <span>Passed to Beneficiary</span>
                <strong>₹{{ sum.total_net_amount | number:'1.2-2' }}</strong>
              </div>
              <div class="cluster-stat">
                <span>Platform Markup</span>
                <strong class="text-green">₹0.00 (0%)</strong>
              </div>
            </div>
          </div>

          <!-- Search & Filter Controls -->
          <div class="ledger-filter-controls">
            <div class="search-wrap">
              <input
                type="text"
                class="input search-input"
                placeholder="Search donor name, phone, PAN, Tx Ref, or patient…"
                [(ngModel)]="donationSearch"
                (input)="onSearchDonations()"
              />
            </div>
            <select class="input campaign-select" [(ngModel)]="selectedCampaignFilter" (change)="loadAdminDonations()">
              <option [value]="0">All Fundraisers</option>
              <option *ngFor="let camp of allCampaigns()" [value]="camp.id">
                #{{ camp.id }} - {{ camp.title | slice:0:35 }}…
              </option>
            </select>
          </div>

          <div class="loading-state" *ngIf="loadingDonations()">
            <div class="loading-spinner"></div>
            <p>Loading transaction ledger…</p>
          </div>

          <div class="table-responsive" *ngIf="!loadingDonations() && adminDonations().length > 0">
            <table class="portal-table">
              <thead>
                <tr>
                  <th>Date & Reference</th>
                  <th>Patient / Beneficiary</th>
                  <th>Donor Details</th>
                  <th>Amount</th>
                  <th>Gateway Status</th>
                  <th>80G Receipt</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let d of adminDonations()">
                  <td>
                    <div class="date-txt">{{ d.created_at | date:'medium' }}</div>
                    <code class="ref-code">{{ d.transaction_ref }}</code>
                  </td>
                  <td>
                    <div class="patient-cell">
                      <strong>{{ d.beneficiary_name || 'Patient' }}</strong>
                      <span class="hospital-sub" *ngIf="d.hospital_name">{{ d.hospital_name }}</span>
                      <a class="camp-link" [routerLink]="['/campaigns', d.campaign_id]">
                        #{{ d.campaign_id }}: {{ d.campaign_title | slice:0:30 }}…
                      </a>
                    </div>
                  </td>
                  <td>
                    <div class="donor-cell">
                      <div class="donor-title">
                        <strong>{{ d.donor_name }}</strong>
                        <span class="anon-pill" *ngIf="d.is_anonymous">Anonymous</span>
                      </div>
                      <span class="contact-txt" *ngIf="d.donor_email">{{ d.donor_email }}</span>
                      <span class="contact-txt" *ngIf="d.donor_phone">📱 {{ d.donor_phone }}</span>
                      <span class="pan-txt" *ngIf="d.donor_pan">PAN: {{ d.donor_pan }}</span>
                    </div>
                  </td>
                  <td>
                    <div class="amount-cell">
                      <span class="amount-val">₹{{ d.amount | number:'1.2-2' }}</span>
                      <span class="net-val">Net: ₹{{ d.net_amount | number:'1.2-2' }}</span>
                    </div>
                  </td>
                  <td>
                    <span class="status-chip chip-success">{{ d.payment_status }}</span>
                    <span class="method-sub">{{ d.payment_method }}</span>
                  </td>
                  <td>
                    <span class="tax-80g-chip" *ngIf="d.tax_exemption_80g_number">
                      {{ d.tax_exemption_80g_number }}
                    </span>
                    <span *ngIf="!d.tax_exemption_80g_number" class="text-muted">-</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="empty-state" *ngIf="!loadingDonations() && adminDonations().length === 0">
            <p>No transaction records match your filters.</p>
          </div>
        </div>

        <!-- Campaign Moderation Queue View -->
        <div *ngIf="activeTab !== 'audit_logs' && activeTab !== 'donations'">
          <div class="loading-state" *ngIf="loading()">
            <div class="loading-spinner"></div>
            <p>Loading moderation queue…</p>
          </div>

          <div class="empty-state card" *ngIf="!loading() && filteredCampaigns().length === 0">
            <div class="empty-icon-wrap">✓</div>
            <h3>Queue Cleared</h3>
            <p>All fundraiser applications in this category have been audited.</p>
          </div>

          <!-- Queue List -->
          <div class="queue-stack" *ngIf="!loading()">
            <div class="queue-card card" *ngFor="let c of filteredCampaigns()">
              <div class="queue-card-top">
                <div class="queue-primary-info">
                  <div class="queue-headline-row">
                    <h3>{{ c.title }}</h3>
                    <span class="status-chip" [ngClass]="'chip-' + (c.status || '').toLowerCase()">
                      {{ c.status }}
                    </span>
                  </div>

                  <div class="queue-meta-row">
                    <span>Category: <strong>{{ c.category }}</strong></span>
                    <span>Location: <strong>{{ c.city }}, {{ c.state }}</strong></span>
                    <span *ngIf="c.hospital_name">Hospital: <strong>{{ c.hospital_name }}</strong></span>
                    <span>Goal: <strong>₹{{ formatINR(c.goal_amount) }}</strong></span>
                  </div>

                  <p class="queue-excerpt">{{ c.short_description || c.subtitle || c.story }}</p>
                </div>

                <!-- AI Score Dial -->
                <div
                  class="score-ring"
                  [class.ring-green]="((c.ai_trust_score ?? c.authenticity_score) || 0) >= 80"
                  [class.ring-amber]="((c.ai_trust_score ?? c.authenticity_score) || 0) >= 50 && ((c.ai_trust_score ?? c.authenticity_score) || 0) < 80"
                  [class.ring-red]="((c.ai_trust_score ?? c.authenticity_score) || 0) < 50"
                >
                  <span class="ring-score">{{ (c.ai_trust_score ?? c.authenticity_score) !== undefined ? (c.ai_trust_score ?? c.authenticity_score) : '?' }}</span>
                  <span class="ring-lbl">AI Score</span>
                </div>
              </div>

              <!-- AI Dimension Scores Breakdown -->
              <div class="ai-dims-bar" *ngIf="c.ai_dimension_scores">
                <div class="dim-pill-item" *ngFor="let dim of getDimensions(c)">
                  <span>{{ dim.label }}: <strong>{{ dim.value | number:'1.0-0' }}%</strong></span>
                </div>
              </div>

              <!-- Red Flags Alert -->
              <div class="red-flags-alert" *ngIf="c.ai_red_flags && c.ai_red_flags.length > 0">
                <div class="flag-line" *ngFor="let f of c.ai_red_flags">
                  ⚠️ {{ f }}
                </div>
              </div>

              <!-- Moderation Decision Action Bar -->
              <div class="decision-action-bar">
                <input
                  class="input decision-input"
                  [(ngModel)]="notes[c.id]"
                  placeholder="Mandatory justification note recorded in immutable audit log…"
                />

                <div class="btn-group">
                  <a [routerLink]="['/campaigns', c.id]" class="btn btn-outline btn-sm">Inspect Full File</a>

                  <button
                    class="btn btn-sm btn-approve"
                    (click)="decide(c, 'APPROVE')"
                    [disabled]="actionLoading()[c.id]"
                  >
                    Accept & Activate
                  </button>

                  <button
                    class="btn btn-sm btn-info"
                    (click)="decide(c, 'REQUEST_MORE_INFO')"
                    [disabled]="actionLoading()[c.id]"
                  >
                    Request Info
                  </button>

                  <button
                    class="btn btn-sm btn-reject"
                    (click)="decide(c, 'REJECT')"
                    [disabled]="actionLoading()[c.id]"
                  >
                    Reject Demand
                  </button>
                </div>
              </div>

              <div class="decision-feedback mt-2" *ngIf="decisions()[c.id]">
                {{ decisions()[c.id] }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .admin-page {
      padding: 40px var(--space-5) 80px;
    }

    .admin-header-strip {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 32px;
      flex-wrap: wrap;
      gap: 16px;
    }

    .portal-heading {
      font-size: clamp(1.8rem, 3vw, 2.4rem);
      font-weight: 600;
      color: var(--slate-900);
      letter-spacing: -0.02em;
      margin-bottom: 4px;
    }

    .portal-desc {
      font-size: 14px;
      color: var(--slate-500);
      max-width: 640px;
    }

    .sub-header-pill {
      font-size: 11.5px;
      font-weight: 700;
      color: var(--violet);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 4px;
      display: inline-block;
    }

    .admin-user-pill {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 6px 14px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-full);
      box-shadow: var(--shadow-xs);
    }

    .admin-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: var(--violet);
      color: var(--on-violet);
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
    }

    .admin-meta {
      display: flex;
      flex-direction: column;
      line-height: 1.2;
    }

    .admin-role {
      font-size: 11px;
      color: var(--violet);
      font-weight: 600;
    }

    /* Gate Card */
    .admin-gate-card {
      max-width: 480px;
      margin: 40px auto;
      padding: 36px 32px;
      text-align: center;
      border-radius: var(--radius-xl);
    }

    .gate-icon-circle {
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: var(--danger-light);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 16px;
    }

    .admin-gate-card h2 {
      font-size: 20px;
      font-weight: 600;
      color: var(--slate-900);
      margin-bottom: 6px;
    }

    .gate-desc {
      font-size: 13.5px;
      color: var(--slate-500);
      margin-bottom: 24px;
      line-height: 1.5;
    }

    .gate-form {
      text-align: left;
    }

    .demo-access-box {
      border-top: 1px dashed var(--border);
      padding-top: 18px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      font-size: 12.5px;
      color: var(--slate-500);
    }

    /* Stats Grid */
    .stats-overview-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 28px;
    }

    .metric-card {
      padding: 18px 20px;
      border-radius: var(--radius-lg);
      display: flex;
      flex-direction: column;
    }

    .clickable-stat {
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .clickable-stat:hover {
      border-color: var(--primary);
      transform: translateY(-2px);
    }

    .m-val {
      font-family: var(--font-heading);
      font-size: 24px;
      font-weight: 600;
      color: var(--slate-900);
      line-height: 1.1;
    }

    .m-val.warning { color: var(--warning); }
    .m-val.danger { color: var(--danger); }
    .m-val.success { color: var(--success); }

    .m-lbl {
      font-size: 12px;
      font-weight: 600;
      color: var(--slate-500);
      margin-top: 4px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    /* Tabs Toolbar */
    .tabs-toolbar {
      display: flex;
      gap: 8px;
      margin-bottom: 24px;
      overflow-x: auto;
      padding-bottom: 4px;
    }

    .filter-pill {
      padding: 8px 16px;
      border-radius: var(--radius-full);
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--slate-600);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
      white-space: nowrap;
    }

    .filter-pill:hover {
      background: var(--slate-100);
    }

    .filter-pill.active {
      background: var(--primary);
      border-color: var(--primary);
      color: var(--on-primary);
      box-shadow: 0 2px 8px var(--accent-glow);
    }

    /* Table Styles */
    .table-responsive {
      width: 100%;
      overflow-x: auto;
    }

    .portal-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13.5px;
      text-align: left;
    }

    .portal-table th {
      padding: 12px 14px;
      background: var(--slate-50);
      border-bottom: 1px solid var(--border);
      font-weight: 700;
      color: var(--slate-700);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .portal-table td {
      padding: 14px;
      border-bottom: 1px solid var(--border-light);
      vertical-align: top;
    }

    .status-chip {
      display: inline-block;
      padding: 2px 8px;
      border-radius: var(--radius-full);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }

    .chip-success, .status-active, .status-approved {
      background: var(--success-light);
      color: var(--success);
    }

    .chip-pending, .status-pending, .status-pending_verification {
      background: var(--warning-light);
      color: var(--warning);
    }

    .chip-danger, .status-flagged, .status-rejected {
      background: var(--danger-light);
      color: var(--danger);
    }

    .chip-info {
      background: var(--info-light);
      color: var(--info);
    }

    .card-header-row {
      padding: 20px 24px;
      border-bottom: 1px solid var(--border-light);
    }

    .card-subhead {
      font-size: 13px;
      color: var(--slate-500);
      margin-top: 2px;
    }

    /* Queue Card */
    .queue-stack {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .queue-card {
      padding: 24px;
      border-radius: var(--radius-xl);
    }

    .queue-card-top {
      display: flex;
      justify-content: space-between;
      gap: 20px;
    }

    .queue-primary-info {
      flex: 1;
    }

    .queue-headline-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }

    .queue-headline-row h3 {
      font-size: 18px;
      font-weight: 600;
      color: var(--slate-900);
    }

    .queue-meta-row {
      display: flex;
      gap: 16px;
      font-size: 13px;
      color: var(--slate-500);
      margin-bottom: 10px;
      flex-wrap: wrap;
    }

    .queue-excerpt {
      font-size: 14px;
      color: var(--slate-600);
      line-height: 1.5;
    }

    .score-ring {
      width: 76px;
      height: 76px;
      border-radius: 50%;
      border: 4px solid var(--slate-200);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .ring-green { border-color: var(--secondary); color: var(--secondary); }
    .ring-amber { border-color: var(--warning); color: var(--warning); }
    .ring-red   { border-color: var(--danger); color: var(--danger); }

    .ring-score {
      font-family: var(--font-heading);
      font-size: 20px;
      font-weight: 600;
      line-height: 1;
    }

    .ring-lbl {
      font-size: 9.5px;
      font-weight: 700;
      text-transform: uppercase;
    }

    .ai-dims-bar {
      display: flex;
      gap: 12px;
      background: var(--slate-50);
      padding: 10px 14px;
      border-radius: var(--radius-md);
      margin-top: 14px;
      flex-wrap: wrap;
      font-size: 12px;
    }

    .red-flags-alert {
      background: var(--warning-light);
      border: 1px solid var(--warning-border);
      border-radius: var(--radius-md);
      padding: 10px 14px;
      margin-top: 14px;
      font-size: 12.5px;
      color: #92400E;
    }

    .decision-action-bar {
      display: flex;
      gap: 12px;
      margin-top: 18px;
      align-items: center;
      flex-wrap: wrap;
    }

    .decision-input {
      flex: 1;
      min-width: 260px;
      font-size: 13px;
      height: 38px;
    }

    .btn-group {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .btn-approve {
      background: var(--secondary);
      color: var(--on-secondary);
      border: none;
    }

    .btn-approve:hover {
      background: var(--secondary-hover);
    }

    .btn-info {
      background: var(--violet);
      color: var(--on-violet);
      border: none;
    }

    .btn-info:hover {
      background: var(--violet-hover);
    }

    .btn-reject {
      background: #DC2626;
      color: #FFFFFF;
      border: none;
    }

    .btn-reject:hover {
      background: #B91C1C;
    }

    .decision-feedback {
      font-size: 13px;
      font-weight: 600;
      color: var(--secondary);
    }

    /* Ledger Summary Cluster */
    .donations-ledger-card {
      padding: 24px;
    }

    .ledger-header-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;
      flex-wrap: wrap;
      gap: 16px;
    }

    .ledger-stats-cluster {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }

    .cluster-stat {
      background: var(--slate-50);
      border: 1px solid var(--border);
      padding: 8px 14px;
      border-radius: var(--radius-md);
      display: flex;
      flex-direction: column;
      font-size: 11px;
      color: var(--slate-500);
    }

    .cluster-stat strong {
      font-size: 14px;
      color: var(--slate-900);
      margin-top: 2px;
    }

    .cluster-stat.highlight {
      background: var(--success-light);
      border-color: var(--success-border);
      color: var(--success);
    }

    .cluster-stat.highlight strong {
      color: var(--success);
    }

    .ledger-filter-controls {
      display: flex;
      gap: 12px;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }

    .campaign-select {
      max-width: 280px;
      height: 40px;
      font-size: 13px;
    }

    .date-txt { font-weight: 600; color: var(--slate-700); font-size: 12px; }
    .ref-code { font-size: 11px; background: var(--slate-100); padding: 2px 4px; border-radius: 4px; }
    .patient-cell { display: flex; flex-direction: column; font-size: 13px; }
    .hospital-sub { font-size: 11.5px; color: var(--slate-500); }
    .camp-link { font-size: 11.5px; color: var(--primary); text-decoration: underline; }
    .donor-cell { display: flex; flex-direction: column; font-size: 13px; }
    .donor-title { display: flex; align-items: center; gap: 6px; }
    .anon-pill { font-size: 10px; background: var(--warning-light); color: var(--warning); padding: 1px 4px; border-radius: 4px; font-weight: 700; }
    .contact-txt { font-size: 11.5px; color: var(--slate-500); }
    .pan-txt { font-size: 11px; font-weight: 700; color: var(--info); }
    .amount-cell { display: flex; flex-direction: column; }
    .amount-val { font-family: var(--font-heading); font-size: 15px; font-weight: 600; color: var(--slate-900); }
    .net-val { font-size: 11.5px; color: var(--success); font-weight: 600; }
    .tax-80g-chip { font-size: 11px; font-weight: 700; background: var(--violet-soft); color: var(--violet); padding: 2px 6px; border-radius: 4px; }

    .loading-state, .empty-state {
      text-align: center;
      padding: 48px 20px;
    }

    .loading-spinner {
      width: 36px;
      height: 36px;
      border: 3px solid var(--slate-200);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 12px;
    }
  `]
})
export class AdminComponent implements OnInit {
  private campaignService = inject(CampaignService);
  private donationService = inject(DonationService);
  private http = inject(HttpClient);
  public authService = inject(AuthService);

  allCampaigns = signal<Campaign[]>([]);
  loading = signal(false);
  actionLoading = signal<Record<number, boolean>>({});
  decisions = signal<Record<number, string>>({});
  notes: Record<number, string> = {};

  loginEmail = 'admin@crowdfund-trust.in';
  loginPassword = 'admin123';
  loginLoading = signal(false);
  loginError = signal('');

  activeTab = 'all';
  tabs = [
    { label: 'All Fundraisers', value: 'all' },
    { label: 'Pending Review', value: 'PENDING_VERIFICATION' },
    { label: 'Flagged by AI', value: 'FLAGGED' },
    { label: 'Accepted (Active)', value: 'ACTIVE' },
    { label: 'Rejected', value: 'REJECTED' },
    { label: 'Donations Ledger', value: 'donations' },
    { label: 'Audit Trail', value: 'audit_logs' }
  ];

  auditLogs = signal<any[]>([]);
  loadingAuditLogs = signal(false);

  adminDonations = signal<AdminDonationItem[]>([]);
  donationSummary = signal<AdminDonationsSummary | null>(null);
  loadingDonations = signal(false);
  donationSearch = '';
  selectedCampaignFilter = 0;

  get pendingCampaigns() {
    return this.allCampaigns().filter(c => c.status === 'PENDING' || c.status === 'PENDING_VERIFICATION');
  }
  get flaggedCampaigns() {
    return this.allCampaigns().filter(c => c.status === 'FLAGGED');
  }

  filteredCampaigns = signal<Campaign[]>([]);

  ngOnInit() {
    if (this.authService.isAdmin()) {
      this.loadAll();
    }
  }

  loginAsAdmin() {
    this.loginLoading.set(true);
    this.loginError.set('');
    this.authService.login(this.loginEmail, this.loginPassword).subscribe({
      next: () => {
        this.loginLoading.set(false);
        this.loadAll();
      },
      error: (err) => {
        this.loginLoading.set(false);
        this.loginError.set(err?.error?.detail || 'Invalid admin credentials');
      }
    });
  }

  quickLoginAdmin() {
    this.loginEmail = 'admin@crowdfund-trust.in';
    this.loginPassword = 'admin123';
    this.loginAsAdmin();
  }

  setTab(tabValue: string) {
    this.activeTab = tabValue;
    if (tabValue === 'audit_logs') {
      this.loadAuditLogs();
    } else if (tabValue === 'donations') {
      this.loadAdminDonations();
    } else {
      this.updateFilter();
    }
  }

  loadAdminDonations() {
    this.loadingDonations.set(true);
    this.donationService.getAdminDonations({
      campaign_id: this.selectedCampaignFilter > 0 ? this.selectedCampaignFilter : undefined,
      search: this.donationSearch.trim() || undefined
    }).subscribe({
      next: (res) => {
        this.adminDonations.set(res.items || []);
        this.donationSummary.set(res.summary);
        this.loadingDonations.set(false);
      },
      error: () => this.loadingDonations.set(false)
    });
  }

  onSearchDonations() {
    this.loadAdminDonations();
  }

  loadAuditLogs() {
    this.loadingAuditLogs.set(true);
    this.http.get<any[]>('http://localhost:8000/api/admin/audit-logs').subscribe({
      next: (res) => {
        this.auditLogs.set(res || []);
        this.loadingAuditLogs.set(false);
      },
      error: () => this.loadingAuditLogs.set(false)
    });
  }

  loadAll() {
    this.loading.set(true);
    this.loadAdminDonations();
    this.campaignService.getAdminQueue().subscribe({
      next: (res) => {
        const list: Campaign[] = Array.isArray(res) ? res : (res.campaigns || res.items || []);
        const sorted = [...list].sort((a: Campaign, b: Campaign) =>
          ((a.ai_trust_score ?? a.authenticity_score ?? 0) - (b.ai_trust_score ?? b.authenticity_score ?? 0))
        );
        this.allCampaigns.set(sorted);
        this.updateFilter();
        this.loading.set(false);
      },
      error: (err) => {
        if (err?.status === 401 || err?.status === 403) {
          this.authService.logout();
        }
        this.loading.set(false);
      }
    });
  }

  updateFilter() {
    if (this.activeTab === 'all') {
      this.filteredCampaigns.set(this.allCampaigns());
    } else if (this.activeTab === 'PENDING_VERIFICATION') {
      this.filteredCampaigns.set(this.allCampaigns().filter(c => c.status === 'PENDING' || c.status === 'PENDING_VERIFICATION'));
    } else {
      this.filteredCampaigns.set(this.allCampaigns().filter(c => c.status === this.activeTab));
    }
  }

  decide(campaign: Campaign, decision: string) {
    this.actionLoading.update(v => ({ ...v, [campaign.id]: true }));
    const noteText = this.notes[campaign.id] || `Admin decision: ${decision}`;

    this.campaignService.adminDecision(campaign.id, decision, noteText).subscribe({
      next: () => {
        const actionLabel = decision === 'APPROVE' ? 'ACCEPTED (ACTIVE)' : decision;
        this.decisions.update(v => ({
          ...v,
          [campaign.id]: `✓ Demand ${actionLabel} by Moderator`
        }));
        this.actionLoading.update(v => ({ ...v, [campaign.id]: false }));
        setTimeout(() => this.loadAll(), 1200);
      },
      error: (err) => {
        this.actionLoading.update(v => ({ ...v, [campaign.id]: false }));
        alert(err?.error?.detail || 'Failed to submit decision.');
      }
    });
  }

  getDimensions(c: Campaign): { label: string; value: number }[] {
    const ds = c.ai_dimension_scores;
    if (!ds) return [];
    return [
      { label: 'Specificity',   value: ds.specificity_score   || 0 },
      { label: 'Benchmark Fit', value: ds.benchmark_score     || 0 },
      { label: 'Documentation', value: ds.documentation_score || 0 },
      { label: 'Urgency',       value: ds.urgency_score       || 0 },
    ];
  }

  formatINR(amount: number): string {
    if (!amount) return '0';
    if (amount >= 10_000_000) return (amount / 10_000_000).toFixed(1) + 'Cr';
    if (amount >= 100_000)    return (amount / 100_000).toFixed(1) + 'L';
    if (amount >= 1000)       return (amount / 1000).toFixed(1) + 'K';
    return amount.toString();
  }
}
