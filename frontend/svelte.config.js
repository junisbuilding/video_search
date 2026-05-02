import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: '../src/videosearch/static',
      assets: '../src/videosearch/static',
      fallback: 'index.html',
      precompress: false,
    }),
  },
};
