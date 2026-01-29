-- CreateTable
CREATE TABLE "Run" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "startedAt" DATETIME,
    "completedAt" DATETIME,
    "duration" TEXT,
    "modelId" TEXT NOT NULL,
    "datasetId" TEXT NOT NULL,
    "evalDatasetId" TEXT,
    "profileName" TEXT NOT NULL DEFAULT 'single_gpu',
    "configJson" TEXT NOT NULL,
    "metricsJson" TEXT,
    "evalResultJson" TEXT,
    "seed" INTEGER,
    "gitCommit" TEXT,
    "totalTokens" INTEGER,
    "totalSteps" INTEGER,
    "gpuHours" REAL,
    "tokensPerSecond" REAL,
    CONSTRAINT "Run_modelId_fkey" FOREIGN KEY ("modelId") REFERENCES "Model" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Run_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES "Dataset" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "RunEvent" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "timestamp" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "level" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "payloadJson" TEXT,
    CONSTRAINT "RunEvent_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "RunMetric" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "timestamp" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "step" INTEGER NOT NULL,
    "loss" REAL,
    "passAt1" REAL,
    "compileRate" REAL,
    "extraJson" TEXT,
    CONSTRAINT "RunMetric_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Artifact" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "path" TEXT NOT NULL,
    "size" INTEGER NOT NULL,
    "sha256" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Artifact_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Model" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "backend" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "quantization" TEXT NOT NULL,
    "params" TEXT NOT NULL,
    "path" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'valid',
    "metaJson" TEXT,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Dataset" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'ready',
    "samples" INTEGER NOT NULL,
    "format" TEXT NOT NULL,
    "size" TEXT NOT NULL,
    "path" TEXT NOT NULL,
    "hash" TEXT NOT NULL,
    "metaJson" TEXT,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Adapter" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "baseModel" TEXT NOT NULL,
    "trainDataset" TEXT NOT NULL,
    "rank" INTEGER NOT NULL,
    "alpha" INTEGER NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'success',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "passAt1" REAL,
    "compileRate" REAL,
    "path" TEXT,
    "metaJson" TEXT
);

-- CreateTable
CREATE TABLE "Report" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "title" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "format" TEXT NOT NULL,
    "size" TEXT NOT NULL,
    "path" TEXT,
    "runId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "KvCache" (
    "key" TEXT NOT NULL PRIMARY KEY,
    "valueJson" TEXT NOT NULL,
    "expireAt" DATETIME
);

-- CreateTable
CREATE TABLE "Setting" (
    "key" TEXT NOT NULL PRIMARY KEY,
    "valueJson" TEXT NOT NULL,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "ExperimentMeta" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "osVersion" TEXT,
    "pythonVersion" TEXT,
    "pytorchVersion" TEXT,
    "transformersVersion" TEXT,
    "trlVersion" TEXT,
    "peftVersion" TEXT,
    "cudaVersion" TEXT,
    "cudnnVersion" TEXT,
    "bitsandbytesVersion" TEXT,
    "gpuModel" TEXT,
    "gpuMemoryGB" REAL,
    "cpuModel" TEXT,
    "ramGB" REAL,
    "startTime" DATETIME,
    "endTime" DATETIME,
    CONSTRAINT "ExperimentMeta_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "DatasetMeta" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "source" TEXT,
    "trainSamples" INTEGER,
    "valSamples" INTEGER,
    "testSamples" INTEGER,
    "totalProblems" INTEGER,
    "totalTokens" INTEGER,
    "promptTemplate" TEXT,
    "outputFormat" TEXT,
    "dedupeMethod" TEXT,
    "lengthFilter" TEXT,
    "cleaningFlags" TEXT,
    "splitMethod" TEXT,
    "splitRatios" TEXT,
    CONSTRAINT "DatasetMeta_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "LoraStats" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "rank" INTEGER,
    "alpha" INTEGER,
    "dropout" REAL,
    "targetModules" TEXT,
    "trainableParams" INTEGER,
    "totalParams" INTEGER,
    "trainablePercent" REAL,
    CONSTRAINT "LoraStats_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PostProcessLog" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "totalAttempts" INTEGER,
    "successfulFixes" INTEGER,
    "fixReasonDistribution" TEXT,
    "passAt1Before" REAL,
    "passAt1After" REAL,
    "syntaxErrorBefore" REAL,
    "syntaxErrorAfter" REAL,
    "runtimeErrorBefore" REAL,
    "runtimeErrorAfter" REAL,
    CONSTRAINT "PostProcessLog_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "Model_name_key" ON "Model"("name");

-- CreateIndex
CREATE UNIQUE INDEX "Dataset_name_key" ON "Dataset"("name");

-- CreateIndex
CREATE UNIQUE INDEX "Adapter_name_key" ON "Adapter"("name");

-- CreateIndex
CREATE UNIQUE INDEX "ExperimentMeta_runId_key" ON "ExperimentMeta"("runId");

-- CreateIndex
CREATE UNIQUE INDEX "DatasetMeta_runId_key" ON "DatasetMeta"("runId");

-- CreateIndex
CREATE UNIQUE INDEX "LoraStats_runId_key" ON "LoraStats"("runId");
