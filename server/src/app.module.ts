import { Module } from '@nestjs/common';
import { StrategyModule } from './modules/strategy/strategy.module';
import { EtfConfigController } from './etf-config.controller';

@Module({
  imports: [StrategyModule],
  controllers: [EtfConfigController],
})
export class AppModule {}
