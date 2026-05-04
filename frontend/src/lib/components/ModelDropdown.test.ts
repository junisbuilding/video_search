import { render } from '@testing-library/svelte';
import ModelDropdown from './ModelDropdown.svelte';

describe('ModelDropdown', () => {
  it('renders dropdown trigger', () => {
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
  });
});
