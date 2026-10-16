import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // This checkout lives on a secondary drive where inotify/ReadDirectoryChangesW
    // events are not delivered reliably: the dev server kept serving a stale
    // module after a file changed on disk. Polling trades a little CPU for HMR
    // that actually fires.
    watch: { usePolling: true, interval: 300 },
  },
})
