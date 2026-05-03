// frontend/src/routes/settings/page.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import * as api from '$lib/api';

vi.mock('$lib/api');
vi.mock('$app/state', () => ({ page: { url: { pathname: '/settings' } } }));

const mockCatalog = {
  first_run: false,
  active_models: { vision: 'moondream2', siglip: 'siglip2-base', text_embedder: 'bge-small-en' },
  vision: [
    { id: 'moondream2', label: 'moondream2', size_label: '~2 GB', cached: true, default: true },
    { id: 'llava-1.5-7b', label: 'LLaVA 1.5 · 7B', size_label: '~4 GB', cached: false, default: false },
  ],
  siglip: [
    { id: 'siglip2-base', label: 'SigLIP Base', size_label: '~1.2 GB', cached: true, default: true },
  ],
  text_embedder: [
    { id: 'bge-small-en', label: 'BGE Small (English)', size_label: '~130 MB', cached: true, default: true },
  ],
};

const mockSettings = {
  frame_fps: 1.0,
  scene_detection: true,
  port: 8083,
  siglip_model: 'google/siglip2-base-patch16-256',
  text_embedder: 'BAAI/bge-small-en-v1.5',
  vlm_model: 'moondream/moondream2-gguf::moondream2-text-model-f16.gguf',
  vlm_mmproj: 'moondream/moondream2-gguf::moondream2-mmproj-f16.gguf',
  vlm_n_gpu_layers: -1,
};

const idleProgress = {
  active: false, model_type: '', model_id: '', downloaded_bytes: 0, total_bytes: 0, error: null, complete: false,
};

beforeEach(() => {
  vi.mocked(api.getModelCatalog).mockResolvedValue(mockCatalog);
  vi.mocked(api.getSettings).mockResolvedValue(mockSettings);
  vi.mocked(api.getDownloadProgress).mockResolvedValue(idleProgress);
  vi.mocked(api.patchSettings).mockResolvedValue({});
  vi.mocked(api.startModelDownload).mockResolvedValue({ queued: true });
});

describe('Settings page', () => {
  it('shows Vision model section heading', async () => {
    render(Page);
    await waitFor(() => expect(screen.getByText('Vision model')).toBeInTheDocument());
  });

  it('shows Image understanding section heading', async () => {
    render(Page);
    await waitFor(() => expect(screen.getByText('Image understanding')).toBeInTheDocument());
  });

  it('shows Search model section heading', async () => {
    render(Page);
    await waitFor(() => expect(screen.getByText('Search model')).toBeInTheDocument());
  });

  it('shows cached indicator for cached model', async () => {
    render(Page);
    await waitFor(() => expect(screen.getAllByText(/Cached/i).length).toBeGreaterThan(0));
  });

  it('shows Advanced options accordion', async () => {
    render(Page);
    await waitFor(() => expect(screen.getByText(/Advanced options/i)).toBeInTheDocument());
  });

  it('FPS input is inside the advanced accordion (not visible by default)', async () => {
    render(Page);
    await waitFor(() => screen.getByText(/Advanced options/i));
    const details = screen.getByRole('group');
    expect(details).not.toHaveAttribute('open');
  });

  it('patching advanced fields uses Save button', async () => {
    render(Page);
    await waitFor(() => screen.getByText(/Advanced options/i));
    await fireEvent.click(screen.getByText(/Advanced options/i));
    const fpsInput = await screen.findByLabelText(/frames per second/i);
    await fireEvent.input(fpsInput, { target: { value: '2' } });
    const saveBtn = screen.getByRole('button', { name: /save/i });
    await fireEvent.click(saveBtn);
    await waitFor(() => expect(api.patchSettings).toHaveBeenCalledWith(expect.objectContaining({ frame_fps: 2 })));
  });

  it('shows requires-restart hint for port', async () => {
    render(Page);
    await waitFor(() => screen.getByText(/Advanced options/i));
    await fireEvent.click(screen.getByText(/Advanced options/i));
    await waitFor(() => expect(screen.getAllByText(/requires restart/i).length).toBeGreaterThan(0));
  });
});
