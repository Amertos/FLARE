import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  // tailwindcss() compiles the utility classes the screens are written in.
  // Without it the entire UI renders unstyled — every `bg-slate-900`,
  // `grid lg:grid-cols-[1fr_340px]` and `text-[10px]` in src/ is inert.
  plugins: [react(), tailwindcss()],
  server: {
    // This checkout lives on a secondary drive where inotify/ReadDirectoryChangesW
    // events are not delivered reliably: the dev server kept serving a stale
    // module after a file changed on disk. Polling trades a little CPU for HMR
    // that actually fires.
    watch: { usePolling: true, interval: 300 },
  },
})
