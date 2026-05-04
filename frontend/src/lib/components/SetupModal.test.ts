import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/svelte';
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
  vi.clearAllMocks();
  vi.mocked(api.startModelDownload).mockResolvedValue({ queued: true });
  vi.mocked(api.getDownloadProgress).mockResolvedValue([]);
  vi.mocked(api.getModelCatalog).mockResolvedValue(catalogWithFirstRun);
  vi.mocked(api.getSettings).mockResolvedValue({ hf_token: 'already-set' });
  vi.mocked(api.patchSettings).mockResolvedValue({ hf_token: null });
  localStorage.clear();
});

describe('SetupModal', () => {
  it('renders the welcome heading', async () => {
    render(SetupModal);
    await waitFor(() => expect(screen.getByText(/Welcome to Videosearch/i)).toBeInTheDocument());
  });

  it('shows all three model labels when token already configured', async () => {
    render(SetupModal);
    await waitFor(() => {
      expect(screen.getByText(/Vision model/i)).toBeInTheDocument();
      expect(screen.getByText(/Image understanding/i)).toBeInTheDocument();
      expect(screen.getByText(/Search model/i)).toBeInTheDocument();
    });
  });

  it('calls startModelDownload for each uncached default when token already configured', async () => {
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
    vi.mocked(api.getDownloadProgress).mockResolvedValue([{ ...idleProgress, complete: true }]);

    render(SetupModal);
    await waitFor(() => {
      expect(localStorage.getItem('setup_seen')).toBe('1');
    }, { timeout: 3000 });
  });

  it('shows token input step when hf_token is null', async () => {
    vi.mocked(api.getSettings).mockResolvedValue({ hf_token: null });
    render(SetupModal);
    await waitFor(() => {
      expect(screen.getByPlaceholderText('hf_...')).toBeInTheDocument();
    });
    expect(api.startModelDownload).not.toHaveBeenCalled();
  });

  it('skips token step and starts downloads when hf_token is already set', async () => {
    vi.mocked(api.getSettings).mockResolvedValue({ hf_token: 'hf_existing' });
    render(SetupModal);
    await waitFor(() => {
      expect(api.startModelDownload).toHaveBeenCalled();
    });
    expect(screen.queryByPlaceholderText('hf_...')).not.toBeInTheDocument();
  });

  it('Skip button saves empty token and starts downloads', async () => {
    vi.mocked(api.getSettings).mockResolvedValue({ hf_token: null });
    render(SetupModal);
    await waitFor(() => screen.getByText('Skip'));
    fireEvent.click(screen.getByText('Skip'));
    await waitFor(() => {
      expect(api.startModelDownload).toHaveBeenCalled();
    });
    expect(api.patchSettings).toHaveBeenCalledWith({ hf_token: '' });
  });

  it('Continue button saves token and starts downloads', async () => {
    vi.mocked(api.getSettings).mockResolvedValue({ hf_token: null });
    render(SetupModal);
    await waitFor(() => screen.getByPlaceholderText('hf_...'));
    const input = screen.getByPlaceholderText('hf_...') as HTMLInputElement;
    input.value = 'hf_mytoken';
    fireEvent.input(input);
    fireEvent.click(screen.getByText('Continue'));
    await waitFor(() => {
      expect(api.patchSettings).toHaveBeenCalledWith({ hf_token: 'hf_mytoken' });
      expect(api.startModelDownload).toHaveBeenCalled();
    });
  });

  it('shows downloading status for active entry', async () => {
    vi.mocked(api.getDownloadProgress).mockResolvedValue([
      {
        active: true, model_type: 'siglip', model_id: 'siglip2-base',
        downloaded_bytes: 0, total_bytes: 1000, error: null, complete: false,
      },
    ]);
    render(SetupModal);
    await waitFor(() => {
      expect(screen.getByText('0%')).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('shows error status and retry button for a failed download', async () => {
    vi.mocked(api.getDownloadProgress).mockResolvedValue([
      {
        active: false, model_type: 'siglip', model_id: 'siglip2-base',
        downloaded_bytes: 0, total_bytes: 0, error: 'network error', complete: false,
      },
    ]);
    render(SetupModal);
    await waitFor(() => {
      expect(screen.getByText('failed')).toBeInTheDocument();
      expect(screen.getByText('Retry')).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('Retry button calls startModelDownload with the failed model', async () => {
    vi.mocked(api.getDownloadProgress).mockResolvedValue([
      {
        active: false, model_type: 'siglip', model_id: 'siglip2-base',
        downloaded_bytes: 0, total_bytes: 0, error: 'network error', complete: false,
      },
    ]);
    render(SetupModal);
    await waitFor(() => screen.getByText('Retry'), { timeout: 3000 });
    fireEvent.click(screen.getByText('Retry'));
    await waitFor(() => {
      // 3 calls from beginDownloads + 1 from retry = 4 total
      expect(api.startModelDownload).toHaveBeenCalledTimes(4);
      expect(api.startModelDownload).toHaveBeenLastCalledWith('siglip', 'siglip2-base');
    });
    // Polling resumes after retry: getDownloadProgress should have been called
    expect(api.getDownloadProgress).toHaveBeenCalled();
  });
});
