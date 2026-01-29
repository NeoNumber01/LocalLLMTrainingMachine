/*
  Warnings:

  - You are about to alter the column `totalParams` on the `LoraStats` table. The data in that column could be lost. The data in that column will be cast from `Int` to `BigInt`.
  - You are about to alter the column `trainableParams` on the `LoraStats` table. The data in that column could be lost. The data in that column will be cast from `Int` to `BigInt`.

*/
-- AlterTable
ALTER TABLE "DatasetMeta" ADD COLUMN "statisticsJson" TEXT;

-- AlterTable
ALTER TABLE "Run" ADD COLUMN "sourceRunId" TEXT;

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_LoraStats" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "rank" INTEGER,
    "alpha" INTEGER,
    "dropout" REAL,
    "targetModules" TEXT,
    "trainableParams" BIGINT,
    "totalParams" BIGINT,
    "trainablePercent" REAL,
    CONSTRAINT "LoraStats_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "new_LoraStats" ("alpha", "dropout", "id", "rank", "runId", "targetModules", "totalParams", "trainableParams", "trainablePercent") SELECT "alpha", "dropout", "id", "rank", "runId", "targetModules", "totalParams", "trainableParams", "trainablePercent" FROM "LoraStats";
DROP TABLE "LoraStats";
ALTER TABLE "new_LoraStats" RENAME TO "LoraStats";
CREATE UNIQUE INDEX "LoraStats_runId_key" ON "LoraStats"("runId");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
