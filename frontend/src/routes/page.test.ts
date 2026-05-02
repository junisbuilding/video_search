import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import * as api from '$lib/api';
import { searchResults, activeVideo } from '$lib/stores';

vi.mock('$lib/api');
vi.mock('$app/state', () => ({
  page: { url: { pathname: '/' } },
}));

beforeEach(() => {
  searchResults.set(null);
  activeVideo.set(null);
  vi.mocked(api.getHealth).mockResolvedValue({
    status: 'ok', db: true, models_loaded: true, gpu_backend: 'cpu', indexed_count: 247,
  });
  vi.mocked(api.search).mockResolvedValue({ query: 'dogs', results: [] });
});

describe('Search page — empty state', () => {
  it('shows the indexed moment count', async () => {
    render(Page);
    await screen.findByText(/247/);
  });

  it('shows the search input', () => {
    render(Page);
    expect(screen.getByRole('searchbox')).toBeInTheDocument();
  });
});

describe('Search page — after search', () => {
  it('calls api.search on form submit', async () => {
    render(Page);
    const input = screen.getByRole('searchbox');
    await fireEvent.input(input, { target: { value: 'dogs' } });
    await fireEvent.submit(input.closest('form')!);
    await waitFor(() => expect(api.search).toHaveBeenCalledWith('dogs', 10));
  });

  it('shows result count after search', async () => {
    vi.mocked(api.search).mockResolvedValue({
      query: 'dogs',
      results: [
        {
          video_id: 'v1', path: '/a.mp4', duration_sec: 60, top_score: 0.9,
          moments: [{ timestamp_sec: 10, score: 0.9, thumb_url: null, caption: 'Dog running', source: 'caption' as const }],
        },
      ],
    });
    render(Page);
    const input = screen.getByRole('searchbox');
    await fireEvent.input(input, { target: { value: 'dogs' } });
    await fireEvent.submit(input.closest('form')!);
    await screen.findByText(/1 moment/);
  });
});
