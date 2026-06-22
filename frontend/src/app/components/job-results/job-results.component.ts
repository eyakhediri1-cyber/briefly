import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-job-results',
  templateUrl: './job-results.component.html',
  styleUrls: ['./job-results.component.scss']
})
export class JobResultsComponent implements OnInit {
  jobs: any[] = [];
  loading = true;
  stats = { totalFound: 0, strongMatches: 0, cvsReady: 0 };

  constructor(private api: ApiService, private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.route.params.subscribe(params => {
      if (params['sessionId']) {
        this.loadResults(params['sessionId']);
      }
    });
  }

  async loadResults(sessionId: string): Promise<void> {
    this.loading = true;
    try {
      const resp: any = await this.api.getJobResults(sessionId).toPromise();
      console.log('JobResults API response (components):', resp);
      const anyRes = resp as any;
      const jobsArr = Array.isArray(anyRes.jobs)
        ? anyRes.jobs
        : Array.isArray(anyRes.results)
        ? anyRes.results
        : [];

      this.jobs = jobsArr.map((r: any) => ({
        id: r.job_id || r.id || r.job_id,
        job: r.job || r,
        title: r.title || r.job?.title || r.job?.job_title,
        company: r.company || r.job?.company,
        location: r.location || r.job?.location,
        fitScore: r.fit_score || r.fit_percentage || 0,
        tailoredCvId: r.tailored_cv_id || r.tailored_cv?.id,
      }));

      this.stats = {
        totalFound: anyRes.total_jobs_found ?? anyRes.jobs_found ?? jobsArr.length,
        strongMatches: this.jobs.filter(j => j.fitScore >= 80).length,
        cvsReady: anyRes.total_tailored ?? anyRes.cvs_ready ?? 0,
      };
    } catch (e) {
      console.error('Load job results failed', e);
    } finally {
      this.loading = false;
    }
  }

  async applyToJob(job: any) {
    if (!confirm(`Apply to ${job.title} at ${job.company}?`)) return;
    try {
      await this.api.submitApplication(job.id).toPromise();
      alert('✓ Applied!');
    } catch (e) {
      console.error('Apply failed', e);
      alert('Apply failed');
    }
  }
}
