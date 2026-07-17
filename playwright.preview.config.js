const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/ui-production',
  timeout: 30_000,
  reporter: 'line',
  use: {
    baseURL: 'http://127.0.0.1:5182',
    trace: 'retain-on-failure'
  },
  webServer: {
    command: 'npm run preview -- --host 127.0.0.1 --port 5182 --strictPort',
    url: 'http://127.0.0.1:5182',
    reuseExistingServer: false,
    timeout: 30_000
  }
});
