import { Controller, Get, Post, Put, Patch, Delete, Body, Param } from '@nestjs/common';
import { EtfConfigService } from './etf-config.service';
import { CreateEtfConfigDto } from './dto/create-etf-config.dto';
import { UpdateEtfConfigDto } from './dto/update-etf-config.dto';
import { EtfConfig } from './entities/etf-config.entity';

@Controller('etf-config')
export class EtfConfigController {
  constructor(private readonly etfConfigService: EtfConfigService) {}

  @Get()
  findAll(): Promise<EtfConfig[]> {
    return this.etfConfigService.findAll();
  }

  @Get('active')
  findActive(): Promise<EtfConfig[]> {
    return this.etfConfigService.findActive();
  }

  @Get(':id')
  findOne(@Param('id') id: string): Promise<EtfConfig> {
    return this.etfConfigService.findOne(+id);
  }

  @Post()
  create(@Body() createEtfConfigDto: CreateEtfConfigDto): Promise<EtfConfig> {
    return this.etfConfigService.create(createEtfConfigDto);
  }

  @Put(':id')
  updateFull(
    @Param('id') id: string,
    @Body() updateEtfConfigDto: UpdateEtfConfigDto,
  ): Promise<EtfConfig> {
    return this.etfConfigService.update(+id, updateEtfConfigDto);
  }

  @Patch(':id')
  update(
    @Param('id') id: string,
    @Body() updateEtfConfigDto: UpdateEtfConfigDto,
  ): Promise<EtfConfig> {
    return this.etfConfigService.update(+id, updateEtfConfigDto);
  }

  @Delete(':id')
  remove(@Param('id') id: string): Promise<void> {
    return this.etfConfigService.remove(+id);
  }
}
