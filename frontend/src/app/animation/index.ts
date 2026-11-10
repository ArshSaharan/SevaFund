import { CountUpDirective } from './count-up.directive';
import { ParallaxDirective } from './parallax.directive';
import { RevealDirective } from './reveal.directive';
import { ScrubTextDirective } from './scrub-text.directive';
import { SplitTextDirective } from './split-text.directive';

export * from './gsap';
export { CountUpDirective, ParallaxDirective, RevealDirective, ScrubTextDirective, SplitTextDirective };

/** Convenience bundle for a standalone component's `imports`. */
export const MOTION = [
  RevealDirective,
  SplitTextDirective,
  ScrubTextDirective,
  CountUpDirective,
  ParallaxDirective,
] as const;
