import { CountUpDirective } from './count-up.directive';
import { ParallaxDirective } from './parallax.directive';
import { MagneticDirective, SpotlightDirective, TiltDirective } from './pointer.directives';
import { RevealDirective } from './reveal.directive';
import { ScrubTextDirective } from './scrub-text.directive';
import { SplitTextDirective } from './split-text.directive';

export * from './gsap';
export { celebrate } from './celebrate';
export {
  CountUpDirective,
  MagneticDirective,
  ParallaxDirective,
  RevealDirective,
  ScrubTextDirective,
  SpotlightDirective,
  SplitTextDirective,
  TiltDirective,
};

/** Convenience bundle for a standalone component's `imports`. */
export const MOTION = [
  RevealDirective,
  SplitTextDirective,
  ScrubTextDirective,
  CountUpDirective,
  ParallaxDirective,
  SpotlightDirective,
  TiltDirective,
  MagneticDirective,
] as const;
