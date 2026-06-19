import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { TokenResponse, User } from '../models';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly tokenKey = 'brieflyy_token';
  private readonly userKey = 'brieflyy_user';

  // Signals for reactive state management (native to Angular 17)
  private _token = signal<string | null>(localStorage.getItem(this.tokenKey));
  private _user = signal<User | null>(this.getUserFromLocalStorage());

  readonly token = computed(() => this._token());
  readonly currentUser = computed(() => this._user());
  readonly isAuthenticated = computed(() => !!this._token());

  constructor(private http: HttpClient, private router: Router) {}

  login(credentials: { email: string; password: string }): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${environment.apiUrl}/auth/login`, credentials).pipe(
      tap(response => {
        this.saveAuth(response.access_token, response.user);
      })
    );
  }

  register(userData: { email: string; password: string; name?: string }): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${environment.apiUrl}/auth/register`, userData).pipe(
      tap(response => {
        this.saveAuth(response.access_token, response.user);
      })
    );
  }

  logout(): void {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
    this._token.set(null);
    this._user.set(null);
    this.router.navigate(['/auth/login']);
  }

  private saveAuth(token: string, user: User): void {
    localStorage.setItem(this.tokenKey, token);
    localStorage.setItem(this.userKey, JSON.stringify(user));
    this._token.set(token);
    this._user.set(user);
  }

  private getUserFromLocalStorage(): User | null {
    const userStr = localStorage.getItem(this.userKey);
    if (!userStr) return null;
    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }
}
