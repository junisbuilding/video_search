import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import { tick } from 'svelte';
import VideoPlayer from './VideoPlayer.svelte';
import { activeVideo } from '$lib/stores';
import * as api from '$lib/api';

vi.mock('$lib/api');

beforeEach(() => {
  activeVideo.set(null);
  vi.mocked(api.revealVideo).mockResolvedValue(undefined);
});

describe('VideoPlayer', () => {
  it('renders nothing when activeVideo is null', () => {
    render(VideoPlayer, { caption: null, path: null });
    expect(screen.queryByRole('region')).not.toBeInTheDocument();
  });

  it('seeks to timestamp when activeVideo changes', async () => {
    const seekSpy = vi.spyOn(HTMLMediaElement.prototype, 'currentTime', 'set');
    render(VideoPlayer, { caption: null, path: '/video.mp4' });

    activeVideo.set({ videoId: 'v1', frameIdx: null, timestamp: 42.5 });
    await tick();

    expect(seekSpy).toHaveBeenCalledWith(42.5);
  });

  it('shows Reveal button and calls revealVideo on click', async () => {
    render(VideoPlayer, { caption: 'A dog', path: '/video.mp4' });
    activeVideo.set({ videoId: 'v1', frameIdx: null, timestamp: 10 });
    await tick();

    const btn = await screen.findByText(/reveal/i);
    await fireEvent.click(btn);
    expect(api.revealVideo).toHaveBeenCalledWith('v1');
  });

  it('shows caption below player', async () => {
    render(VideoPlayer, { caption: 'A dog on the beach', path: '/video.mp4' });
    activeVideo.set({ videoId: 'v1', frameIdx: null, timestamp: 10 });
    await tick();
    expect(screen.getByText('A dog on the beach')).toBeInTheDocument();
  });
});
