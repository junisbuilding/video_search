import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import JobItem from './JobItem.svelte';
import * as api from '$lib/api';
import type { Job } from '$lib/types';

vi.mock('$lib/api');

const makeJob = (overrides: Partial<Job> = {}): Job => ({
  id: 'job-1', video_id: null, path: '/home/user/video.mp4', kind: 'index',
  status: 'pending', progress: 0, error: null, created_at: 0, updated_at: 0,
  ...overrides,
});

describe('JobItem', () => {
  it('shows the filename from path', () => {
    render(JobItem, { job: makeJob() });
    expect(screen.getByText('video.mp4')).toBeInTheDocument();
  });

  it('shows status badge', () => {
    render(JobItem, { job: makeJob({ status: 'done' }) });
    expect(screen.getByText('done')).toBeInTheDocument();
  });

  it('shows progress bar when in_progress', () => {
    const { container } = render(JobItem, { job: makeJob({ status: 'in_progress', progress: 0.5 }) });
    const bar = container.querySelector('.progress-fill');
    expect(bar).toBeInTheDocument();
    expect((bar as HTMLElement).style.width).toBe('50%');
  });

  it('shows error message when failed', () => {
    render(JobItem, { job: makeJob({ status: 'failed', error: 'model error' }) });
    expect(screen.getByText('model error')).toBeInTheDocument();
  });

  it('shows Retry button when failed', () => {
    render(JobItem, { job: makeJob({ status: 'failed' }) });
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('calls retryJob on Retry click', async () => {
    vi.mocked(api.retryJob).mockResolvedValue({ job_id: 'new-job' });
    render(JobItem, { job: makeJob({ status: 'failed' }) });
    await fireEvent.click(screen.getByText('Retry'));
    expect(api.retryJob).toHaveBeenCalledWith('job-1');
  });

  it('does not show Retry button for non-failed jobs', () => {
    render(JobItem, { job: makeJob({ status: 'done' }) });
    expect(screen.queryByText('Retry')).not.toBeInTheDocument();
  });
});
