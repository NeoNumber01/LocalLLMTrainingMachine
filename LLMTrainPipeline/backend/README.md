# Nexus AI Backend

LLM 训练流水线后端服务，基于 Node.js + TypeScript + Fastify + Prisma + SQLite。

## 快速开始

### 1. 安装依赖

```bash
cd backend
npm install
```

### 2. 初始化数据库

```bash
# 生成 Prisma Client
npm run db:generate

# 执行数据库迁移
npm run db:push

# 插入种子数据
npm run db:seed
```

### 3. 启动开发服务器

```bash
npm run dev
```

服务将在 `http://localhost:3001` 启动。

### 4. 查看 API 文档

访问 `http://localhost:3001/docs` 查看 Swagger 文档。

## 配置系统

配置采用三层合并策略：

1. `src/config/defaults.yaml` - 默认配置
2. `src/config/profiles/*.yaml` - 计算配置文件
3. Run 创建时的 `config` 参数 - 运行时覆盖

获取合并后配置：
```bash
GET /api/config/resolved?runId=xxx
```

## Provider 切换

修改 `src/config/defaults.yaml` 中的 `providers` 配置即可切换实现：

```yaml
providers:
  compute: "local_single"      # local_single | local_multi_fsdp
  trainer: "lora"              # lora | full_finetune
  eval: "code_passk"           # code_passk
  artifactStore: "filesystem"  # filesystem | s3
  cache: "memory_ttl"          # memory_ttl | sqlite_cache
```

## 前端对接

1. 在前端项目添加环境变量：
   ```
   VITE_API_BASE_URL=http://localhost:3001/api
   ```

2. 替换 mockData 导入为 API 调用

3. SSE 日志流连接：
   ```javascript
   const eventSource = new EventSource('/api/runs/:id/logs/stream');
   ```

## 目录结构

```
backend/
├── src/
│   ├── config/          # 配置系统
│   ├── db/              # 数据库 (Prisma)
│   ├── providers/       # Provider 接口与实现
│   ├── routes/          # API 路由
│   ├── services/        # 业务逻辑
│   ├── types/           # 类型定义
│   └── index.ts         # 入口
├── storage/             # 本地存储目录
└── package.json
```
