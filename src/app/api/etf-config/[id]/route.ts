import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const scriptPath = '/workspace/projects/server/scripts/get_etf_config.py';
    const { stdout } = await execAsync(`python3 ${scriptPath} ${id}`);

    const config = JSON.parse(stdout);
    if (!config) {
      return NextResponse.json(
        { message: 'ETF配置不存在' },
        { status: 404 }
      );
    }
    return NextResponse.json(config);
  } catch (error: any) {
    console.error('获取ETF配置失败:', error);
    return NextResponse.json(
      { message: '获取ETF配置失败' },
      { status: 500 }
    );
  }
}

// PATCH - 更新ETF配置
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    const idNum = parseInt(id);

    const dbPath = '/workspace/projects/server/database.sqlite';
    
    // 构建更新 SQL
    const updates: string[] = [];
    const values: any[] = [];
    
    if (body.code !== undefined) {
      updates.push('code = ?');
      values.push(body.code);
    }
    if (body.name !== undefined) {
      updates.push('name = ?');
      values.push(body.name);
    }
    if (body.market !== undefined) {
      updates.push('market = ?');
      values.push(body.market);
    }
    if (body.isActive !== undefined) {
      updates.push('isActive = ?');
      values.push(body.isActive ? 1 : 0);
    }

    if (updates.length === 0) {
      return NextResponse.json({ message: '没有需要更新的字段' }, { status: 400 });
    }

    values.push(idNum);
    const sql = `UPDATE etf_config SET ${updates.join(', ')} WHERE id = ?`;
    
    const { execAsync: execDb } = await import('child_process').then(m => ({ execAsync: promisify(m.exec) }));
    const dbCmd = `sqlite3 "${dbPath}" "${sql.replace(/\?/g, "'$&'").replace(/'/g, "''")}"`;
    
    await execDb(dbCmd);

    // 返回更新后的数据
    const selectSql = `SELECT id, code, name, market, isActive FROM etf_config WHERE id = ${idNum}`;
    const { stdout } = await execDb(`sqlite3 -json "${dbPath}" "${selectSql}"`);
    const result = stdout.trim() ? JSON.parse(stdout)[0] : null;

    return NextResponse.json(result);
  } catch (error: any) {
    console.error('更新ETF配置失败:', error);
    return NextResponse.json(
      { message: '更新ETF配置失败' },
      { status: 500 }
    );
  }
}

// DELETE - 删除ETF配置
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const scriptPath = '/workspace/projects/server/scripts/delete_etf_config.py';
    const { stdout } = await execAsync(`python3 ${scriptPath} ${id}`);

    const result = JSON.parse(stdout);
    return NextResponse.json(result);
  } catch (error: any) {
    console.error('删除ETF配置失败:', error);
    return NextResponse.json(
      { message: '删除ETF配置失败' },
      { status: 500 }
    );
  }
}
