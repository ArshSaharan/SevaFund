import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-footer',
  standalone: true,
  imports: [RouterLink],
  template: `
    <footer class="footer">
      <!-- Trust Banner Strip -->
      <div class="footer-trust-strip">
        <div class="container trust-strip-inner">
          <div class="trust-pill">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            <span>AI Cost Audited</span>
          </div>
          <div class="trust-divider"></div>
          <div class="trust-pill">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="5" width="20" height="14" rx="2"></rect>
              <line x1="2" y1="10" x2="22" y2="10"></line>
            </svg>
            <span>0% Platform Fee</span>
          </div>
          <div class="trust-divider"></div>
          <div class="trust-pill">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <span>Section 80G Tax Exemption</span>
          </div>
          <div class="trust-divider"></div>
          <div class="trust-pill">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              <polyline points="9 22 9 12 15 12 15 22"></polyline>
            </svg>
            <span>Direct Hospital NEFT</span>
          </div>
        </div>
      </div>

      <!-- Main Directory Columns -->
      <div class="container footer-main">
        <div class="footer-grid">
          <!-- Col 1: Brand Info -->
          <div class="footer-col brand-col">
            <div class="footer-brand">
              <div class="brand-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2L3 7V12C3 17.5 6.8 21.7 12 23C17.2 21.7 21 17.5 21 12V7L12 2Z" fill="#FF6B00" fill-opacity="0.2" stroke="#FF6B00" stroke-width="2"/>
                  <path d="M9 12L11 14L15 10" stroke="#00A86B" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <span class="brand-name">SevaFund<span class="brand-highlight">India</span></span>
            </div>
            <p class="brand-desc">
              India's first AI-audited medical and emergency crowdfunding network.
              Every rupee is tracked with institutional verification, zero platform markup, and direct hospital settlements.
            </p>
            <div class="national-tag">
              <span class="in-flag">🇮🇳</span>
              <span>Proudly built for Indian healthcare accessibility</span>
            </div>
          </div>

          <!-- Col 2: Supported Causes -->
          <div class="footer-col">
            <h4 class="col-title">Supported Causes</h4>
            <ul class="col-links">
              <li><a routerLink="/" [queryParams]="{category: 'MEDICAL'}">Cancer & Chemotherapy</a></li>
              <li><a routerLink="/" [queryParams]="{category: 'MEDICAL'}">Pediatric Heart Surgeries</a></li>
              <li><a routerLink="/" [queryParams]="{category: 'MEDICAL'}">Organ Transplants (Liver/Kidney)</a></li>
              <li><a routerLink="/" [queryParams]="{category: 'EMERGENCY'}">Accident & ICU Emergency</a></li>
              <li><a routerLink="/" [queryParams]="{category: 'EDUCATION'}">Higher Education Grants</a></li>
              <li><a routerLink="/" [queryParams]="{category: 'ANIMALS'}">Animal Rescue & Care</a></li>
            </ul>
          </div>

          <!-- Col 3: Trust & Verification -->
          <div class="footer-col">
            <h4 class="col-title">Trust & Safety</h4>
            <ul class="col-links">
              <li><span class="static-link">AI Cost Benchmark Audits</span></li>
              <li><span class="static-link">Hospital UHID Cross-Verification</span></li>
              <li><span class="static-link">Direct Vendor / Hospital Payout</span></li>
              <li><span class="static-link">Section 80G Tax Exemption</span></li>
              <li><span class="static-link">256-bit Bank-Grade Encryption</span></li>
              <li><a routerLink="/admin">Moderator Portal</a></li>
            </ul>
          </div>

          <!-- Col 4: Payment Partners -->
          <div class="footer-col">
            <h4 class="col-title">Payment Networks</h4>
            <p class="payments-desc">
              Accepting zero-surcharge contributions via instant UPI, RuPay, and leading Indian banks.
            </p>
            <div class="payment-badges-row">
              <span class="pay-chip">UPI</span>
              <span class="pay-chip">GPay</span>
              <span class="pay-chip">PhonePe</span>
              <span class="pay-chip">Paytm</span>
              <span class="pay-chip">RuPay</span>
              <span class="pay-chip">Netbanking</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Bottom Bar -->
      <div class="footer-bottom">
        <div class="container bottom-inner">
          <p class="copyright">
            © 2026 SevaFund India Technologies Private Limited. All rights reserved.
          </p>
          <div class="bottom-links">
            <span class="bottom-item">Terms of Service</span>
            <span class="dot-sep">•</span>
            <span class="bottom-item">Privacy Policy</span>
            <span class="dot-sep">•</span>
            <span class="bottom-item">AML / KYC Policy</span>
            <span class="dot-sep">•</span>
            <span class="bottom-item">80G Compliance</span>
          </div>
        </div>
      </div>
    </footer>
  `,
  styles: [`
    .footer {
      background: var(--slate-900);
      color: var(--slate-300);
      margin-top: 80px;
      border-top: 1px solid var(--slate-800);
    }

    /* Trust Strip */
    .footer-trust-strip {
      background: var(--slate-950);
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
      padding: 16px 0;
    }

    .trust-strip-inner {
      display: flex;
      align-items: center;
      justify-content: space-around;
      flex-wrap: wrap;
      gap: 16px;
    }

    .trust-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      font-weight: 600;
      color: var(--slate-300);
    }

    .trust-pill svg {
      color: var(--secondary);
    }

    .trust-divider {
      width: 1px;
      height: 18px;
      background: rgba(255, 255, 255, 0.1);
    }

    /* Main Footer */
    .footer-main {
      padding: 60px 0 50px;
    }

    .footer-grid {
      display: grid;
      grid-template-columns: 1.5fr 1fr 1fr 1fr;
      gap: 40px;
    }

    .brand-col {
      padding-right: 20px;
    }

    .footer-brand {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 16px;
    }

    .brand-icon {
      width: 36px;
      height: 36px;
      border-radius: var(--radius-md);
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .brand-name {
      font-family: var(--font-heading);
      font-size: 20px;
      font-weight: 800;
      color: #FFFFFF;
      letter-spacing: -0.02em;
    }

    .brand-highlight {
      color: var(--primary);
    }

    .brand-desc {
      font-size: 13.5px;
      color: var(--slate-400);
      line-height: 1.6;
      margin-bottom: 20px;
    }

    .national-tag {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: var(--radius-full);
      font-size: 12px;
      color: var(--slate-300);
      font-weight: 500;
    }

    .in-flag {
      font-size: 14px;
    }

    /* Column Styles */
    .col-title {
      font-size: 14px;
      font-weight: 700;
      color: #FFFFFF;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 18px;
    }

    .col-links {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .col-links a,
    .static-link {
      font-size: 13.5px;
      color: var(--slate-400);
      transition: color 0.15s ease;
      cursor: pointer;
    }

    .col-links a:hover {
      color: var(--primary);
    }

    .payments-desc {
      font-size: 13px;
      color: var(--slate-400);
      line-height: 1.5;
      margin-bottom: 14px;
    }

    .payment-badges-row {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }

    .pay-chip {
      display: inline-block;
      padding: 4px 8px;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: var(--radius-sm);
      font-size: 11px;
      font-weight: 600;
      color: var(--slate-300);
    }

    /* Bottom Bar */
    .footer-bottom {
      border-top: 1px solid rgba(255, 255, 255, 0.06);
      padding: 24px 0;
      font-size: 12.5px;
      color: var(--slate-500);
    }

    .bottom-inner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 16px;
    }

    .bottom-links {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .bottom-item {
      cursor: pointer;
      transition: color 0.15s ease;
    }

    .bottom-item:hover {
      color: var(--slate-300);
    }

    .dot-sep {
      color: var(--slate-700);
    }

    @media (max-width: 992px) {
      .footer-grid {
        grid-template-columns: 1fr 1fr;
        gap: 32px;
      }
      .brand-col {
        grid-column: span 2;
        padding-right: 0;
      }
      .trust-divider {
        display: none;
      }
    }

    @media (max-width: 640px) {
      .footer-grid {
        grid-template-columns: 1fr;
      }
      .brand-col {
        grid-column: span 1;
      }
      .bottom-inner {
        flex-direction: column;
        text-align: center;
      }
    }
  `]
})
export class FooterComponent {}
