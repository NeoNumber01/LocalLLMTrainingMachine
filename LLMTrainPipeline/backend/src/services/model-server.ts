
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import * as http from 'http';
import axios from 'axios';
import { fileURLToPath } from 'url';
import { getPython } from '../utils/python-utils.js';

// ES Module dirname fix
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Adjust path based on compiled structure (dist/services) vs source (src/services)
// Assuming output dir structure mirrors src
const SERVER_SCRIPT = path.resolve(__dirname, '../../scripts/server.py');
const PORT = 8000;
const BASE_URL = `http://127.0.0.1:${PORT}`;

class ModelServerService {
    private process: ChildProcess | null = null;
    private isStarting = false;

    async ensureRunning() {
        if (this.process && !this.process.killed) {
            // Check health
            try {
                await axios.get(`${BASE_URL}/health`, { timeout: 1000 });
                return;
            } catch (e) {
                console.log('Server not responding, restarting...');
                this.kill();
            }
        }

        if (this.isStarting) {
            // Wait for start
            await new Promise(r => setTimeout(r, 2000));
            // Just return, let the first caller handle wait, or implement proper mutex
            // For simplicity, we just check again if running
            if (this.process && !this.process.killed) return;
        }

        await this.start();
    }

    private async start() {
        if (this.isStarting) return;
        this.isStarting = true;

        console.log('Starting Python Model Server...');
        console.log('Script Path:', SERVER_SCRIPT);

        // Spawn python process using cross-platform compatible command
        const pythonCmd = getPython();
        this.process = spawn(pythonCmd, [SERVER_SCRIPT], {
            stdio: 'inherit' // Pipe logs to main process for debugging
        });

        this.process.on('error', (err) => {
            console.error('Failed to start server:', err);
            this.isStarting = false;
        });

        this.process.on('exit', (code) => {
            console.log(`Model Server exited with code ${code}`);
            this.isStarting = false;
            this.process = null;
        });

        try {
            await this.waitForReady();
        } catch (e) {
            console.error(e);
            this.kill(); // Cleanup if failed start
            throw e;
        } finally {
            this.isStarting = false;
        }
    }

    async waitForReady() {
        console.log('Waiting for Model Server to be ready...');
        // Poll /health max 60 times (60s) for model loading
        for (let i = 0; i < 60; i++) {
            try {
                await axios.get(`${BASE_URL}/health`);
                console.log('Model Server Ready');
                return;
            } catch (e) {
                await new Promise(r => setTimeout(r, 1000));
            }
        }
        throw new Error('Timeout waiting for model server');
    }

    async loadModel(modelPath: string, adapterPath?: string, quantization?: string) {
        await this.ensureRunning();
        try {
            // Large models (6B+) can take 2-5 minutes to load, set 5 min timeout
            const res = await axios.post(`${BASE_URL}/load`,
                { model_path: modelPath, adapter_path: adapterPath, quantization },
                { timeout: 300000 } // 5 minutes
            );
            return res.data;
        } catch (e: any) {
            if (e.code === 'ECONNABORTED') {
                console.error('Model loading timed out after 5 minutes');
                throw new Error('Model loading timed out - the model may be too large for available VRAM');
            }
            console.error('Failed to load model:', e.response?.data || e.message);
            throw new Error('Failed to load model in python server');
        }
    }

    async chatStream(body: any): Promise<NodeJS.ReadableStream> {
        await this.ensureRunning();

        console.log('[ModelServer] Starting chat stream request...');

        // Use native http for true streaming (axios buffers internally)
        return new Promise((resolve, reject) => {
            const postData = JSON.stringify(body);

            const options = {
                hostname: '127.0.0.1',
                port: PORT,
                path: '/chat',
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(postData)
                },
                // Add timeout setting
                timeout: 300000 // 5 minutes
            };

            const req = http.request(options, (res) => {
                console.log(`[ModelServer] Chat response status: ${res.statusCode}`);

                if (res.statusCode !== 200) {
                    // Read error response body to get detailed info
                    let errorBody = '';
                    res.on('data', (chunk) => { errorBody += chunk.toString(); });
                    res.on('end', () => {
                        console.error('[ModelServer] Chat error response:', errorBody);
                        reject(new Error(`Chat request failed with status ${res.statusCode}: ${errorBody}`));
                    });
                    return;
                }

                console.log('[ModelServer] Chat stream connected, piping response...');
                // Return the response stream directly
                resolve(res);
            });

            req.on('error', (err) => {
                console.error('[ModelServer] Chat request connection error:', err.message);
                reject(new Error(`Chat request failed: ${err.message}`));
            });

            req.on('timeout', () => {
                console.error('[ModelServer] Chat request timed out');
                req.destroy();
                reject(new Error('Chat request timed out'));
            });

            req.write(postData);
            req.end();
        });
    }

    async unloadModel() {
        await this.ensureRunning();
        try {
            await axios.post(`${BASE_URL}/unload`);
        } catch (e) {
            console.error('Failed to unload model:', e);
        }
    }

    async getStatus(): Promise<{ loaded: boolean; loadedModel?: { modelPath: string; adapterPath?: string; quantization?: string } }> {
        await this.ensureRunning();
        try {
            const res = await axios.get(`${BASE_URL}/health`, { timeout: 5000 });
            if (res.data.loaded && res.data.model_path) {
                return {
                    loaded: true,
                    loadedModel: {
                        modelPath: res.data.model_path,
                        adapterPath: res.data.adapter_path || undefined,
                        quantization: res.data.quantization || undefined,
                    },
                };
            }
            return { loaded: res.data.loaded || false };
        } catch (e) {
            console.error('Failed to get status:', e);
            throw e;
        }
    }

    kill() {
        if (this.process) {
            console.log('Killing Model Server...');
            this.process.kill();
            this.process = null;
        }
    }
}

export const modelServer = new ModelServerService();

// Cleanup on process exit
process.on('exit', () => modelServer.kill());
process.on('SIGINT', () => process.exit());
process.on('SIGTERM', () => process.exit());
