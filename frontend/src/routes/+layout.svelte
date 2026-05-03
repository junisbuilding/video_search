<script lang="ts">
  import type { Snippet } from 'svelte';
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { connectJobsSocket } from '$lib/ws';
  import { getModelCatalog } from '$lib/api';
  import SetupModal from '$lib/components/SetupModal.svelte';

  let { children }: { children: Snippet } = $props();

  let setupNeeded = $state(false);
  let showModal = $state(false);

  onMount(async () => {
    const disconnect = connectJobsSocket();

    try {
      const catalog = await getModelCatalog();
      const anyVisionCached = catalog.vision.some(e => e.cached);
      const anySiglipCached = catalog.siglip.some(e => e.cached);
      const anyTeCached = catalog.text_embedder.some(e => e.cached);
      setupNeeded = !(anyVisionCached && anySiglipCached && anyTeCached);

      if (catalog.first_run && !localStorage.getItem('setup_seen')) {
        showModal = true;
      }
    } catch {
      // Server not ready — don't block app
    }

    return disconnect;
  });

  function isActive(pathname: string, href: string): boolean {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  }

  const navItems = [
    { label: 'Search', href: '/' },
    { label: 'Library', href: '/library' },
    { label: 'Jobs', href: '/jobs' },
    { label: 'Settings', href: '/settings' },
  ];
</script>

{#if showModal}
  <SetupModal />
{/if}

<div class="app">
  <nav class="navbar">
    <div class="logo">
      <div class="logo-square" aria-hidden="true"></div>
      <span class="logo-text">VIDEOSEARCH</span>
    </div>
    <div class="nav-links">
      {#each navItems as item}
        <a
          href={item.href}
          class="nav-link"
          class:active={isActive(page.url.pathname, item.href)}
          aria-current={isActive(page.url.pathname, item.href) ? 'page' : undefined}
        >
          {item.label}
          {#if item.href === '/settings' && setupNeeded}
            <span class="setup-dot" aria-label="Setup required"></span>
          {/if}
        </a>
      {/each}
    </div>
  </nav>

  <main class="main-content">
    {@render children()}
  </main>
</div>

<style>
  :global(*) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :global(body) {
    background: #0d0d0d;
    color: #e0e0e0;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 14px;
    min-height: 100vh;
  }

  :global(button) {
    cursor: pointer;
    font-family: inherit;
    font-size: inherit;
  }

  .app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  .navbar {
    background: #111;
    border-bottom: 1px solid #1e1e1e;
    padding: 10px 20px;
    display: flex;
    align-items: center;
    gap: 20px;
    flex-shrink: 0;
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .logo-square {
    width: 20px;
    height: 20px;
    background: #4ade80;
    border-radius: 4px;
  }

  .logo-text {
    font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro', monospace;
    font-size: 11px;
    color: #4ade80;
    font-weight: 700;
    letter-spacing: 0.08em;
  }

  .nav-links {
    margin-left: auto;
    display: flex;
    gap: 20px;
    align-items: center;
  }

  .nav-link {
    font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro', monospace;
    font-size: 11px;
    color: #555;
    text-decoration: none;
    padding-bottom: 2px;
    position: relative;
  }

  .nav-link.active {
    color: #4ade80;
    border-bottom: 1px solid #4ade80;
  }

  .nav-link:not(.active):hover {
    color: #888;
  }

  .setup-dot {
    position: absolute;
    top: -3px;
    right: -7px;
    width: 5px;
    height: 5px;
    background: #f59e0b;
    border-radius: 50%;
    display: inline-block;
  }

  .main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
</style>
