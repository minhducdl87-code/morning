import { defineConfig } from 'vite'

// Dev-only server for the static site (index.html + plain JS/CSS + JSON data).
// Port fixed to 5180 with strictPort so it never drifts onto 3000/5173/5174
// (reserved by other repos). Deployment is unaffected — GitHub Pages serves the
// raw root files; Vite is only used for local `npm run dev`.
export default defineConfig({
  server: {
    port: 5180,
    strictPort: true, // fail loudly if 5180 is taken instead of auto-incrementing
    open: false,
  },
  preview: {
    port: 5180,
    strictPort: true,
  },
})
