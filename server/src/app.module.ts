import { Module } from '@nestjs/common';
import { StrategyModule } from './modules/strategy/strategy.module';

@Module({
  imports: [StrategyModule],
  controllers: [],
  providers: [],
})
export class AppModule {}
