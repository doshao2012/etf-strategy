import { Injectable, Logger } from '@nestjs/common';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// 策略参数
const CONFIG = {
  lookbackDays: 25,
  scoreThreshold: 0.0,
  lossLimit: 0.97,
};

// Python脚本路径
const SCRIPTS_PATH = '/workspace/projects/server/scripts';

export interface ETFMetrics {
  code: string;
  name: string;
  score: number;
  rSquared: number;
  price: number;
  todayChange: number;
  status: string;
  reason?: string;
  slope?: number;
  annualReturn?: number;
}

@Injectable()
export class StrategyService {
  private readonly logger = new Logger(StrategyService.name);

  /**
   * 调用Python脚本计算动量得分
   */
  private async calculateMomentumWithPython(): Promise<any> {
    try {
      const scriptPath = `${SCRIPTS_PATH}/calculate_momentum_joinquant.py`;
      const { stdout, stderr } = await execAsync(
        `python3 ${scriptPath} ${CONFIG.lookbackDays} ${CONFIG.scoreThreshold} ${CONFIG.lossLimit}`
      );

      if (stderr) {
        this.logger.warn(`Python script warning: ${stderr}`);
      }

      const result = JSON.parse(stdout);
      return result;
    } catch (error) {
      this.logger.error('计算动量得分失败:', error);
      throw error;
    }
  }

  /**
   * 调用Python脚本计算超跌策略
   */
  private async calculateOversoldWithPython(): Promise<any> {
    try {
      const scriptPath = `${SCRIPTS_PATH}/calculate_oversold_strategy.py`;
      const { stdout, stderr } = await execAsync(`python3 ${scriptPath} --quiet`);

      if (stderr) {
        this.logger.warn(`Python script warning: ${stderr}`);
      }

      // 从输出中提取JSON
      const lines = stdout.trim().split('\n').filter(line => line.trim());
      let jsonStr = '';
      
      for (let i = lines.length - 1; i >= 0; i--) {
        const line = lines[i].trim();
        if (line.startsWith('{') || line.includes('"code"')) {
          jsonStr = lines.slice(i).join('');
          break;
        }
      }

      if (!jsonStr) {
        return { code: 500, data: { etfs: [] }, message: '未找到JSON输出' };
      }

      return JSON.parse(jsonStr);
    } catch (error) {
      this.logger.error('计算超跌策略失败:', error);
      throw error;
    }
  }

  /**
   * 获取ETF轮动策略推荐
   */
  async getETFStrategy() {
    this.logger.log('开始计算ETF轮动策略（真实数据）...');

    try {
      const pythonResult = await this.calculateMomentumWithPython();

      if (!pythonResult.data || !pythonResult.data.etfs || pythonResult.data.etfs.length === 0) {
        this.logger.warn('Python脚本未返回有效数据');
        return {
          code: 200,
          data: {
            etfs: [],
            recommend: [],
            recommendCode: null,
            timestamp: new Date().toISOString(),
            dataSource: '真实数据',
            summary: { total: 0, recommended: 0, topPick: '暂无' },
          },
          message: 'success',
        };
      }

      // 转换为前端需要的格式
      const validResults: ETFMetrics[] = pythonResult.data.etfs.map((etf: any) => ({
        code: etf.code,
        name: etf.name,
        score: etf.score,
        rSquared: etf.r_squared,
        price: etf.price,
        todayChange: etf.today_pct,
        status: etf.status,
        slope: etf.slope,
        annualReturn: etf.ann_return,
      }));

      const recommended = validResults
        .filter(r => r.score >= CONFIG.scoreThreshold && r.status === '正常')
        .map(r => r.name);

      this.logger.log(`策略计算完成，返回 ${validResults.length} 个ETF，推荐: ${recommended.join(', ') || '无'}`);

      return {
        code: 200,
        data: {
          etfs: validResults,
          recommend: recommended,
          recommendCode: pythonResult.data.recommend,
          timestamp: new Date().toISOString(),
          dataSource: '真实数据（Python脚本计算）',
          summary: pythonResult.data.summary,
        },
        message: 'success',
      };
    } catch (error) {
      this.logger.error('获取ETF策略失败:', error);
      return {
        code: 500,
        data: {
          etfs: [],
          recommend: [],
          recommendCode: null,
          timestamp: new Date().toISOString(),
          dataSource: '真实数据',
          summary: { total: 0, recommended: 0, topPick: '暂无' },
        },
        message: '获取策略失败: ' + (error as Error).message,
      };
    }
  }

  /**
   * 获取ETF超跌策略推荐
   */
  async getOversoldStrategy() {
    this.logger.log('开始计算ETF超跌策略（真实数据）...');

    try {
      const result = await this.calculateOversoldWithPython();

      if (!result || result.code !== 200) {
        this.logger.warn(`超跌策略计算失败: ${result?.message || '未知错误'}`);
        return {
          code: 200,
          data: {
            etfs: [],
            oversold: [],
            recommendCode: null,
            timestamp: new Date().toISOString(),
            dataSource: '真实数据',
            summary: { total: 0, oversoldSignals: 0 },
          },
          message: 'success',
        };
      }

      this.logger.log(`超跌策略计算完成，返回 ${result.data.etfs.length} 个ETF`);

      // 转换为前端需要的格式
      const validResults: ETFMetrics[] = result.data.etfs.map((etf: any) => ({
        code: etf.code,
        name: etf.name,
        score: etf.current_price || 0,
        rSquared: 0,
        price: etf.current_price || 0,
        todayChange: etf.today_pct || 0,
        status: etf.status || '正常',
        annualReturn: etf.distanceToLower || 0,
      }));

      const oversoldList = validResults
        .filter(r => r.status === '超跌信号')
        .map(r => r.name);

      return {
        code: 200,
        data: {
          etfs: validResults,
          oversold: oversoldList,
          recommendCode: oversoldList[0] || null,
          timestamp: new Date().toISOString(),
          dataSource: '真实数据（ENE下轨计算）',
          summary: {
            total: result.data.etfs.length,
            oversoldSignals: oversoldList.length,
          },
        },
        message: 'success',
      };
    } catch (error) {
      this.logger.error('获取超跌策略失败:', error);
      return {
        code: 500,
        data: {
          etfs: [],
          oversold: [],
          recommendCode: null,
          timestamp: new Date().toISOString(),
          dataSource: '真实数据',
          summary: { total: 0, oversoldSignals: 0 },
        },
        message: '获取策略失败: ' + (error as Error).message,
      };
    }
  }
}
