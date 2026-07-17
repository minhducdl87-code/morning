import { copyFile, mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'

const runtimeFiles = [
  'date-week-utils.js',
  'renderers.js',
  'view-builder.js',
  'router-init.js',
  'config.json',
  'cards.json',
  'weekly.json',
  'monthly.json',
  '_headers',
]

function copyStaticRuntime() {
  return {
    name: 'copy-static-runtime',
    apply: 'build',
    async closeBundle() {
      const outputDir = resolve('dist')
      await mkdir(outputDir, { recursive: true })
      await Promise.all(runtimeFiles.map(file => copyFile(resolve(file), resolve(outputDir, file))))
    },
  }
}

// Dev-only server for the static site (index.html + plain JS/CSS + JSON data).
// Port fixed to 5180 with strictPort so it never drifts onto 3000/5173/5174
// (reserved by other repos). Deployment is unaffected — GitHub Pages serves the
// raw root files; Vite is only used for local `npm run dev`.
export default defineConfig({
  plugins: [copyStaticRuntime()],
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
