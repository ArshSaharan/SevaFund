import { ApplicationConfig, inject, provideZoneChangeDetection } from '@angular/core';
import { IsActiveMatchOptions, Router, provideRouter, withViewTransitions } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';

import { routes } from './app.routes';
import { authInterceptor } from './interceptors/auth.interceptor';

/** Same page, different query params (e.g. a category filter) — no page transition. */
const SAME_PAGE: IsActiveMatchOptions = {
  paths: 'exact',
  matrixParams: 'exact',
  queryParams: 'ignored',
  fragment: 'ignored',
};

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(
      routes,
      withViewTransitions({
        skipInitialTransition: true,
        onViewTransitionCreated: ({ transition }) => {
          const router = inject(Router);
          const target = router.getCurrentNavigation()?.finalUrl;
          if (target && router.isActive(target, SAME_PAGE)) {
            transition.skipTransition();
          }
        },
      }),
    ),
    provideHttpClient(
      withFetch(),
      withInterceptors([authInterceptor])
    )
  ]
};
