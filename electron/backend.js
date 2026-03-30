/**
 * Backend process manager for Aether.
 * Spawns crt_api.py as a child process, monitors health, auto-restarts on crash.
 */

const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const { EventEmitter } = require('events');

const MAX_RESTARTS = 5;
const HEALTH_INTERVAL_MS = 30000;   // Check every 30s (was 10s — reduced to cut log spam)
const HEALTH_TIMEOUT_MS = 5000;     // Allow 5s for response (backend may be busy with Ollama)
const STARTUP_TIMEOUT_MS = 120000;
const UNHEALTHY_THRESHOLD = 3;      // Require 3 consecutive failures before marking unhealthy

class BackendManager extends EventEmitter {
  constructor(repoRoot) {
    super();
    this.repoRoot = repoRoot;
    this.process = null;
    this.restartCount = 0;
    this.healthy = false;
    this.healthTimer = null;
    this.startupTimer = null;
    this.shuttingDown = false;
    this.port = parseInt(process.env.PORT || '8000', 10);
    this.host = process.env.CRT_HOST || '127.0.0.1';
    this.failCount = 0;
  }

  /** Resolve the Python executable inside the venv */
  getPythonPath() {
    if (process.platform === 'win32') {
      return path.join(this.repoRoot, '.venv', 'Scripts', 'python.exe');
    }
    return path.join(this.repoRoot, '.venv', 'bin', 'python');
  }

  /** Environment variables for the backend (mirrors start_api.ps1) */
  getEnv() {
    return {
      ...process.env,
      PORT: String(this.port),
      CRT_HOST: this.host,
      CRT_CORS_ORIGINS: [
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:5174',
        'http://127.0.0.1:5174',
        'app://aether',
      ].join(','),
      CRT_SHARED_MEMORY: 'true',
      CRT_ENABLE_LLM: 'true',
      CRT_OLLAMA_MODEL: process.env.CRT_OLLAMA_MODEL || 'qwen3:14b',
      OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://192.168.1.146:11434',
      CRT_INTENT_MODEL: process.env.CRT_INTENT_MODEL || 'llama3.2',
      HF_HUB_OFFLINE: '1',
      TRANSFORMERS_OFFLINE: '1',
    };
  }

  /** Start the backend process */
  start() {
    if (this.process) {
      console.log('[backend] Already running, pid:', this.process.pid);
      return;
    }

    this.shuttingDown = false;
    const pythonPath = this.getPythonPath();
    const scriptPath = path.join(this.repoRoot, 'crt_api.py');

    console.log(`[backend] Starting: ${pythonPath} ${scriptPath}`);
    this.emit('status', 'starting');

    this.process = spawn(pythonPath, [scriptPath], {
      cwd: this.repoRoot,
      env: this.getEnv(),
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    });

    this.process.stdout.on('data', (data) => {
      const line = data.toString().trim();
      if (line) {
        console.log(`[backend:out] ${line}`);
        this.emit('log', { stream: 'stdout', text: line });
      }
    });

    this.process.stderr.on('data', (data) => {
      const line = data.toString().trim();
      if (line) {
        console.error(`[backend:err] ${line}`);
        this.emit('log', { stream: 'stderr', text: line });
      }
    });

    this.process.on('exit', (code, signal) => {
      console.log(`[backend] Exited: code=${code}, signal=${signal}`);
      this.process = null;
      this.healthy = false;
      this.emit('status', 'stopped');
      this.stopHealthCheck();

      if (!this.shuttingDown && this.restartCount < MAX_RESTARTS) {
        this.restartCount++;
        console.log(`[backend] Auto-restart ${this.restartCount}/${MAX_RESTARTS}`);
        this.emit('status', 'restarting');
        setTimeout(() => this.start(), 2000);
      } else if (this.restartCount >= MAX_RESTARTS) {
        console.error('[backend] Max restarts reached, giving up');
        this.emit('status', 'failed');
      }
    });

    this.process.on('error', (err) => {
      console.error('[backend] Spawn error:', err.message);
      this.emit('status', 'error');
    });

    // Wait for /health to respond
    this.waitForHealthy();
  }

  /** Poll /health until it responds or timeout */
  waitForHealthy() {
    const startTime = Date.now();

    const check = () => {
      if (this.shuttingDown) return;

      this.checkHealth().then((ok) => {
        if (ok) {
          console.log('[backend] Healthy!');
          this.healthy = true;
          this.restartCount = 0; // Reset on successful start
          this.emit('status', 'healthy');
          this.startHealthCheck();
        } else if (Date.now() - startTime < STARTUP_TIMEOUT_MS) {
          setTimeout(check, 1000);
        } else {
          console.error('[backend] Startup timeout');
          this.emit('status', 'timeout');
        }
      });
    };

    setTimeout(check, 2000); // Give it 2s before first check
  }

  /** Single health check: GET /health */
  checkHealth() {
    return new Promise((resolve) => {
      const req = http.get(
        {
          hostname: this.host,
          port: this.port,
          path: '/health',
          timeout: HEALTH_TIMEOUT_MS,
        },
        (res) => {
          resolve(res.statusCode === 200);
          res.resume();
        }
      );
      req.on('error', () => resolve(false));
      req.on('timeout', () => {
        req.destroy();
        resolve(false);
      });
    });
  }

  /** Periodic health monitoring */
  startHealthCheck() {
    this.stopHealthCheck();
    this.failCount = 0;
    this.healthTimer = setInterval(async () => {
      const ok = await this.checkHealth();
      if (ok) {
        this.failCount = 0;
        if (!this.healthy) {
          this.healthy = true;
          this.emit('status', 'healthy');
        }
      } else {
        this.failCount++;
        // Only mark unhealthy after consecutive failures (avoids flapping)
        if (this.healthy && this.failCount >= UNHEALTHY_THRESHOLD) {
          console.warn(`[backend] ${UNHEALTHY_THRESHOLD} consecutive health check failures`);
          this.healthy = false;
          this.emit('status', 'unhealthy');
        }
      }
    }, HEALTH_INTERVAL_MS);
  }

  stopHealthCheck() {
    if (this.healthTimer) {
      clearInterval(this.healthTimer);
      this.healthTimer = null;
    }
  }

  /** Graceful shutdown */
  async stop() {
    this.shuttingDown = true;
    this.stopHealthCheck();

    if (!this.process) return;

    console.log('[backend] Stopping...');
    this.emit('status', 'stopping');

    // Try graceful termination first
    if (process.platform === 'win32') {
      // On Windows, spawn taskkill for the process tree
      spawn('taskkill', ['/pid', String(this.process.pid), '/t', '/f'], {
        windowsHide: true,
      });
    } else {
      this.process.kill('SIGTERM');
    }

    // Force kill after 5s if still alive
    await new Promise((resolve) => {
      const timeout = setTimeout(() => {
        if (this.process) {
          console.log('[backend] Force killing...');
          this.process.kill('SIGKILL');
        }
        resolve();
      }, 5000);

      if (this.process) {
        this.process.once('exit', () => {
          clearTimeout(timeout);
          resolve();
        });
      } else {
        clearTimeout(timeout);
        resolve();
      }
    });

    this.process = null;
    this.healthy = false;
    this.emit('status', 'stopped');
  }

  /** Restart the backend */
  async restart() {
    await this.stop();
    this.restartCount = 0;
    this.start();
  }
}

module.exports = { BackendManager };
