import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavbarComponent } from './components/navbar/navbar.component';
import { FooterComponent } from './components/footer/footer.component';
import { SmoothScrollService } from './services/smooth-scroll.service';
import { ThemeService } from './services/theme.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, NavbarComponent, FooterComponent],
  template: `
    <a class="skip-link" href="#main" (click)="skipToContent($event)">Skip to content</a>
    <app-navbar></app-navbar>
    <main id="main" class="main-content" tabindex="-1">
      <router-outlet></router-outlet>
    </main>
    <app-footer></app-footer>
  `,
  styles: [`
    .main-content {
      display: block;
      min-height: 70vh;
      outline: none;
    }
  `]
})
export class AppComponent {
  title = 'SevaFund India';
  // Start Lenis + ScrollTrigger and the theme engine once, app-wide.
  private smoothScroll = inject(SmoothScrollService);
  private theme = inject(ThemeService);

  skipToContent(event: Event): void {
    event.preventDefault();
    const main = document.getElementById('main');
    main?.focus({ preventScroll: true });
    this.smoothScroll.scrollTo(main ?? 0, { offset: -80 });
  }
}
