import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { HttpEvent, HttpEventType } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { CVUploadResponse, ProfileMetric } from '../../core/models';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatProgressBarModule,
    MatChipsModule,
    MatIconModule
  ],
  templateUrl: './upload.component.html',
  styleUrls: ['./upload.component.css']
})
export class UploadComponent {
  dragOver = false;
  uploading = false;
  parsing = false;
  uploadProgress = 0;
  uploadError = '';
  parsedProfileSummary: CVUploadResponse['profile_summary'] | null = null;
  profileMetrics: ProfileMetric[] = [];
  statusMessage = '';

  private uploadCapTimer?: ReturnType<typeof setTimeout>;

  constructor(
    private apiService: ApiService,
    private authService: AuthService,
    private router: Router
  ) {}

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragOver = true;
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.dragOver = false;
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver = false;
    if (event.dataTransfer?.files?.length) {
      this.handleFile(event.dataTransfer.files[0]);
    }
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files?.length) {
      this.handleFile(input.files[0]);
    }
  }

  handleFile(file: File): void {
    if (file.type !== 'application/pdf') {
      this.uploadError = 'Only PDF files are supported.';
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      this.uploadError = 'File size exceeds the 5MB limit.';
      return;
    }

    this.clearUploadTimer();
    this.uploadError = '';
    this.uploading = true;
    this.parsing = false;
    this.uploadProgress = 0;
    this.parsedProfileSummary = null;
    this.profileMetrics = [];
    this.statusMessage = 'Uploading...';

    // Cap "Uploading..." UI at 3 seconds, then show parsing state
    this.uploadCapTimer = setTimeout(() => {
      if (this.uploading) {
        this.uploading = false;
        this.parsing = true;
        this.statusMessage = 'Extracting text & structuring profile...';
      }
    }, 3000);

    console.log('[Brieflyy] CV upload started:', file.name, file.size);

    this.apiService.uploadCV(file).subscribe({
      next: (event: HttpEvent<CVUploadResponse>) => {
        if (event.type === HttpEventType.UploadProgress) {
          this.uploadProgress = Math.round((100 * event.loaded) / (event.total || 100));
        } else if (event.type === HttpEventType.Response && event.body) {
          console.log('[Brieflyy] CV parse complete:', event.body);
          this.clearUploadTimer();
          this.uploading = false;
          this.parsing = false;
          this.showResults(event.body);
        }
      },
      error: (err) => {
        console.error('[Brieflyy] CV upload error:', err);
        this.clearUploadTimer();
        this.uploading = false;
        this.parsing = false;
        this.uploadError = err.error?.detail || err.message || 'Failed to upload CV. Please try again.';
      }
    });
  }

  private showResults(response: CVUploadResponse): void {
    this.parsedProfileSummary = response.profile_summary;
    this.profileMetrics = this.buildMetrics(response);
    this.statusMessage = '';
  }

  private clearUploadTimer(): void {
    if (this.uploadCapTimer) {
      clearTimeout(this.uploadCapTimer);
      this.uploadCapTimer = undefined;
    }
  }

  private buildMetrics(response: CVUploadResponse): ProfileMetric[] {
    if (response.metrics?.length) {
      return response.metrics;
    }
    const s = response.profile_summary;
    return [
      { label: 'Skills', count: s.skills_count, icon: 'bi-tools' },
      { label: 'Experience', count: s.experience_count, icon: 'bi-briefcase' },
      { label: 'Projects', count: s.projects_count, icon: 'bi-folder' },
      { label: 'Education', count: s.education_count, icon: 'bi-mortarboard' },
    ].filter(m => m.count > 0);
  }

  logout(): void {
    this.authService.logout();
  }
}
