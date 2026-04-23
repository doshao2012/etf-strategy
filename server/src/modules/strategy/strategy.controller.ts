import { Controller, Get } from '@nestjs/common';
import { StrategyService } from './strategy.service';

@Controller('strategy')
export class StrategyController {
  constructor(private readonly strategyService: StrategyService) {}

  /**
   * 获取ETF轮动策略推荐（策略1：趋势）
   */
  @Get('etf-rotation')
  async getETFStrategy() {
    return await this.strategyService.getETFStrategy();
  }

  /**
   * 获取ETF超跌策略推荐（策略2：危机）
   */
  @Get('oversold')
  async getOversoldStrategy() {
    return await this.strategyService.getOversoldStrategy();
  }

  /**
   * 健康检查
   */
  @Get('health')
  health() {
    return { status: 'ok', timestamp: new Date().toISOString() };
  }
}
