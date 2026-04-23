import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { EtfConfigService } from './etf-config.service';
import { EtfConfigController } from './etf-config.controller';
import { EtfConfig } from './entities/etf-config.entity';

@Module({
  imports: [TypeOrmModule.forFeature([EtfConfig])],
  controllers: [EtfConfigController],
  providers: [EtfConfigService],
  exports: [EtfConfigService],
})
export class EtfConfigModule {}
