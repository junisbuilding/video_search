import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import ModelDropdown from './ModelDropdown.svelte';

describe('ModelDropdown', () => {
  it('renders dropdown trigger with selected model', () => {
    const catalog = {
      vision: [{ id: 'model1', label: 'Model 1', size_label: '1 GB', cached: false, default: true }],
      siglip: [],
      text_embedder: [],
      active_models: { vision: '', siglip: '', text_embedder: '' },
      first_run: false
    };
    const { container } = render(ModelDropdown, {
      props: {
        type: 'vision',
        catalog,
        selectedId: 'model1',
        progress: null,
        onchange: () => {}
      }
    });
    expect(container).toBeTruthy();
    expect(screen.getByText('Model 1')).toBeTruthy();
    expect(screen.getByText('1 GB')).toBeTruthy();
  });

  it('renders dropdown trigger with default text when no model selected', () => {
    const catalog = {
      vision: [{ id: 'model1', label: 'Model 1', size_label: '1 GB', cached: false, default: true }],
      siglip: [],
      text_embedder: [],
      active_models: { vision: '', siglip: '', text_embedder: '' },
      first_run: false
    };
    render(ModelDropdown, {
      props: {
        type: 'vision',
        catalog,
        selectedId: '',
        progress: null,
        onchange: () => {}
      }
    });
    expect(screen.getByText('Select model')).toBeTruthy();
  });

  it('renders badge elements for model status', () => {
    const catalog = {
      vision: [
        { id: 'model1', label: 'Model 1', size_label: '1 GB', cached: true, default: true },
        { id: 'model2', label: 'Model 2', size_label: '2 GB', cached: false, default: false }
      ],
      siglip: [],
      text_embedder: [],
      active_models: { vision: '', siglip: '', text_embedder: '' },
      first_run: false
    };
    const { container } = render(ModelDropdown, {
      props: {
        type: 'vision',
        catalog,
        selectedId: 'model1',
        progress: null,
        onchange: () => {}
      }
    });
    expect(container).toBeTruthy();
  });

  it('closes dropdown when clicking outside', async () => {
    const catalog = {
      vision: [{ id: 'model1', label: 'Model 1', size_label: '1 GB', cached: false, default: true }],
      siglip: [],
      text_embedder: [],
      active_models: { vision: '', siglip: '', text_embedder: '' },
      first_run: false
    };
    const { container } = render(ModelDropdown, {
      props: {
        type: 'vision',
        catalog,
        selectedId: 'model1',
        progress: null,
        onchange: () => {}
      }
    });

    const trigger = container.querySelector('.dropdown-trigger') as HTMLElement;
    trigger?.click();

    await new Promise(resolve => setTimeout(resolve, 0));

    const options = container.querySelector('.dropdown-options');
    expect(options).toBeTruthy();

    document.body.click();

    await new Promise(resolve => setTimeout(resolve, 0));

    const optionsAfter = container.querySelector('.dropdown-options');
    expect(optionsAfter).toBeFalsy();
  });

  it('supports keyboard navigation', async () => {
    const catalog = {
      vision: [
        { id: 'model1', label: 'Model 1', size_label: '1 GB', cached: false, default: true },
        { id: 'model2', label: 'Model 2', size_label: '2 GB', cached: false, default: false }
      ],
      siglip: [],
      text_embedder: [],
      active_models: { vision: '', siglip: '', text_embedder: '' },
      first_run: false
    };
    let selectedId = 'model1';
    const { container } = render(ModelDropdown, {
      props: {
        type: 'vision',
        catalog,
        selectedId,
        progress: null,
        onchange: (id: string) => { selectedId = id; }
      }
    });

    const trigger = container.querySelector('.dropdown-trigger') as HTMLElement;
    fireEvent.keyDown(trigger, { key: 'Enter' });

    await new Promise(resolve => setTimeout(resolve, 0));

    const options = container.querySelectorAll('.dropdown-option');
    expect(options.length).toBe(2);

    const firstOption = options[0] as HTMLElement;
    fireEvent.keyDown(firstOption, { key: 'ArrowDown' });

    await new Promise(resolve => setTimeout(resolve, 0));

    const secondOption = options[1] as HTMLElement;
    fireEvent.keyDown(secondOption, { key: 'Enter' });

    await new Promise(resolve => setTimeout(resolve, 0));

    expect(selectedId).toBe('model2');
  });

  it('renders error badge for failed downloads', async () => {
    const catalog = {
      vision: [{ id: 'model1', label: 'Model 1', size_label: '1 GB', cached: false, default: true }],
      siglip: [],
      text_embedder: [],
      active_models: { vision: '', siglip: '', text_embedder: '' },
      first_run: false
    };
    const progress = {
      active: false,
      model_type: 'vision',
      model_id: 'model1',
      downloaded_bytes: 0,
      total_bytes: 1000000000,
      error: 'Download failed: network error',
      complete: false
    };
    const { container } = render(ModelDropdown, {
      props: {
        type: 'vision',
        catalog,
        selectedId: 'model1',
        progress,
        onchange: () => {}
      }
    });

    const trigger = container.querySelector('.dropdown-trigger') as HTMLElement;
    trigger?.click();

    await new Promise(resolve => setTimeout(resolve, 0));

    const badge = container.querySelector('.option-badge');
    expect(badge?.textContent).toBe('Error');
    expect(badge?.getAttribute('style')).toContain('rgb(239, 68, 68)');
  });
});
