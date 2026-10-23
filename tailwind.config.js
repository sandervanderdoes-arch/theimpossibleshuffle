// Builds tw.css, the site's Tailwind utilities (replaces the in-browser Tailwind CDN script for speed).
// Rebuild after adding or changing Tailwind classes in index.html:
//   npx tailwindcss@3.4.17 -c tailwind.config.js -i tw-input.css -o tw.css --minify
module.exports = {
  content: ['./index.html'],
  theme: {
    extend: {
      colors: { neonpink: '#ff2fd6', neoncyan: '#22f3ff', neongold: '#ffd23f' },
      fontFamily: {
        display: ['Bungee', 'Impact', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace']
      }
    }
  }
};
