import { Injectable, Logger } from '@nestjs/common';

// 策略参数
const CONFIG = {
  lookbackDays: 25,
  scoreThreshold: 0.0,
  lossLimit: 0.97,
};

// ETF配置
const ETF_CONFIGS = [
  { code: '159915', name: '创业板ETF', market: '0' },
  { code: '518880', name: '黄金ETF', market: '1' },
  { code: '513100', name: '纳指ETF', market: '1' },
  { code: '511220', name: '城投债ETF', market: '1' },
  { code: '588000', name: '科创50ETF', market: '1' },
  { code: '159985', name: '豆粕ETF', market: '0' },
  { code: '513260', name: '恒生科技ETF', market: '1' },
];

// 辅助函数
function generateMockData(basePrice: number, volatility: number, targetDays: number): any[] {
  const data: any[] = [];
  let price = basePrice;
  const today = new Date();
  
  // 生成更多天数以确保跳过周末后仍有足够数据
  const totalDaysToGenerate = Math.ceil(targetDays * 1.5);
  
  for (let i = totalDaysToGenerate; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    
    // 跳过周末
    if (date.getDay() === 0 || date.getDay() === 6) continue;
    
    const change = (Math.random() - 0.5) * 2 * volatility;
    price = price * (1 + change);
    
    data.push({
      date: date.toISOString().split('T')[0],
      close: parseFloat(price.toFixed(3)),
      open: parseFloat((price * 0.995).toFixed(3)),
      high: parseFloat((price * 1.01).toFixed(3)),
      low: parseFloat((price * 0.99).toFixed(3)),
      volume: Math.floor(Math.random() * 1000000000) + 100000000,
    });
  }
  
  return data;
}

