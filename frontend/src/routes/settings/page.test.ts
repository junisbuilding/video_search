import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import * as api from '$lib/api';

vi.mock('$lib/api');
vi.mock('$app/state', () => ({ page: { url: { pathname: '/settings' } } }));

beforeEach(() => {
  vi.mocked(api.getSettings).mockResolvedValue({
    frame_fps: 1.0,
    scene_detection: true,
    port: 8083,
    siglip_model: 'google/siglip2-base-patch16-256',
    text_embedder: 'BAAI/bge-small-en-v1.5',
    vlm_model: null,
    vlm_mmproj: null,
    vlm_n_gpu_layers: -1,
  });
  vi.mocked(api.patchSettings).mockResolvedValue({ frame_fps: 2.0 });
});

describe('Settings page', () => {
  it('loads and shows current frame_fps', async () => {
    render(Page);
    const input = await screen.findByLabelText(/frames per second/i);
    expect((input as HTMLInputElement).value).toBe('1');
  });

  it('submits only changed fields', async () => {
    render(Page);
    const input = await screen.findByLabelText(/frames per second/i);
    await fireEvent.input(input, { target: { value: '2' } });
    await fireEvent.submit(screen.getByRole('form'));
    await waitFor(() => expect(api.patchSettings).toHaveBeenCalledWith({ frame_fps: 2 }));
  });

  it('does not submit unchanged fields', async () => {
    render(Page);
    await screen.findByLabelText(/frames per second/i);
    await fireEvent.submit(screen.getByRole('form'));
    await waitFor(() => expect(api.patchSettings).toHaveBeenCalledWith({}));
  });

  it('shows requires-restart hint for port field', async () => {
    render(Page);
    await screen.findByLabelText(/port/i);
    expect(screen.getAllByText(/requires restart/i).length).toBeGreaterThan(0);
  });
});
