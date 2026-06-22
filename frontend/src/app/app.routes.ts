import { Routes } from '@angular/router';
import { AuthGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: '/upload', pathMatch: 'full' },
  { path: 'auth/login', loadComponent: () => import('./features/auth/login/login.component').then(m => m.LoginComponent) },
  { path: 'auth/register', loadComponent: () => import('./features/auth/register/register.component').then(m => m.RegisterComponent) },
  { path: 'upload', loadComponent: () => import('./features/upload/upload.component').then(m => m.UploadComponent), canActivate: [AuthGuard] },
  { path: 'search', loadComponent: () => import('./features/search/search.component').then(m => m.SearchComponent), canActivate: [AuthGuard] },
  { path: 'strategy/:sessionId', loadComponent: () => import('./features/strategy/strategy.component').then(m => m.StrategyComponent), canActivate: [AuthGuard] },
  { path: 'results/:sessionId', loadComponent: () => import('./features/job-results/job-results.component').then(m => m.JobResultsComponent), canActivate: [AuthGuard] },
  { path: 'job/:jobId/fit', loadComponent: () => import('./features/job-detail/job-detail.component').then(m => m.JobDetailComponent), canActivate: [AuthGuard] },
  { path: 'tailor/:jobId', loadComponent: () => import('./features/cv-tailoring/cv-tailoring.component').then(m => m.CVTailoringComponent), canActivate: [AuthGuard] },
];
