<script lang="ts">
  import { activeVideo } from '$lib/stores';
  import { revealVideo } from '$lib/api';

  let { caption, path }: { caption: string | null; path: string | null } = $props();

  let videoEl: HTMLVideoElement | undefined = $state(undefined);
  let currentVideoId: string | null = $state(null);

  $effect(() => {
    const av = $activeVideo;
    if (!av || !videoEl) return;

    if (av.videoId !== currentVideoId) {
      currentVideoId = av.videoId;
      videoEl.src = `/api/videos/${av.videoId}/stream`;
      videoEl.load();
    }
    videoEl.currentTime = av.timestamp;
    videoEl.play()?.catch(() => {});
  });

  async function handleReveal() {
    if ($activeVideo) {
      await revealVideo($activeVideo.videoId);
    }
  }
</script>

{#if $activeVideo}
  <div class="player" role="region" aria-label="video player">
    <div class="video-area">
      <video
        bind:this={videoEl}
        controls
        class="video-el"
      >
        <track kind="captions" />
      </video>
    </div>
    <div class="player-footer">
      <div class="player-meta">
        {#if path}
          <p class="player-filename">{path.split('/').pop()}</p>
        {/if}
        {#if caption}
          <p class="player-caption">{caption}</p>
        {/if}
      </div>
      <button class="reveal-btn" onclick={handleReveal}>📂 Reveal</button>
    </div>
  </div>
{/if}

<style>
  .player {
    flex: 1;
    background: #111;
    border-radius: 10px;
    border: 1px solid #1e1e1e;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .video-area {
    flex: 1;
    background: #0a0a0a;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 160px;
  }

  .video-el {
    width: 100%;
    height: 100%;
    max-height: 480px;
    object-fit: contain;
  }

  .player-footer {
    padding: 10px 14px;
    border-top: 1px solid #1e1e1e;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }

  .player-meta {
    min-width: 0;
    flex: 1;
  }

  .player-filename {
    font-size: 11px;
    color: #e0e0e0;
    font-weight: 600;
    margin-bottom: 3px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .player-caption {
    font-size: 10px;
    color: #555;
    line-height: 1.4;
  }

  .reveal-btn {
    background: none;
    border: 1px solid #2a2a2a;
    color: #555;
    font-size: 9px;
    padding: 4px 8px;
    border-radius: 4px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .reveal-btn:hover {
    border-color: #4ade80;
    color: #4ade80;
  }
</style>
