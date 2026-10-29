import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./pages/campaign-list/campaign-list.component').then(m => m.CampaignListComponent),
  },
  {
    path: 'campaigns/:id',
    loadComponent: () =>
      import('./pages/campaign-detail/campaign-detail.component').then(m => m.CampaignDetailComponent),
  },
  {
    path: 'create',
    loadComponent: () =>
      import('./pages/create-campaign/create-campaign.component').then(m => m.CreateCampaignComponent),
  },
  {
    path: 'admin',
    loadComponent: () =>
      import('./pages/admin/admin.component').then(m => m.AdminComponent),
  },
  {
    path: '**',
    redirectTo: '',
  },
];
