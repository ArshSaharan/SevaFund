import {
  Component,
  ElementRef,
  ViewChild,
  AfterViewInit,
  OnDestroy,
  NgZone,
  inject,
  signal
} from '@angular/core';
import { CommonModule } from '@angular/common';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { SmoothScrollService } from '../../services/smooth-scroll.service';

@Component({
  selector: 'app-expo-glasses',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div
      class="expo-glasses-container"
      #containerRef
      (mousemove)="onMouseMove($event)"
      (mouseleave)="onMouseLeave()"
    >
      <!-- Ambient Backlight Glow -->
      <div class="ambient-glow" #glowRef></div>

      <!-- Futuristic 3D Glass Frame -->
      <div class="glasses-rig" #rigRef>
        <!-- Top Status Pill -->
        <div class="expo-hud-pill">
          <span class="live-pulse"></span>
          <span class="hud-label">EXPO GLASSES · AI TRANSPARENCY VISION</span>
          <span class="hud-status">ACTIVE</span>
        </div>

        <!-- The Glasses Structure -->
        <div class="glasses-body">
          <!-- Left Frame & Lens -->
          <div class="glass-lens-wrap left-wrap">
            <div class="glass-rim">
              <div class="lens-glass">
                <div class="reflection-sheen"></div>
                <div class="hud-telemetry">
                  <div class="hud-corner top-l"></div>
                  <div class="hud-corner bottom-r"></div>
                  <span class="hud-data-label">VERIFIED CAUSE</span>
                  <div class="hud-data-val">98.4% TRUST</div>
                  <div class="hud-wave">
                    <span></span><span></span><span></span><span></span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Bridge Connection with Smart Sensor -->
          <div class="glasses-bridge">
            <div class="bridge-arch"></div>
            <div class="bridge-sensor">
              <div class="sensor-dot"></div>
            </div>
            <div class="bridge-wire"></div>
          </div>

          <!-- Right Frame & Lens -->
          <div class="glass-lens-wrap right-wrap">
            <div class="glass-rim">
              <div class="lens-glass">
                <div class="reflection-sheen right-sheen"></div>
                <div class="hud-telemetry">
                  <div class="hud-corner top-r"></div>
                  <div class="hud-corner bottom-l"></div>
                  <span class="hud-data-label">FUND ROUTING</span>
                  <div class="hud-data-val">UPI · 0% FEE</div>
                  <div class="hud-tags">
                    <span class="hud-pill">80G TAX</span>
                    <span class="hud-pill">100% DIRECT</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Frame Arms (Left & Right) -->
          <div class="glasses-arm arm-left"></div>
          <div class="glasses-arm arm-right"></div>
        </div>

        <!-- Bottom Controls & Floating HUD Stats -->
        <div class="expo-glasses-footer">
          <div class="hud-metric">
            <span class="metric-title">Smart Refraction</span>
            <span class="metric-value">Index 1.58</span>
          </div>
          <div class="mode-toggle-btn" (click)="toggleVisionMode()">
            <span class="toggle-icon">👁️</span>
            <span>{{ visionModeActive() ? 'Expo Clarity Max' : 'Enhance Expo Vision' }}</span>
          </div>
          <div class="hud-metric align-right">
            <span class="metric-title">Scroll Physics</span>
            <span class="metric-value">Lenis + GSAP</span>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      width: 100%;
    }

    .expo-glasses-container {
      position: relative;
      width: 100%;
      max-width: 540px;
      margin: 0 auto;
      padding: 24px 20px;
      perspective: 1200px;
      transform-style: preserve-3d;
      cursor: crosshair;
    }

    .ambient-glow {
      position: absolute;
      top: 50%;
      left: 50%;
      width: 380px;
      height: 220px;
      transform: translate(-50%, -50%);
      background: radial-gradient(circle, rgba(255, 107, 0, 0.22) 0%, rgba(0, 168, 107, 0.18) 50%, transparent 75%);
      filter: blur(45px);
      pointer-events: none;
      z-index: 0;
      transition: opacity 0.5s ease;
    }

    .glasses-rig {
      position: relative;
      z-index: 1;
      transform-style: preserve-3d;
      will-change: transform;
      background: rgba(255, 255, 255, 0.35);
      backdrop-filter: blur(24px) saturate(190%);
      -webkit-backdrop-filter: blur(24px) saturate(190%);
      border: 1px solid rgba(255, 255, 255, 0.5);
      border-radius: 28px;
      box-shadow:
        0 20px 50px -10px rgba(15, 23, 42, 0.12),
        0 0 0 1px rgba(255, 255, 255, 0.3) inset,
        0 1px 2px 0 rgba(255, 255, 255, 0.6) inset;
      padding: 20px 24px 18px;
      transition: box-shadow 0.4s ease, border-color 0.4s ease;
    }

    .glasses-rig:hover {
      border-color: rgba(255, 107, 0, 0.4);
      box-shadow:
        0 25px 60px -10px rgba(255, 107, 0, 0.18),
        0 0 0 1px rgba(255, 255, 255, 0.5) inset;
    }

    /* Top HUD Pill */
    .expo-hud-pill {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      background: rgba(15, 23, 42, 0.05);
      padding: 6px 14px;
      border-radius: 999px;
      border: 1px solid rgba(15, 23, 42, 0.08);
      margin-bottom: 22px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      color: #0F172A;
    }

    .live-pulse {
      width: 7px;
      height: 7px;
      background: #00A86B;
      border-radius: 50%;
      box-shadow: 0 0 8px #00A86B;
      animation: pulse 1.8s infinite ease-in-out;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(1.3); }
    }

    .hud-label {
      flex: 1;
      text-align: left;
    }

    .hud-status {
      color: #FF6B00;
      font-family: monospace;
      font-size: 10px;
    }

    /* Main Glasses Body */
    .glasses-body {
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      padding: 10px 0 20px;
      transform-style: preserve-3d;
    }

    /* Glass Lens Wrappers */
    .glass-lens-wrap {
      flex: 1;
      max-width: 200px;
      height: 125px;
      position: relative;
      transform-style: preserve-3d;
    }

    .glass-rim {
      width: 100%;
      height: 100%;
      border-radius: 24px;
      background: linear-gradient(145deg, rgba(255, 255, 255, 0.7), rgba(240, 245, 250, 0.25));
      border: 3px solid rgba(15, 23, 42, 0.85);
      box-shadow:
        0 12px 28px rgba(0, 0, 0, 0.12),
        0 2px 4px rgba(255, 255, 255, 0.6) inset;
      position: relative;
      overflow: hidden;
      padding: 4px;
      transition: transform 0.3s ease;
    }

    .lens-glass {
      width: 100%;
      height: 100%;
      border-radius: 18px;
      background: linear-gradient(
        135deg,
        rgba(255, 255, 255, 0.45) 0%,
        rgba(224, 242, 254, 0.25) 50%,
        rgba(254, 243, 199, 0.2) 100%
      );
      backdrop-filter: blur(12px) brightness(1.08);
      -webkit-backdrop-filter: blur(12px) brightness(1.08);
      border: 1px solid rgba(255, 255, 255, 0.75);
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 10px;
    }

    /* Refractive Sheen */
    .reflection-sheen {
      position: absolute;
      top: -60%;
      left: -60%;
      width: 220%;
      height: 220%;
      background: linear-gradient(
        125deg,
        transparent 35%,
        rgba(255, 255, 255, 0.6) 48%,
        rgba(255, 255, 255, 0.8) 50%,
        rgba(255, 255, 255, 0.2) 53%,
        transparent 65%
      );
      pointer-events: none;
      transform: rotate(25deg);
      transition: transform 0.2s ease-out;
    }

    .right-sheen {
      transform: rotate(20deg) scaleX(-1);
    }

    /* HUD Telemetry inside lenses */
    .hud-telemetry {
      position: relative;
      height: 100%;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      z-index: 2;
    }

    .hud-corner {
      position: absolute;
      width: 8px;
      height: 8px;
      border: 1.5px solid #00A86B;
    }

    .top-l { top: -2px; left: -2px; border-right: none; border-bottom: none; }
    .bottom-r { bottom: -2px; right: -2px; border-left: none; border-top: none; }
    .top-r { top: -2px; right: -2px; border-left: none; border-bottom: none; border-color: #FF6B00; }
    .bottom-l { bottom: -2px; left: -2px; border-right: none; border-top: none; border-color: #FF6B00; }

    .hud-data-label {
      font-size: 8.5px;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: #64748B;
      text-transform: uppercase;
    }

    .hud-data-val {
      font-size: 15px;
      font-weight: 800;
      font-family: 'Plus Jakarta Sans', sans-serif;
      color: #0F172A;
      letter-spacing: -0.02em;
    }

    .hud-wave {
      display: flex;
      align-items: center;
      gap: 3px;
      height: 14px;
    }

    .hud-wave span {
      width: 3px;
      height: 100%;
      background: #00A86B;
      border-radius: 2px;
      animation: wave 1.2s infinite ease-in-out;
    }

    .hud-wave span:nth-child(2) { animation-delay: 0.2s; height: 60%; }
    .hud-wave span:nth-child(3) { animation-delay: 0.4s; height: 80%; }
    .hud-wave span:nth-child(4) { animation-delay: 0.6s; height: 40%; }

    @keyframes wave {
      0%, 100% { transform: scaleY(0.4); }
      50% { transform: scaleY(1); }
    }

    .hud-tags {
      display: flex;
      gap: 4px;
      flex-wrap: wrap;
    }

    .hud-pill {
      font-size: 8px;
      font-weight: 700;
      background: rgba(255, 107, 0, 0.12);
      color: #FF6B00;
      padding: 2px 6px;
      border-radius: 4px;
    }

    /* Center Bridge */
    .glasses-bridge {
      width: 44px;
      height: 30px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      position: relative;
      margin: 0 4px;
    }

    .bridge-arch {
      width: 100%;
      height: 8px;
      border: 3.5px solid #0F172A;
      border-bottom: none;
      border-radius: 12px 12px 0 0;
    }

    .bridge-sensor {
      width: 14px;
      height: 14px;
      background: #0F172A;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-top: 2px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.25);
    }

    .sensor-dot {
      width: 5px;
      height: 5px;
      background: #00A86B;
      border-radius: 50%;
      box-shadow: 0 0 6px #00A86B;
    }

    .bridge-wire {
      width: 24px;
      height: 1.5px;
      background: linear-gradient(90deg, #FF6B00, #00A86B);
      margin-top: 2px;
    }

    /* Arms on the outer sides */
    .glasses-arm {
      position: absolute;
      width: 28px;
      height: 6px;
      background: #0F172A;
      border-radius: 3px;
      top: 42%;
    }

    .arm-left {
      left: -12px;
      transform: rotate(8deg);
    }

    .arm-right {
      right: -12px;
      transform: rotate(-8deg);
    }

    /* Footer / Controls */
    .expo-glasses-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-top: 1px solid rgba(15, 23, 42, 0.08);
      padding-top: 14px;
      margin-top: 6px;
    }

    .hud-metric {
      display: flex;
      flex-direction: column;
    }

    .hud-metric.align-right {
      text-align: right;
    }

    .metric-title {
      font-size: 9px;
      font-weight: 600;
      color: #94A3B8;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .metric-value {
      font-size: 11px;
      font-weight: 700;
      color: #334155;
      font-family: monospace;
    }

    .mode-toggle-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: linear-gradient(135deg, #FF6B00, #E65100);
      color: #FFFFFF;
      font-size: 11px;
      font-weight: 700;
      padding: 6px 12px;
      border-radius: 999px;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(255, 107, 0, 0.3);
      transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease;
      user-select: none;
    }

    .mode-toggle-btn:hover {
      transform: scale(1.05);
      box-shadow: 0 6px 16px rgba(255, 107, 0, 0.4);
    }

    @media (max-width: 640px) {
      .expo-glasses-container {
        padding: 12px 8px;
      }
      .glass-lens-wrap {
        height: 105px;
      }
      .hud-data-val {
        font-size: 12px;
      }
      .glasses-bridge {
        width: 28px;
      }
      .arm-left, .arm-right {
        display: none;
      }
    }
  `]
})
export class ExpoGlassesComponent implements AfterViewInit, OnDestroy {
  @ViewChild('containerRef') containerRef!: ElementRef<HTMLDivElement>;
  @ViewChild('rigRef') rigRef!: ElementRef<HTMLDivElement>;
  @ViewChild('glowRef') glowRef!: ElementRef<HTMLDivElement>;

  visionModeActive = signal<boolean>(false);

  private ngZone = inject(NgZone);
  private scrollService = inject(SmoothScrollService);
  private scrollTriggerInstance: ScrollTrigger | null = null;

  ngAfterViewInit(): void {
    if (typeof window === 'undefined') return;

    this.ngZone.runOutsideAngular(() => {
      this.initScrollTrigger();
    });
  }

  /**
   * Interactive 3D tilt tracking with GSAP Expo easing
   */
  onMouseMove(event: MouseEvent): void {
    if (!this.containerRef?.nativeElement || !this.rigRef?.nativeElement) return;

    const rect = this.containerRef.nativeElement.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const rotateX = ((y - centerY) / centerY) * -16; // Up / Down tilt
    const rotateY = ((x - centerX) / centerX) * 20;  // Left / Right tilt

    // Animate with GSAP exponential ease-out
    gsap.to(this.rigRef.nativeElement, {
      rotateX,
      rotateY,
      transformPerspective: 1000,
      duration: 0.8,
      ease: 'expo.out'
    });

    if (this.glowRef?.nativeElement) {
      const glowX = ((x - centerX) / centerX) * 40;
      const glowY = ((y - centerY) / centerY) * 30;
      gsap.to(this.glowRef.nativeElement, {
        x: glowX,
        y: glowY,
        duration: 1,
        ease: 'expo.out'
      });
    }
  }

  /**
   * Reset orientation smoothly when cursor leaves
   */
  onMouseLeave(): void {
    if (!this.rigRef?.nativeElement) return;

    gsap.to(this.rigRef.nativeElement, {
      rotateX: 0,
      rotateY: 0,
      duration: 1.2,
      ease: 'expo.out'
    });

    if (this.glowRef?.nativeElement) {
      gsap.to(this.glowRef.nativeElement, {
        x: 0,
        y: 0,
        duration: 1.2,
        ease: 'expo.out'
      });
    }
  }

  /**
   * ScrollTrigger parallax animation tied to Lenis
   */
  private initScrollTrigger(): void {
    const ScrollTriggerClass = this.scrollService.getScrollTrigger();
    if (!ScrollTriggerClass || !this.containerRef?.nativeElement) return;

    // Create scroll-driven parallax for Expo Glasses
    this.scrollTriggerInstance = ScrollTriggerClass.create({
      trigger: this.containerRef.nativeElement,
      start: 'top bottom',
      end: 'bottom top',
      scrub: 1.2,
      onUpdate: (self) => {
        const progress = self.progress;
        if (this.rigRef?.nativeElement) {
          // Floating vertical parallax and subtle tilt shift on scroll
          gsap.set(this.rigRef.nativeElement, {
            y: (progress - 0.5) * -60,
            rotateZ: (progress - 0.5) * 6
          });
        }
      }
    });
  }

  /**
   * Toggle enhanced glassmorphism clarity mode on root element
   */
  toggleVisionMode(): void {
    const nextState = !this.visionModeActive();
    this.visionModeActive.set(nextState);

    if (typeof document !== 'undefined') {
      if (nextState) {
        document.body.classList.add('expo-vision-mode');
      } else {
        document.body.classList.remove('expo-vision-mode');
      }
    }
  }

  ngOnDestroy(): void {
    if (this.scrollTriggerInstance) {
      this.scrollTriggerInstance.kill();
      this.scrollTriggerInstance = null;
    }
    if (typeof document !== 'undefined') {
      document.body.classList.remove('expo-vision-mode');
    }
  }
}
