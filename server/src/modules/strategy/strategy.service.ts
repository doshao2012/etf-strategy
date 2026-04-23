import { Injectable, HttpException, Logger } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// 策略参数
const CONFIG = {
  lookbackDays: 25,
  scoreThreshold: 0.0,
  lossLimit: 0.97,
};

export interface PriceData {
  date: string;
  close: number;
  preClose: number;
  dailyChangePercent: number;
}

export interface ETFMetrics {
  code: string;
  name: string;
  score: number;
  estimatedScore: number;  // 预估动量得分
  rSquared: number;
  price: number;
  todayChange: number;
  status: string;
  reason?: string;
  slope?: number;
  annualReturn?: number;
}

export interface ETFConfig {
  code: string;
  name: string;
  market: string;
}

@Injectable()
export class StrategyService {
  private readonly logger = new Logger(StrategyService.name);
  private realEtfData: any = null;
  private etfConfigs: ETFConfig[] = [];

  constructor(private readonly httpService: HttpService) {}

  /**
   * 从数据库读取ETF配置
   */
  private async loadEtfConfigs(): Promise<ETFConfig[]> {
    try {
      const scriptPath = '/workspace/projects/server/scripts/get_etf_configs.py';
      const { stdout } = await execAsync(`python3 ${scriptPath}`);
      const configs = JSON.parse(stdout);
      this.etfConfigs = configs;
      this.logger.log(`从数据库加载了 ${configs.length} 个ETF配置`);
      return configs;
    } catch (error) {
      this.logger.error('从数据库加载ETF配置失败，使用默认配置:', error);
      // 使用默认配置
      this.etfConfigs = [
        { code: '159915', name: '创业板ETF', market: '0' },
        { code: '518880', name: '黄金ETF', market: '1' },
        { code: '513100', name: '纳指ETF', market: '1' },
        { code: '511220', name: '城投债ETF', market: '1' },
        { code: '588000', name: '科创50ETF', market: '1' },
        { code: '159985', name: '豆粕ETF', market: '0' },
        { code: '513260', name: '恒生科技ETF', market: '1' },
      ];
      return this.etfConfigs;
    }
  }

  /**
   * 动态加载配置文件（确保获取最新数据）
   * 注意：由于配置文件格式已改为JSON，直接导入可能失败
   * 因此这个方法仅用于记录日志，实际数据由Python脚本处理
   */
  private async loadEtfData() {
    try {
      this.logger.log('ETF配置文件已通过Python脚本生成');
    } catch (error) {
      this.logger.error('加载ETF配置文件失败:', error);
    }
  }

  /**
   * 获取最新的市场数据
   */
  private async fetchMarketData(): Promise<void> {
    try {
      this.logger.log('开始获取最新的市场数据...');

      // 先从数据库生成ETF配置
      const scriptPath = '/workspace/projects/server/scripts/fetch_market_data_from_db.py';
      const { stdout, stderr } = await execAsync(`python3 ${scriptPath}`);

      if (stderr) {
        this.logger.warn(`获取市场数据警告: ${stderr}`);
      }

      this.logger.log('市场数据获取完成');
    } catch (error) {
      this.logger.error('获取市场数据失败:', error);
      // 获取数据失败不抛出异常，继续使用旧数据
      this.logger.warn('将使用已缓存的配置文件数据');
    }
  }

  /**
   * 调用Python脚本计算动量得分（使用聚宽算法）
   */
  private async calculateMomentumWithPython(): Promise<any> {
    try {
      const scriptPath = '/workspace/projects/server/scripts/calculate_momentum_joinquant.py';
      const { stdout, stderr } = await execAsync(`python3 ${scriptPath} ${CONFIG.lookbackDays} ${CONFIG.scoreThreshold} ${CONFIG.lossLimit}`);

      if (stderr) {
        this.logger.warn(`Python script warning: ${stderr}`);
      }

      const result = JSON.parse(stdout);
      return result;
    } catch (error) {
      this.logger.error('Failed to calculate momentum with Python:', error);
      throw new Error('Failed to calculate momentum with Python');
    }
  }

