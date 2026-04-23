import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from '@/app.controller';
import { AppService } from '@/app.service';
import { StrategyModule } from './modules/strategy/strategy.module';
import { EtfConfigModule } from './etf-config/etf-config.module';
import { EtfConfig } from './etf-config/entities/etf-config.entity';

@Module({
  imports: [
    TypeOrmModule.forRoot({
      type: 'sqlite',
      database: __dirname + '/../database.sqlite',
      entities: [EtfConfig],
      synchronize: true,
    }),
    StrategyModule,
    EtfConfigModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
