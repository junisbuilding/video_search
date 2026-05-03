# HF Token Design

**Goal:** Fix stalled download progress and improve download speeds by supporting a Hugging Face token — read from env, prompted in SetupModal on first launch, persisted in settings.

**Problem:** Without authentication, `hf_hub_download` goes through an unauthenticated redirect chain before bytes start flowing, causing a long 0 B/s stall. With a token, downloads start immediately and are rate-limit-free.

**Non-goals:** OAuth flow, token validation UI, token rotation, multi-user support.

---

## Architecture

Three layers of changes:

1. **Backend** — `Settings` + `ModelDownloader`: token flows from config → downloader → HF Hub calls
2. **API** — `SettingsPatch` + settings response: frontend can read and save the token
3. **Frontend** — `SetupModal`: gated token input step before downloads start

---

## Section 1: Backend

### `src/videosearch/config.py`

Add field:
```python
hf_token: str | None = None
```

In `load_config`, after reading `VS_*` env vars, also check bare `HF_TOKEN` as a fallback (huggingface_hub's standard env var name):
```python
if "HF_TOKEN" in os.environ and "hf_token" not in env_data:
    env_data["hf_token"] = os.environ["HF_TOKEN"]
```

Precedence: `VS_HF_TOKEN` > `HF_TOKEN` > `config.toml` > default (`None`).

### `src/videosearch/models/downloader.py`

`ModelDownloader.__init__` signature change:
```python
def __init__(self, models_dir: Path, token: str | None = None) -> None:
    self._token = token
    ...
```

All `hf_hub_download` and `snapshot_download` calls add `token=self._token`:
```python
hf_hub_download(repo, file, cache_dir=..., tqdm_class=tqdm_cls, token=self._token)
snapshot_download(entry.hf_repo, tqdm_class=tqdm_cls, token=self._token)
```

### `src/videosearch/api/app.py`

Pass token when constructing downloader:
```python
downloader = ModelDownloader(settings.models_dir, token=settings.hf_token)
```

---

## Section 2: API

### `src/videosearch/api/routers/settings.py`

Add `hf_token` to `SettingsPatch`:
```python
class SettingsPatch(BaseModel, extra="ignore"):
    ...
    hf_token: str | None = None
```

Change `_settings_to_toml_dict` to always include `hf_token` in the response (even when `None`), so the frontend can reliably check for its presence. Add this after the existing loop:
```python
result["hf_token"] = s.hf_token  # explicit: include even when None
```
All other None fields continue to be skipped by the existing loop.

### `frontend/src/lib/types.ts`

Add `hf_token` to `SettingsPatch`:
```typescript
export interface SettingsPatch {
  ...
  hf_token?: string | null;
}
```

---

## Section 3: Frontend

### `frontend/src/lib/components/SetupModal.svelte`

Add `step: 'token' | 'downloading'` state. Add `tokenInput: string` state for the controlled input.

**On mount:**
1. Fetch catalog and settings in parallel
2. If `settings.hf_token !== null` → `step = 'downloading'`, enqueue defaults, start polling
3. If `settings.hf_token === null` → `step = 'token'`, wait for user action

**Token step UI:**
```
"Speed up downloads"
"A Hugging Face token enables faster, authenticated downloads. Free at huggingface.co."
[input type=password placeholder="hf_..."]
[Skip]  [Continue]
```

**Continue:** `PATCH /api/settings` with `{ hf_token: tokenInput }` → `step = 'downloading'` → enqueue + poll  
**Skip:** `step = 'downloading'` → enqueue + poll (no token saved)

**Downloading step:** identical to current modal behaviour.

---

## Files changed

| File | Action |
|---|---|
| `src/videosearch/config.py` | Add `hf_token` field + `HF_TOKEN` env fallback in `load_config` |
| `src/videosearch/models/downloader.py` | Add `token` param, pass to all HF Hub calls |
| `src/videosearch/api/app.py` | Pass `token=settings.hf_token` to `ModelDownloader` |
| `src/videosearch/api/routers/settings.py` | Add `hf_token` to `SettingsPatch`, always return in response |
| `frontend/src/lib/types.ts` | Add `hf_token` to `SettingsPatch` interface |
| `frontend/src/lib/components/SetupModal.svelte` | Add token step before downloads |

---

## Testing

**Backend:**
- `test_hf_token_from_env` — `HF_TOKEN` in env → `settings.hf_token` set
- `test_vs_hf_token_overrides_hf_token` — `VS_HF_TOKEN` wins over `HF_TOKEN`
- `test_downloader_passes_token_to_hf_hub_download` — mock `hf_hub_download`, assert `token=` passed
- `test_settings_response_includes_hf_token_when_null` — `GET /api/settings` returns `hf_token: null`
- `test_patch_settings_saves_hf_token` — `PATCH /api/settings` with `hf_token` persists it

**Frontend (Vitest):**
- `shows token step when hf_token is null` — renders token input, not progress bars
- `skips token step when hf_token is set` — goes straight to downloading step
- `Continue saves token and transitions` — calls `patchSettings`, then `startModelDownload`
- `Skip transitions without saving token` — skips `patchSettings`, proceeds to download
