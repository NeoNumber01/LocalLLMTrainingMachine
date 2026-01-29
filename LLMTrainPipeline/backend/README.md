# Nexus AI Backend

LLM training pipeline backend service, built with Node.js + TypeScript + Fastify + Prisma + SQLite.

## Quick Start

### 1. Install Dependencies

```bash
cd backend
npm install
```

### 2. Initialize Database

```bash
# Generate Prisma Client
npm run db:generate

# Execute database migration
npm run db:push

# Insert seed data
npm run db:seed
```

### 3. Start Development Server

```bash
npm run dev
```

The service will start at `http://localhost:3001`.

### 4. View API Documentation

Visit `http://localhost:3001/docs` to view Swagger documentation.

## Configuration System

Configuration uses a three-layer merge strategy:

1. `src/config/defaults.yaml` - Default configuration
2. `src/config/profiles/*.yaml` - Compute configuration profiles
3. `config` parameter when creating Run - Runtime override

Get merged configuration:
```bash
GET /api/config/resolved?runId=xxx
```

## Provider Switching

Modify the `providers` configuration in `src/config/defaults.yaml` to switch implementations:

```yaml
providers:
  compute: "local_single"      # local_single | local_multi_fsdp
  trainer: "lora"              # lora | full_finetune
  eval: "code_passk"           # code_passk
  artifactStore: "filesystem"  # filesystem | s3
  cache: "memory_ttl"          # memory_ttl | sqlite_cache
```

## Frontend Integration

1. Add environment variable in frontend project:
   ```
   VITE_API_BASE_URL=http://localhost:3001/api
   ```

2. Replace mockData imports with API calls

3. SSE log stream connection:
   ```javascript
   const eventSource = new EventSource('/api/runs/:id/logs/stream');
   ```

## Directory Structure

```
backend/
├── src/
│   ├── config/          # Configuration system
│   ├── db/              # Database (Prisma)
│   ├── providers/       # Provider interfaces and implementations
│   ├── routes/          # API routes
│   ├── services/        # Business logic
│   ├── types/           # Type definitions
│   └── index.ts         # Entry point
├── storage/             # Local storage directory
└── package.json
```