  /**
   * 获取ETF轮动策略推荐（使用Python脚本）
   */
  async getETFStrategy() {
    try {
      this.logger.log('开始计算ETF轮动策略...');

      // 先获取最新的市场数据
      await this.fetchMarketData();

      // 重新加载配置文件（确保获取最新数据）
      await this.loadEtfData();

      // 调用Python脚本计算动量得分（Python脚本会从数据库读取ETF配置）
      const pythonResult = await this.calculateMomentumWithPython();

      // 检查Python脚本返回的数据
      if (!pythonResult.data || !pythonResult.data.etfs || pythonResult.data.etfs.length === 0) {
        this.logger.warn('Python脚本未返回有效数据');
        throw new HttpException('未能获取ETF策略数据', 500);
      }

      // 转换为前端需要的格式
      const validResults: ETFMetrics[] = pythonResult.data.etfs.map((etf: any) => ({
        code: etf.code,
        name: etf.name,
        score: etf.score,
        estimatedScore: etf.estimated_score || etf.score,  // 预估动量得分
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
          dataSource: '用户配置的真实数据（Python脚本计算）',
          summary: pythonResult.data.summary,
        },
        message: 'success',
      };
    } catch (error) {
      this.logger.error('获取ETF策略失败:', error);
      throw new HttpException(error.message || '获取ETF策略失败', 500);
    }
  }

  /**
   * 获取ETF超跌策略推荐（策略2：危机）
   */
  async getOversoldStrategy() {
    try {
      this.logger.log('开始计算ETF超跌策略（危机模式）...');

      const scriptPath = '/workspace/projects/server/scripts/calculate_oversold_strategy.py';
      const { stdout, stderr } = await execAsync(`python3 ${scriptPath} --quiet`);

      if (stderr) {
        this.logger.warn(`Python script warning: ${stderr}`);
      }

      // 调试：打印stdout的长度和前100个字符
      this.logger.log(`Python stdout长度: ${stdout.length}`);
      this.logger.log(`Python stdout前100个字符: ${stdout.substring(0, 100)}`);

      // 直接从stdout中提取JSON（取最后几行）
      const lines = stdout.trim().split('\n').filter(line => line.trim());
      
      // 从后往前找第一个包含完整JSON的行
      let jsonStr = '';
      for (let i = lines.length - 1; i >= 0; i--) {
        const line = lines[i].trim();
        if (line.startsWith('{') || line.includes('"code"')) {
          // 从这一行开始，一直到末尾，组合成完整的JSON
          jsonStr = lines.slice(i).join('');
          break;
        }
      }
      
      if (!jsonStr) {
        this.logger.warn('未找到JSON格式的输出');
        return {
          code: 200,
          data: {
            etfs: [],
            recommend: [],
            timestamp: new Date().toISOString(),
            dataSource: '真实数据',
            summary: '未找到JSON格式的输出',
          },
          message: 'success',
        };
      }
      
      const result = JSON.parse(jsonStr);

      if (!result || result.code !== 200) {
        this.logger.warn(`超跌策略计算失败: ${result.msg || result.message}`);
        return {
          code: 200,
          data: {
            etfs: [],
            recommend: [],
            timestamp: new Date().toISOString(),
            dataSource: '真实数据',
            summary: result.msg || result.message,
          },
          message: 'success',
        };
      }

      this.logger.log(`超跌策略计算完成，返回 ${result.data.etfs.length} 个ETF`);

      // 转换为前端需要的格式
      const validResults = result.data.etfs.map((etf: any) => ({
        code: etf.code,
        name: etf.name,
        currentPrice: etf.current_price,
        ma10: etf.ma10,
        lowerBand: etf.lower_band,
        distanceToLower: etf.dist_to_lower,
        avgMoney: etf.avg_money,
      }));

      // 距离下轨最近的为推荐（绝对值最小的负值）
      const recommended = validResults
        .filter(r => r.distanceToLower <= 0)
        .slice(0, 3)
        .map(r => r.name);

      return {
        code: 200,
        data: {
          etfs: validResults,
          recommend: recommended,
          timestamp: new Date().toISOString(),
          dataSource: '真实数据（ENE下轨计算）',
          summary: `共分析${result.data.summary.analyzed}只ETF（筛选后${result.data.summary.total}只），距离ENE下轨最近的top10`,
        },
        message: 'success',
      };
    } catch (error) {
      this.logger.error('获取超跌策略失败:', error);
      throw new HttpException(error.message || '获取超跌策略失败', 500);
    }
  }
}
