import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import MomentCard from './MomentCard.svelte';
import type { MomentResponse } from '$lib/types';

const moment: MomentResponse = {
  timestamp_sec: 42.5,
  score: 0.9,
  thumb_url: null,
  caption: 'A dog runs on the beach',
  source: 'caption',
};

describe('MomentCard', () => {
  it('renders the caption', () => {
    render(MomentCard, { moment });
    expect(screen.getByText('A dog runs on the beach')).toBeInTheDocument();
  });

  it('renders the timestamp formatted as m:ss', () => {
    render(MomentCard, { moment });
    expect(screen.getByText('0:42')).toBeInTheDocument();
  });

  it('calls onselect when clicked', async () => {
    const onselect = vi.fn();
    render(MomentCard, { moment, onselect });
    await fireEvent.click(screen.getByRole('article'));
    expect(onselect).toHaveBeenCalledOnce();
  });

  it('applies selected class when selected=true', () => {
    render(MomentCard, { moment, selected: true });
    expect(screen.getByRole('article')).toHaveClass('selected');
  });

  it('renders thumbnail image when thumb_url is set', () => {
    const momentWithThumb = { ...moment, thumb_url: '/api/videos/v1/thumbs/10' };
    render(MomentCard, { moment: momentWithThumb });
    expect(screen.getByRole('img')).toHaveAttribute('src', '/api/videos/v1/thumbs/10');
  });
});
