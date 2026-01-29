import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import yaml from 'js-yaml';
import { ConfigSchema } from './schema.js';
import type { Config } from './schema.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CONFIG_DIR = __dirname;


// Deep merge objects
function deepMerge<T extends Record<string, any>>(target: T, source: Partial<T>): T {
    const result = { ...target };

    for (const key of Object.keys(source) as (keyof T)[]) {
        const sourceValue = source[key];
        const targetValue = target[key];

        if (
            sourceValue !== undefined &&
            typeof sourceValue === 'object' &&
            sourceValue !== null &&
            !Array.isArray(sourceValue) &&
            typeof targetValue === 'object' &&
            targetValue !== null &&
            !Array.isArray(targetValue)
        ) {
            result[key] = deepMerge(targetValue, sourceValue as any);
        } else if (sourceValue !== undefined) {
            result[key] = sourceValue as T[keyof T];
        }
    }

    return result;
}

// Load YAML file
function loadYaml(filePath: string): Record<string, any> {
    try {
        const content = fs.readFileSync(filePath, 'utf-8');
        return (yaml.load(content) as Record<string, any>) || {};
    } catch (error) {
        console.warn(`Warning: Could not load config file: ${filePath}`);
        return {};
    }
}

// Load default config
export function loadDefaults(): Partial<Config> {
    const defaultsPath = path.join(CONFIG_DIR, 'defaults.yaml');
    return loadYaml(defaultsPath);
}

// Load profile config
export function loadProfile(profileName: string): Partial<Config> {
    const profilePath = path.join(CONFIG_DIR, 'profiles', `${profileName}.yaml`);
    return loadYaml(profilePath);
}

// Merge three-layer config: defaults < profile < runOverride
export function resolveConfig(
    profileName: string = 'single_gpu',
    runOverride: Partial<Config> = {}
): Config {
    const defaults = loadDefaults();
    const profile = loadProfile(profileName);

    // Three-layer merge
    const merged = deepMerge(deepMerge(defaults, profile), runOverride);

    // Validate and return
    return ConfigSchema.parse(merged);
}

// Global config instance
let globalConfig: Config | null = null;

export function getConfig(): Config {
    if (!globalConfig) {
        globalConfig = resolveConfig();
    }
    return globalConfig;
}

export function setGlobalConfig(config: Config): void {
    globalConfig = config;
}

export { Config, ConfigSchema };
