import { Component } from '@angular/core';

@Component({
  selector: 'app-footer',
  standalone: true,
  template: `
    <footer class="footer">
      <div class="container footer-content">
        <div class="footer-col">
          <div class="footer-brand">
            <span class="flag">🇮🇳</span>
            <span class="name">SevaFund India</span>
          </div>
          <p class="tagline">India's first AI-audited medical & emergency crowdfunding network. Powered by real-time hospital verification and 0% platform fee.</p>
        </div>

        <div class="footer-col">
          <h4>Supported Causes</h4>
          <ul>
            <li>Cancer & Chemotherapy</li>
            <li>Pediatric Heart Surgeries</li>
            <li>Organ Transplants (Liver/Kidney)</li>
            <li>Emergency Disaster Relief</li>
            <li>Education & Tuition Support</li>
          </ul>
        </div>

        <div class="footer-col">
          <h4>Trust & Security</h4>
          <ul>
            <li>🛡️ AI Medical Cost Verification</li>
            <li>🏥 Direct Hospital Billing NEFT</li>
            <li>📜 Section 80G Tax Certificates</li>
            <li>⚡ Instant UPI Payments (GPay/PhonePe)</li>
          </ul>
        </div>
      </div>
      <div class="footer-bottom">
        <div class="container bottom-content">
          <p>© 2026 SevaFund India. Built for Indian healthcare accessibility. 100% Secure.</p>
        </div>
      </div>
    </footer>
  `,
  styles: [`
    .footer {
      background-color: var(--navy);
      color: var(--gray-300);
      margin-top: 80px;
      padding-top: 60px;
    }
    .footer-content {
      display: grid;
      grid-template-columns: 2fr 1fr 1fr;
      gap: 40px;
      padding-bottom: 50px;
    }
    .footer-brand {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 16px;
    }
    .footer-brand .name {
      font-size: 20px;
      font-weight: 800;
      color: white;
    }
    .tagline {
      font-size: 14px;
      color: var(--gray-400);
      max-width: 380px;
      line-height: 1.6;
    }
    .footer-col h4 {
      color: white;
      font-size: 16px;
      margin-bottom: 18px;
    }
    .footer-col ul {
      list-style: none;
    }
    .footer-col ul li {
      font-size: 14px;
      color: var(--gray-400);
      margin-bottom: 10px;
    }
    .footer-bottom {
      border-top: 1px solid rgba(255,255,255,0.1);
      padding: 20px 0;
      font-size: 13px;
      color: var(--gray-500);
      text-align: center;
    }
    @media (max-width: 768px) {
      .footer-content {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class FooterComponent {}
