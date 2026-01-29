// Check actual database column types
import { PrismaClient } from '@prisma/client';
import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function main() {
    const dbPath = path.join(__dirname, '../prisma/dev.db');
    console.log('Database path:', dbPath);

    const db = new Database(dbPath, { readonly: true });

    // 查看 LoraStats 表结构
    const tableInfo = db.prepare("PRAGMA table_info('LoraStats')").all();

    console.log('\n========== LoraStats Table Schema ==========');
    console.log('Column Name\t\tType\t\tNot Null');
    console.log('------------------------------------------------');
    for (const col of tableInfo) {
        console.log(`${col.name}\t\t${col.type}\t\t${col.notnull}`);
    }

    db.close();
}

main().catch(console.error);
