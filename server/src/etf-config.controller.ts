import { Controller, Get, Post, Patch, Delete, Body, Param } from '@nestjs/common';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);
const DB_PATH = '/workspace/projects/server/database.sqlite';

async function execPython(script: string): Promise<string> {
  const { stdout } = await execAsync(`python3 -c "${script.replace(/"/g, '\\"')}"`, { timeout: 10000 });
  return stdout;
}

@Controller('etf-config')
export class EtfConfigController {
  @Get()
  async findAll() {
    try {
      const stdout = await execPython(
        `import sqlite3;import json;conn=sqlite3.connect('${DB_PATH}');cursor=conn.cursor();cursor.execute('SELECT id,code,name,market,isActive,createdAt,updatedAt FROM etf_config ORDER BY id');rows=cursor.fetchall();conn.close();print(json.dumps([{'id':r[0],'code':r[1],'name':r[2],'market':r[3],'isActive':bool(r[4]),'createdAt':r[5],'updatedAt':r[6]} for r in rows]))`
      );
      return JSON.parse(stdout.trim());
    } catch (e) {
      return [];
    }
  }

  @Post()
  async create(@Body() data: { code: string; name: string; market?: string }) {
    const market = data.market || 'sz';
    const stdout = await execPython(
      `import sqlite3;import json;conn=sqlite3.connect('${DB_PATH}');cursor=conn.cursor();cursor.execute('INSERT INTO etf_config (code,name,market,isActive) VALUES (?,?,?,1)',['${data.code}','${data.name}','${market}']);conn.commit();id=cursor.lastrowid;cursor.execute('SELECT id,code,name,market,isActive,createdAt,updatedAt FROM etf_config WHERE id=?',[id]);row=cursor.fetchone();conn.close();print(json.dumps({'id':row[0],'code':row[1],'name':row[2],'market':row[3],'isActive':bool(row[4]),'createdAt':row[5],'updatedAt':row[6]}))`
    );
    return JSON.parse(stdout.trim());
  }

  @Patch(':id')
  async update(@Param('id') id: string, @Body() data: { code?: string; name?: string; market?: string; isActive?: boolean }) {
    const updates: string[] = [];
    const values: any[] = [];
    if (data.code) { updates.push('code=?'); values.push(data.code); }
    if (data.name) { updates.push('name=?'); values.push(data.name); }
    if (data.market) { updates.push('market=?'); values.push(data.market); }
    if (data.isActive !== undefined) { updates.push('isActive=?'); values.push(data.isActive ? 1 : 0); }
    updates.push("updatedAt=datetime('now')");
    values.push(id);
    
    await execPython(
      `import sqlite3;conn=sqlite3.connect('${DB_PATH}');cursor=conn.cursor();cursor.execute('UPDATE etf_config SET ${updates.join(',')} WHERE id=?',${JSON.stringify(values)});conn.commit();conn.close()`
    );
    return { success: true };
  }

  @Delete(':id')
  async remove(@Param('id') id: string) {
    await execPython(
      `import sqlite3;conn=sqlite3.connect('${DB_PATH}');cursor=conn.cursor();cursor.execute('DELETE FROM etf_config WHERE id=?',[${id}]);conn.commit();conn.close()`
    );
    return { success: true };
  }
}
