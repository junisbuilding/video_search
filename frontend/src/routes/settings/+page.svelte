<script lang="ts">
  import { onMount } from 'svelte';
  import { getSettings, patchSettings } from '$lib/api';

  type FieldValue = string | number | boolean | null;
  type Settings = Record<string, FieldValue>;

  let original = $state<Settings>({});
  let current = $state<Settings>({});
  let saving = $state(false);
  let saved = $state(false);

  onMount(async () => {
    const s = await getSettings();
    original = { ...s } as Settings;
    current = { ...s } as Settings;
  });

  function touched(): Partial<Settings> {
    const patch: Partial<Settings> = {};
    for (const key of Object.keys(current)) {
      if (current[key] !== original[key]) {
        patch[key] = current[key];
      }
    }
    return patch;
  }

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault();
    saving = true;
    try {
      const patch = touched();
      if ('frame_fps' in patch) patch.frame_fps = Number(patch.frame_fps);
      if ('port' in patch) patch.port = Number(patch.port);
      if ('vlm_n_gpu_layers' in patch) patch.vlm_n_gpu_layers = Number(patch.vlm_n_gpu_layers);
      await patchSettings(patch as Record<string, unknown>);
      original = { ...current };
      saved = true;
      setTimeout(() => (saved = false), 2000);
    } finally {
      saving = false;
    }
  }
</script>

<div class="page">
  <div class="page-header">
    <h1 class="page-title">Settings</h1>
  </div>

  <form class="settings-form" onsubmit={handleSubmit} role="form">
    <div class="field">
      <label class="label" for="frame_fps">Frames per second</label>
      <input
        id="frame_fps"
        class="input"
        type="number"
        step="0.5"
        min="0.1"
        bind:value={current.frame_fps}
      />
    </div>

    <div class="field">
      <label class="label" for="scene_detection">
        <input
          id="scene_detection"
          type="checkbox"
          bind:checked={current.scene_detection as boolean}
        />
        Scene detection
      </label>
    </div>

    <div class="field">
      <label class="label" for="port">
        Port
        <span class="restart-hint">⚠ requires restart</span>
      </label>
      <input id="port" class="input" type="number" bind:value={current.port} />
    </div>

    <div class="field">
      <label class="label" for="siglip_model">
        SigLIP model
        <span class="restart-hint">⚠ requires restart</span>
      </label>
      <input id="siglip_model" class="input" type="text" bind:value={current.siglip_model as string} />
    </div>

    <div class="field">
      <label class="label" for="text_embedder">
        Text embedder
        <span class="restart-hint">⚠ requires restart</span>
      </label>
      <input id="text_embedder" class="input" type="text" bind:value={current.text_embedder as string} />
    </div>

    <div class="field">
      <label class="label" for="vlm_model">
        VLM model path
        <span class="restart-hint">⚠ requires restart</span>
      </label>
      <input id="vlm_model" class="input" type="text" bind:value={current.vlm_model as string} placeholder="GGUF path or HF repo" />
    </div>

    <div class="field">
      <label class="label" for="vlm_mmproj">
        VLM mmproj path
        <span class="restart-hint">⚠ requires restart</span>
      </label>
      <input id="vlm_mmproj" class="input" type="text" bind:value={current.vlm_mmproj as string} placeholder="mmproj path" />
    </div>

    <div class="field">
      <label class="label" for="vlm_n_gpu_layers">GPU layers (-1 = all)</label>
      <input id="vlm_n_gpu_layers" class="input" type="number" bind:value={current.vlm_n_gpu_layers} />
    </div>

    <div class="form-footer">
      {#if saved}
        <span class="saved-msg">Saved.</span>
      {/if}
      <button class="btn-save" type="submit" disabled={saving}>
        {saving ? 'Saving…' : 'Save'}
      </button>
    </div>
  </form>
</div>

<style>
  .page {
    padding: 24px 20px;
    flex: 1;
    max-width: 560px;
  }

  .page-header {
    margin-bottom: 24px;
  }

  .page-title {
    font-size: 16px;
    color: #e0e0e0;
    font-weight: 600;
  }

  .settings-form {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  .label {
    font-size: 11px;
    color: #888;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .restart-hint {
    font-size: 9px;
    color: #f59e0b;
  }

  .input {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 12px;
    color: #e0e0e0;
    font-family: inherit;
    outline: none;
    width: 100%;
  }

  .input:focus {
    border-color: #4ade80;
  }

  .form-footer {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 12px;
    padding-top: 8px;
  }

  .saved-msg {
    font-size: 11px;
    color: #4ade80;
  }

  .btn-save {
    background: #4ade80;
    border: none;
    color: #000;
    font-size: 11px;
    font-weight: 700;
    padding: 7px 18px;
    border-radius: 6px;
  }

  .btn-save:disabled {
    opacity: 0.5;
  }
</style>
