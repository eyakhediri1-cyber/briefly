import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const ErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);

  return next(req).pipe(
    catchError(err => {
      if ([401, 403].includes(err.status)) {
        // Auto-logout if unauthorized or forbidden
        authService.logout();
      }

      const error = err.error?.detail || err.statusText || 'An error occurred';
      return throwError(() => new Error(error));
    })
  );
};
