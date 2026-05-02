<script lang="ts">
  import type { VideoResultResponse, MomentResponse } from '$lib/types';
  import MomentCard from './MomentCard.svelte';

  let {
    results,
    activeVideoId,
    activeMomentTimestamp,
    onselect,
  }: {
    results: VideoResultResponse[];
    activeVideoId: string | null;
    activeMomentTimestamp: number | null;
    onselect?: (selection: { videoId: string; frameIdx: number | null; timestamp: number }) => void;
  } = $props();

  function handleSelect(videoId: string, moment: MomentResponse) {
    onselect?.({
      videoId,
      frameIdx: null,
      timestamp: moment.timestamp_sec,
    });
  }

  function isSelected(videoId: string, moment: MomentResponse): boolean {
    return activeVideoId === videoId && activeMomentTimestamp === moment.timestamp_sec;
  }

  function filename(path: string): string {
    return path.split('/').pop() ?? path;
  }
</script>

<div class="grid">
  {#each results as result}
    {#each result.moments as moment}
      <MomentCard
        {moment}
        filename={filename(result.path)}
        selected={isSelected(result.video_id, moment)}
        onselect={() => handleSelect(result.video_id, moment)}
      />
    {/each}
  {/each}
</div>

<style>
  .grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow-y: auto;
    width: 240px;
    flex-shrink: 0;
  }
</style>
