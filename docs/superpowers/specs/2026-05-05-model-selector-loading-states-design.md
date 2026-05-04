# Model Selector Loading States and Cache Indicators Design

## Problem

When selecting a non-cached model on the settings page, the download kicks off in the background but there is no UI indication that the model is downloading. Users need visual feedback to understand:
1. Which models are already locally cached
2. When a model is currently downloading
3. The progress of ongoing downloads

## Requirements

- **Dropdown indicators**: Show cache status for each model in the dropdown (color-coded badges)
- **Loading state**: Show loading indicator next to dropdown when a model is downloading
- **Badge text**: Color-coded minimal text (green for cached, gray for not cached, blue for downloading)
- **Loading indicator**: Spinner icon next to dropdown

## Solution

Replace native `<select>` elements with custom dropdown components that provide full control over styling and indicators.

## Architecture

### Components

**ModelDropdown Component** (new)
- Location: `frontend/src/lib/components/ModelDropdown.svelte`
- Props:
  - `type`: string (vision/siglip/text_embedder)
  - `catalog`: ModelCatalogResponse
  - `selectedId`: string
  - `progress`: DownloadProgress | null
  - `onchange`: (id: string) => void
- State:
  - `isOpen`: boolean (dropdown open/closed)
- Renders:
  - Dropdown trigger with selected model label and size
  - Dropdown options with cache status badges
  - Spinner icon when downloading

**Settings Page** (modified)
- Location: `frontend/src/routes/settings/+page.svelte`
- Replace `<select>` elements with `ModelDropdown` components
- Pass catalog, selectedId, progress, and onchange handler
- Remove existing cached/uncached badges (now in dropdown)

### Data Flow

```
Polling (1.5s) → getDownloadProgress() → progress state
Polling (1.5s) → getModelCatalog() → catalog with cache status
ModelDropdown → renders badges based on catalog
ModelDropdown → shows spinner when progress.active && progress.model_type === type
```

### Badge Styling

**Badge Types:**
- **Cached**: Green background (#4ade80), text "Cached"
- **Not cached**: Gray background (#555), text "Not cached"
- **Downloading**: Blue background (#3b82f6), text "Downloading"

**Badge Properties:**
- Small pill-shaped badges
- 8-10px font size
- 4px border radius
- 4px padding (horizontal)
- 2px padding (vertical)

### Loading Indicator

**Spinner Icon:**
- 16x16px size
- Animated rotation
- Positioned to the right of dropdown trigger
- Only visible when that model type is downloading
- Color: #4ade80 (green)

### Error Handling

- If catalog is null, show loading state
- If download progress is null, no loading indicator
- If download fails, show error badge in dropdown (red background, "Error" text)

## Implementation Notes

- Use Svelte's `<select>` element for accessibility, but style it as a custom dropdown
- Or build fully custom dropdown with `<div>` elements for maximum control
- Follow existing design language (colors, fonts, spacing)
- Maintain existing polling behavior (1.5s interval)
- Keep existing progress box below dropdown (shows detailed progress)

## Testing

### Unit Tests

- ModelDropdown component rendering
- Badge rendering for cached/uncached/downloading states
- Loading indicator visibility
- Dropdown open/close behavior
- onchange handler invocation

### Integration Tests

- Settings page with ModelDropdown components
- Badge updates when catalog changes
- Loading indicator appears/disappears with download progress
- Model selection triggers download

### Test Scenarios

1. Select non-cached model → download starts → spinner appears → badge shows "Downloading"
2. Download completes → spinner disappears → badge shows "Cached"
3. Select cached model → badge shows "Cached" → no download starts
4. Multiple models downloading → only one spinner visible at a time
5. Download fails → badge shows "Error" → spinner disappears
