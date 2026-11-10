import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    title: 'SevaFund India — Every rupee, accounted for',
    loadComponent: () =>
      import('./pages/home/home.component').then(m => m.HomeComponent),
  },
  {
    path: 'campaigns',
    title: 'Explore verified causes · SevaFund India',
    loadComponent: () =>
      import('./pages/campaign-list/campaign-list.component').then(m => m.CampaignListComponent),
  },
  {
    path: 'campaigns/:id',
    title: 'Fundraiser · SevaFund India',
    loadComponent: () =>
      import('./pages/campaign-detail/campaign-detail.component').then(m => m.CampaignDetailComponent),
  },
  {
    path: 'how-it-works',
    title: 'How it works · SevaFund India',
    loadComponent: () =>
      import('./pages/how-it-works/how-it-works.component').then(m => m.HowItWorksComponent),
  },
  {
    path: 'trust',
    title: 'Trust & safety · SevaFund India',
    loadComponent: () =>
      import('./pages/trust/trust.component').then(m => m.TrustComponent),
  },
  {
    path: 'about',
    title: 'About · SevaFund India',
    loadComponent: () =>
      import('./pages/about/about.component').then(m => m.AboutComponent),
  },
  {
    path: 'create',
    title: 'Start a fundraiser · SevaFund India',
    loadComponent: () =>
      import('./pages/create-campaign/create-campaign.component').then(m => m.CreateCampaignComponent),
  },
  {
    path: 'admin',
    title: 'Moderation portal · SevaFund India',
    loadComponent: () =>
      import('./pages/admin/admin.component').then(m => m.AdminComponent),
  },
  {
    path: '**',
    redirectTo: '',
  },
];
