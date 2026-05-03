import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import SetupModal from './SetupModal.svelte';
import * as api from '$lib/api';

vi.mock('$lib/api');
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

const catalogWithFirstRun = {
  first_run: true,
  active_models: { vision: '', siglip: '', text_embedder: '' },
  vision: [{ id: 'moondream2', label: 'moondream2', size_label: '~2 GB', cached: false, default: true }],
  siglip: [{ id: 'siglip2-base', label: 'SigLIP Base', size_label: '~1.2 GB', cached: false, default: true }],
  text_embedder: [{ id: 'bge-small-en', label: 'BGE Small (English)', size_label: '~130 MB', cached: false, default: true }],
};

const catalogAllCached = {
  first_run: false,
  active_models: { vision: 'moondream2', siglip: 'siglip2-base', text_embedder: 'bge-small-en' },
  vision: [{ id: 'moondream2', label: 'moondream2', size_label: '~2 GB', cached: true, default: true }],
  siglip: [{ id: 'siglip2-base', label: 'SigLIP Base', size_label: '~1.2 GB', cached: true, default: true }],
  text_embedder: [{ id: 'bge-small-en', label: 'BGE Small (English)', size_label: '~130 MB', cached: true, default: true }],
};

const idleProgress = {
  active: false, model_type: '', model_id: '', downloaded_bytes: 0, total_bytes: 0, error: null, complete: false,
};

beforeEach(() => {
  vi.mocked(api.startModelDownload).mockResolvedValue({ queued: true });
  vi.mocked(api.getDownloadProgress).mockResolvedValue(idleProgress);
  vi.mocked(api.getModelCatalog).mockResolvedValue(catalogWithFirstRun);
  localStorage.clear();
});

describe('SetupModal', () => {
  it('renders the welcome heading', async () => {
    render(SetupModal);
    await waitFor(() => expect(screen.getByText(/Welcome to Videosearch/i)).toBeInTheDocument());
  });

  it('shows all three model labels', async () => {
    render(SetupModal);
    await waitFor(() => {
      expect(screen.getByText(/Vision model/i)).toBeInTheDocument();
      expect(screen.getByText(/Image understanding/i)).toBeInTheDocument();
      expect(screen.getByText(/Search model/i)).toBeInTheDocument();
    });
  });

  it('calls startModelDownload for each uncached default on mount', async () => {
    render(SetupModal);
    await waitFor(() => {
      expect(api.startModelDownload).toHaveBeenCalledWith('vision', 'moondream2');
      expect(api.startModelDownload).toHaveBeenCalledWith('siglip', 'siglip2-base');
      expect(api.startModelDownload).toHaveBeenCalledWith('text_embedder', 'bge-small-en');
    });
  });

  it('sets localStorage setup_seen when all models become cached', async () => {
    vi.mocked(api.getModelCatalog)
      .mockResolvedValueOnce(catalogWithFirstRun)
      .mockResolvedValue(catalogAllCached);
    vi.mocked(api.getDownloadProgress).mockResolvedValue({ ...idleProgress, complete: true });

    render(SetupModal);
    await waitFor(() => {
      expect(localStorage.getItem('setup_seen')).toBe('1');
    }, { timeout: 3000 });
  });
});
