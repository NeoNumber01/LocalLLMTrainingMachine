import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import yaml from 'js-yaml';
import { ConfigSchema } from './schema.js';
import type { Config } from './schema.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CONFIG_DIR = __dirname;


// 深度合并对象
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

// 加载 YAML 文件
function loadYaml(filePath: string): Record<string, any> {
    try {
        const content = fs.readFileSync(filePath, 'utf-8');
        return (yaml.load(content) as Record<string, any>) || {};
    } catch (error) {
        console.warn(`Warning: Could not load config file: ${filePath}`);
        return {};
    }
}

// 加载默认配置
export function loadDefaults(): Partial<Config> {
    const defaultsPath = path.join(CONFIG_DIR, 'defaults.yaml');
    return loadYaml(defaultsPath);
}

// 加载 Profile 配置
export function loadProfile(profileName: string): Partial<Config> {
    const profilePath = path.join(CONFIG_DIR, 'profiles', `${profileName}.yaml`);
    return loadYaml(profilePath);
}

// 合并三层配置: defaults < profile < runOverride
export function resolveConfig(
    profileName: string = 'single_gpu',
    runOverride: Partial<Config> = {}
): Config {
    const defaults = loadDefaults();
    const profile = loadProfile(profileName);

    // 三层合并
    const merged = deepMerge(deepMerge(defaults, profile), runOverride);

    // 验证并返回
    return ConfigSchema.parse(merged);
}

// 全局配置实例
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
