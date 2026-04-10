// Backend manager (simplified)
class BackendManager {
    constructor() {
        this.port = parseInt(process.env.PORT || '8000', 10);
    }

    getEnv() {
        return {
            ...process.env,
            PORT: String(this.port),
        };
    }

    getHealthUrl() {
        return `http://127.0.0.1:${this.port}/health`;
    }
}

module.exports = { BackendManager };
