import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import * as api from '$lib/api';

vi.mock('$lib/api');
vi.mock('$app/state', () => ({ page: { url: { pathname: '/library' } } }));

const folder = {
  id: 'f1',
  path: '/home/user/videos',
  added_at: 0,
  counts: { indexed: 5, pending: 0, failed: 0, missing: 1 },
};

beforeEach(() => {
  vi.mocked(api.getLibrary).mockResolvedValue({ folders: [folder], ad_hoc_counts: { indexed: 0, pending: 0, failed: 0, missing: 0 } });
  vi.mocked(api.rescanFolder).mockResolvedValue({ enqueued: 2 });
  vi.mocked(api.deleteFolder).mockResolvedValue(undefined);
  vi.mocked(api.addFolder).mockResolvedValue({ folder, enqueued: 1 });
});

describe('Library page', () => {
  it('lists folder paths', async () => {
    render(Page);
    await screen.findByText('/home/user/videos');
  });

  it('shows indexed and missing counts', async () => {
    render(Page);
    await screen.findByText(/5 indexed/);
    await screen.findByText(/1 missing/);
  });

  it('calls rescanFolder on Rescan click', async () => {
    render(Page);
    await screen.findByText('Rescan');
    await fireEvent.click(screen.getByText('Rescan'));
    await waitFor(() => expect(api.rescanFolder).toHaveBeenCalledWith('f1'));
  });

  it('calls deleteFolder after Remove confirmation', async () => {
    vi.stubGlobal('confirm', () => true);
    render(Page);
    await screen.findByText('Remove');
    await fireEvent.click(screen.getByText('Remove'));
    await waitFor(() => expect(api.deleteFolder).toHaveBeenCalledWith('f1'));
    vi.unstubAllGlobals();
  });

  it('shows Add Folder button', async () => {
    render(Page);
    await screen.findByText('Add Folder');
  });
});
