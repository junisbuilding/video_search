import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import FolderPicker from './FolderPicker.svelte';
import * as api from '$lib/api';

vi.mock('$lib/api');

const homeFs = {
  path: '/home/user',
  parent: null,
  entries: [
    { name: 'videos', path: '/home/user/videos', kind: 'dir' as const, size_bytes: null, mtime: 0 },
    { name: 'movie.mp4', path: '/home/user/movie.mp4', kind: 'video' as const, size_bytes: 1024, mtime: 0 },
    { name: 'readme.txt', path: '/home/user/readme.txt', kind: 'other' as const, size_bytes: 100, mtime: 0 },
  ],
};

beforeEach(() => {
  vi.mocked(api.listFs).mockResolvedValue(homeFs);
});

describe('FolderPicker', () => {
  it('shows current path on load', async () => {
    render(FolderPicker, { onconfirm: vi.fn(), oncancel: vi.fn() });
    await screen.findByText('/home/user');
  });

  it('lists directories and video files', async () => {
    render(FolderPicker, { onconfirm: vi.fn(), oncancel: vi.fn() });
    await screen.findByText('videos');
    expect(screen.getByText('movie.mp4')).toBeInTheDocument();
    expect(screen.queryByText('readme.txt')).not.toBeInTheDocument();
  });

  it('navigates into a directory on click', async () => {
    const subFs = { path: '/home/user/videos', parent: '/home/user', entries: [] };
    vi.mocked(api.listFs).mockResolvedValueOnce(homeFs).mockResolvedValueOnce(subFs);
    render(FolderPicker, { onconfirm: vi.fn(), oncancel: vi.fn() });
    await screen.findByText('videos');
    await fireEvent.click(screen.getByText('videos'));
    await screen.findByText('/home/user/videos');
  });

  it('navigates to parent on ".." click', async () => {
    const subFs = { path: '/home/user/videos', parent: '/home/user', entries: [] };
    vi.mocked(api.listFs).mockResolvedValueOnce(subFs);
    render(FolderPicker, { onconfirm: vi.fn(), oncancel: vi.fn() });
    await screen.findByText('/home/user/videos');
    vi.mocked(api.listFs).mockResolvedValueOnce(homeFs);
    await fireEvent.click(screen.getByText('..'));
    await screen.findByText('/home/user');
  });

  it('calls onconfirm with current path on "Add this folder"', async () => {
    const onconfirm = vi.fn();
    render(FolderPicker, { onconfirm, oncancel: vi.fn() });
    await screen.findByText('/home/user');
    await fireEvent.click(screen.getByText('Add this folder'));
    expect(onconfirm).toHaveBeenCalledWith('/home/user');
  });

  it('calls oncancel on "Cancel"', async () => {
    const oncancel = vi.fn();
    render(FolderPicker, { onconfirm: vi.fn(), oncancel });
    await screen.findByText('/home/user');
    await fireEvent.click(screen.getByText('Cancel'));
    expect(oncancel).toHaveBeenCalled();
  });
});
