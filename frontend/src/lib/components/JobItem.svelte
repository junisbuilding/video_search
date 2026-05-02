<script lang="ts">
  import { retryJob } from '$lib/api';
  import type { Job } from '$lib/types';

  let { job }: { job: Job } = $props();

  function filename(path: string | null): string {
    if (!path) return '(unknown)';
    return path.split('/').pop() ?? path;
  }

  function statusColor(status: string): string {
    if (status === 'done') return '#4ade80';
    if (status === 'failed') return '#f87171';
    if (status === 'in_progress') return '#60a5fa';
    return '#555';
  }

  async function handleRetry() {
    await retryJob(job.id);
  }
</script>

<li class="job-item">
  <div class="job-main">
    <div class="job-left">
      <span class="job-filename">{filename(job.path)}</span>
      <span class="job-badge" style="color: {statusColor(job.status)}">{job.status}</span>
    </div>
    {#if job.status === 'failed'}
      <button class="retry-btn" onclick={handleRetry}>Retry</button>
    {/if}
  </div>

  {#if job.status === 'in_progress'}
    <div class="progress-bar">
      <div class="progress-fill" style="width: {Math.round(job.progress * 100)}%"></div>
    </div>
  {/if}

  {#if job.error}
    <p class="error-msg">{job.error}</p>
  {/if}
</li>

<style>
  .job-item {
    background: #1a1a1a;
    border: 1px solid #1e1e1e;
    border-radius: 8px;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .job-main {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .job-left {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .job-filename {
    font-size: 11px;
    color: #e0e0e0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .job-badge {
    font-size: 9px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .retry-btn {
    background: none;
    border: 1px solid #f87171;
    color: #f87171;
    font-size: 9px;
    padding: 3px 8px;
    border-radius: 4px;
    flex-shrink: 0;
    cursor: pointer;
  }

  .retry-btn:hover {
    background: #f8717122;
  }

  .progress-bar {
    height: 2px;
    background: #2a2a2a;
    border-radius: 1px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: #4ade80;
    border-radius: 1px;
    transition: width 0.3s;
  }

  .error-msg {
    font-size: 9px;
    color: #f87171;
  }
</style>
