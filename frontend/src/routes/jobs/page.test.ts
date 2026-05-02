import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import Page from './+page.svelte';
import { jobs } from '$lib/stores';
import type { Job } from '$lib/types';

vi.mock('$lib/api');
vi.mock('$app/state', () => ({ page: { url: { pathname: '/jobs' } } }));

const makeJob = (overrides: Partial<Job> = {}): Job => ({
  id: 'job-1', video_id: null, path: '/video.mp4', kind: 'index',
  status: 'pending', progress: 0, error: null, created_at: 0, updated_at: 0,
  ...overrides,
});

beforeEach(() => {
  jobs.set([]);
});

describe('Jobs page', () => {
  it('shows empty state when no jobs', () => {
    render(Page);
    expect(screen.getByText(/no jobs/i)).toBeInTheDocument();
  });

  it('renders a job from the store', () => {
    jobs.set([makeJob({ path: '/home/user/movie.mp4', status: 'done' })]);
    render(Page);
    expect(screen.getByText('movie.mp4')).toBeInTheDocument();
    expect(screen.getByText('done')).toBeInTheDocument();
  });
});
