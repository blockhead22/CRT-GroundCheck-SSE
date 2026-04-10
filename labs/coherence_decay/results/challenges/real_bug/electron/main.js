// Electron main process (simplified for bug challenge)
const { app } = require('electron');

class Backend {
    constructor() {
        // BUG: reads PORT from process.env, which is empty
        // Defaults to 8000, but backend runs on 8123 (from .env)
        this.port = parseInt(process.env.PORT || '8000', 10);
        this.healthUrl = `http://127.0.0.1:${this.port}/health`;
    }

    async checkHealth() {
        try {
            const resp = await fetch(this.healthUrl);
            return resp.ok;
        } catch {
            return false;
        }
    }

    async waitForStartup(timeoutMs = 120000) {
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            if (await this.checkHealth()) {
                console.log('[ELECTRON] Backend healthy');
                return true;
            }
            await new Promise(r => setTimeout(r, 1000));
        }
        console.log('[ELECTRON] Startup timeout');
        return false;
    }
}

app.on('ready', async () => {
    const backend = new Backend();
    // Spawn Python backend (it reads .env and uses PORT=8123)
    // spawn('python', ['crt_api.py']);

    const healthy = await backend.waitForStartup();
    if (!healthy) {
        console.log('[ELECTRON] Backend failed to start');
        // app.quit();
    }
});
