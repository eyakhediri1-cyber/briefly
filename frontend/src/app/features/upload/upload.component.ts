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

interface ParsingStep {
  label: string;
  status: 'pending' | 'active' | 'done';
}

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
  uploadProgress = 0;
  parsing = false;
  uploadError = '';

  parsingSteps: ParsingStep[] = [
    { label: 'Uploading file...', status: 'pending' },
    { label: 'Extracting text from PDF...', status: 'pending' },
    { label: 'Structuring profile with AI...', status: 'pending' },
    { label: 'Generating embeddings & FAISS index...', status: 'pending' }
  ];

  parsedProfileSummary: CVUploadResponse['profile_summary'] | null = null;
  profileMetrics: ProfileMetric[] = [];

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
    if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
      this.handleFile(event.dataTransfer.files[0]);
    }
  }

  onFileSelected(event: any): void {
    if (event.target.files && event.target.files.length > 0) {
      this.handleFile(event.target.files[0]);
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

    this.uploadError = '';
    this.uploading = true;
    this.uploadProgress = 0;
    this.parsing = false;
    this.parsedProfileSummary = null;
    this.profileMetrics = [];
    this.resetParsingSteps();

    this.apiService.uploadCV(file).subscribe({
      next: (event: HttpEvent<CVUploadResponse>) => {
        if (event.type === HttpEventType.UploadProgress) {
          this.uploadProgress = Math.round((100 * event.loaded) / (event.total || 100));
        } else if (event.type === HttpEventType.Response) {
          console.log('[Brieflyy] CV upload response:', event.body);
          this.uploading = false;
          this.parsing = true;
          this.completeParsingSteps(event.body!);
        }
      },
      error: (err) => {
        console.error('[Brieflyy] CV upload error:', err);
        this.uploading = false;
        this.parsing = false;
        this.uploadError = err.error?.detail || err.message || 'Failed to upload CV. Please try again.';
      }
    });
  }

  private resetParsingSteps(): void {
    this.parsingSteps = this.parsingSteps.map(s => ({ ...s, status: 'pending' as const }));
  }

  private completeParsingSteps(response: CVUploadResponse): void {
    // Backend already parsed — animate steps quickly to show what happened
    this.parsingSteps[0].status = 'done';
    this.parsingSteps[1].status = 'active';

    setTimeout(() => {
      this.parsingSteps[1].status = 'done';
      this.parsingSteps[2].status = 'active';

      setTimeout(() => {
        this.parsingSteps[2].status = 'done';
        this.parsingSteps[3].status = 'active';

        setTimeout(() => {
          this.parsingSteps[3].status = 'done';
          this.parsing = false;
          this.parsedProfileSummary = response.profile_summary;
          this.profileMetrics = this.buildMetrics(response);
          console.log('[Brieflyy] Profile metrics:', this.profileMetrics);
        }, 400);
      }, 400);
    }, 400);
  }

  private buildMetrics(response: CVUploadResponse): ProfileMetric[] {
    if (response.metrics && response.metrics.length > 0) {
      return response.metrics;
    }

    const s = response.profile_summary;
    const candidates: ProfileMetric[] = [
      { label: 'Skills', count: s.skills_count, icon: 'bi-tools' },
      { label: 'Experience', count: s.experience_count, icon: 'bi-briefcase' },
      { label: 'Projects', count: s.projects_count, icon: 'bi-folder' },
      { label: 'Education', count: s.education_count, icon: 'bi-mortarboard' },
      { label: 'Certifications', count: s.certifications_count || 0, icon: 'bi-award' },
      { label: 'Languages', count: s.languages_count || 0, icon: 'bi-translate' },
    ];
    return candidates.filter(m => m.count > 0);
  }

  logout(): void {
    this.authService.logout();
  }
}
