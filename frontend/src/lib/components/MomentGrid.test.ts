import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import MomentGrid from './MomentGrid.svelte';
import type { MomentResponse, VideoResultResponse } from '$lib/types';

const makeMoment = (caption: string, timestamp_sec: number): MomentResponse => ({
  timestamp_sec, score: 0.8, thumb_url: null, caption, source: 'caption',
});

const results: VideoResultResponse[] = [
  { video_id: 'v1', path: '/a.mp4', duration_sec: 60, top_score: 0.9, moments: [makeMoment('Dog on beach', 10)] },
  { video_id: 'v2', path: '/b.mp4', duration_sec: 120, top_score: 0.7, moments: [makeMoment('Cat napping', 30)] },
];

describe('MomentGrid', () => {
  it('renders all moments across results', () => {
    render(MomentGrid, { results, activeVideoId: null, activeMomentTimestamp: null });
    expect(screen.getByText('Dog on beach')).toBeInTheDocument();
    expect(screen.getByText('Cat napping')).toBeInTheDocument();
  });

  it('calls onselect when a card is clicked', async () => {
    const onselect = vi.fn();
    render(MomentGrid, { results, activeVideoId: null, activeMomentTimestamp: null, onselect });
    await fireEvent.click(screen.getByText('Dog on beach').closest('article')!);
    expect(onselect).toHaveBeenCalledWith({ videoId: 'v1', frameIdx: null, timestamp: 10 });
  });
});