// 模拟数据（近25个交易日）
const MOCK_ETF_DATA: Record<string, any[]> = {
  '159915': generateMockData(3.5, 0.02, 26),
  '518880': generateMockData(10.0, 0.005, 26),
  '513100': generateMockData(1.8, 0.015, 26),
  '511220': generateMockData(10.3, 0.001, 26),
  '588000': generateMockData(1.5, 0.018, 26),
  '159985': generateMockData(2.1, 0.012, 26),
  '513260': generateMockData(1.2, 0.016, 26),
};

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
   * 计算线性回归（带权重）
   */
  private weightedLinearRegression(x: number[], y: number[], weights: number[]): { slope: number; intercept: number } {
    const n = x.length;
    
    let sumW = 0, sumWX = 0, sumWY = 0, sumWXX = 0, sumWXY = 0;
    
    for (let i = 0; i < n; i++) {
      sumW += weights[i];
      sumWX += weights[i] * x[i];
      sumWY += weights[i] * y[i];
      sumWXX += weights[i] * x[i] * x[i];
      sumWXY += weights[i] * x[i] * y[i];
    }
    
    const denominator = sumW * sumWXX - sumWX * sumWX;
    if (Math.abs(denominator) < 1e-10) {
      return { slope: 0, intercept: y.reduce((a, b) => a + b, 0) / n };
    }
    
    const slope = (sumW * sumWXY - sumWX * sumWY) / denominator;
    const intercept = (sumWY - slope * sumWX) / sumW;
    
    return { slope, intercept };
  }

  /**
   * 计算单个ETF的动量指标
   */
  private calculateMetrics(etfInfo: { code: string; name: string; data: any[] }): ETFMetrics | null {
    try {
      const data = etfInfo.data;
      if (data.length < CONFIG.lookbackDays + 1) {
        this.logger.warn(`${etfInfo.code}: 数据不足 ${data.length} < ${CONFIG.lookbackDays + 1}`);
        return null;
      }

      // 提取 lookback_days + 1 个数据点
      const dataSlice = data.slice(-(CONFIG.lookbackDays + 1));
      const prices = dataSlice.map(d => d.close);

      const currentPrice = prices[prices.length - 1];
      const lastClose = data.length >= 2 ? data[data.length - 2].close : currentPrice;
      const todayPct = ((currentPrice / lastClose) - 1) * 100;

      // 动量得分 & 稳定性计算 (线性加权回归)
      const x = Array.from({ length: prices.length }, (_, i) => i);
      const y = prices.map(p => Math.log(p));
      const weights = Array.from({ length: prices.length }, (_, i) => 1 + i);

      const { slope, intercept } = this.weightedLinearRegression(x, y, weights);

      // R² 稳定性
      const predicted = x.map(xi => slope * xi + intercept);
      const meanY = y.reduce((a, b) => a + b, 0) / y.length;
      
      let ssRes = 0, ssTot = 0;
      for (let i = 0; i < y.length; i++) {
        ssRes += weights[i] * Math.pow(y[i] - predicted[i], 2);
        ssTot += weights[i] * Math.pow(y[i] - meanY, 2);
      }
      
      const rSquared = ssTot > 0 ? 1 - ssRes / ssTot : 0;

      // 综合得分 = 年化(slope*250转指数) * R²
      const annReturn = Math.exp(slope * 250) - 1;
      const score = annReturn * rSquared;

      // 状态判定
      let status = '正常';
      const ratios = [
        prices[prices.length - 1] / prices[prices.length - 2],
        prices[prices.length - 2] / prices[prices.length - 3],
        prices[prices.length - 3] / prices[prices.length - 4],
      ];
      
      if (Math.min(...ratios) < CONFIG.lossLimit) {
        status = '跌幅拦截';
      } else if (score < CONFIG.scoreThreshold) {
        status = '分值过低';
      }

      return {
        code: etfInfo.code,
        name: etfInfo.name,
        score: parseFloat(score.toFixed(4)),
        rSquared: parseFloat(rSquared.toFixed(3)),
        price: parseFloat(currentPrice.toFixed(3)),
        todayChange: parseFloat(todayPct.toFixed(2)),
        status,
        slope: parseFloat(slope.toFixed(6)),
        annualReturn: parseFloat(annReturn.toFixed(4)),
      };
    } catch (error) {
      this.logger.error(`计算 ${etfInfo.code} 失败:`, error);
      return null;
    }
  }

  /**
   * 获取ETF轮动策略推荐
   */
  async getETFStrategy() {
    this.logger.log('开始计算ETF轮动策略...');

    // 计算所有ETF的动量指标
    const etfMetrics: ETFMetrics[] = [];
    
    for (const config of ETF_CONFIGS) {
      const data = MOCK_ETF_DATA[config.code];
      if (data) {
        const metrics = this.calculateMetrics({
          code: config.code,
          name: config.name,
          data,
        });
        if (metrics) {
          etfMetrics.push(metrics);
        }
      } else {
        this.logger.warn(`未找到 ${config.code} 的数据`);
      }
    }

    // 按得分排序
    etfMetrics.sort((a, b) => b.score - a.score);

    // 筛选推荐
    const recommended = etfMetrics
      .filter(r => r.score >= CONFIG.scoreThreshold && r.status === '正常')
      .map(r => r.name);

    const recommendCode = etfMetrics.length > 0 && etfMetrics[0].status === '正常' 
      ? etfMetrics[0].code 
      : null;

    this.logger.log(`策略计算完成，返回 ${etfMetrics.length} 个ETF，推荐: ${recommended.join(', ') || '无'}`);

    return {
      code: 200,
      data: {
        etfs: etfMetrics,
        recommend: recommended,
        recommendCode,
        timestamp: new Date().toISOString(),
        dataSource: '模拟数据（移动端预览版）',
        summary: {
          total: etfMetrics.length,
          recommended: recommended.length,
          topPick: recommended[0] || '暂无',
        },
      },
      message: 'success',
    };
  }

  /**
   * 获取ETF超跌策略推荐
   */
  async getOversoldStrategy() {
    this.logger.log('开始计算ETF超跌策略...');

    const etfMetrics: ETFMetrics[] = [];
    
    for (const config of ETF_CONFIGS) {
      const data = MOCK_ETF_DATA[config.code];
      if (data) {
        // 超跌策略：寻找近期跌幅大但有反弹潜力的
        const prices = data.map(d => d.close);
        const recentPrices = prices.slice(-5);
        const decline = (recentPrices[recentPrices.length - 1] / recentPrices[0] - 1) * 100;
        
        // 计算RSI简化版
        const gains: number[] = [];
        const losses: number[] = [];
        for (let i = 1; i < recentPrices.length; i++) {
          const diff = recentPrices[i] - recentPrices[i - 1];
          if (diff > 0) gains.push(diff);
          else losses.push(Math.abs(diff));
        }
        
        const avgGain = gains.length > 0 ? gains.reduce((a, b) => a + b, 0) / gains.length : 0;
        const avgLoss = losses.length > 0 ? losses.reduce((a, b) => a + b, 0) / losses.length : 0;
        const rs = avgLoss > 0 ? avgGain / avgLoss : 100;
        const rsi = 100 - (100 / (1 + rs));

        const metrics = this.calculateMetrics({
          code: config.code,
          name: config.name,
          data,
        });

        if (metrics) {
          // 超跌信号：近期跌幅 > 3% 且 RSI < 40
          const isOversold = decline < -3 && rsi < 40;
          
          etfMetrics.push({
            ...metrics,
            score: isOversold ? Math.abs(decline) : metrics.score * 0.5,
            status: isOversold ? '超跌信号' : '正常',
          });
        }
      }
    }

    // 按超跌程度排序
    etfMetrics.sort((a, b) => b.score - a.score);

    const oversoldList = etfMetrics
      .filter(r => r.status === '超跌信号')
      .map(r => r.name);

    return {
      code: 200,
      data: {
        etfs: etfMetrics,
        oversold: oversoldList,
        recommendCode: oversoldList[0] || null,
        timestamp: new Date().toISOString(),
        dataSource: '模拟数据（移动端预览版）',
        summary: {
          total: etfMetrics.length,
          oversoldSignals: oversoldList.length,
        },
      },
      message: 'success',
    };
  }
}
