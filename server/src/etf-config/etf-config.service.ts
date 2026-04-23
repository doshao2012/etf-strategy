import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { EtfConfig } from './entities/etf-config.entity';
import { CreateEtfConfigDto } from './dto/create-etf-config.dto';
import { UpdateEtfConfigDto } from './dto/update-etf-config.dto';

@Injectable()
export class EtfConfigService {
  constructor(
    @InjectRepository(EtfConfig)
    private readonly etfConfigRepository: Repository<EtfConfig>,
  ) {}

  async findAll(): Promise<EtfConfig[]> {
    return this.etfConfigRepository.find({
      order: { id: 'ASC' },
    });
  }

  async findActive(): Promise<EtfConfig[]> {
    return this.etfConfigRepository.find({
      where: { isActive: true },
      order: { id: 'ASC' },
    });
  }

  async findOne(id: number): Promise<EtfConfig> {
    const etf = await this.etfConfigRepository.findOne({ where: { id } });
    if (!etf) {
      throw new NotFoundException(`ETF配置 ${id} 不存在`);
    }
    return etf;
  }

  async create(createEtfConfigDto: CreateEtfConfigDto): Promise<EtfConfig> {
    const etf = this.etfConfigRepository.create(createEtfConfigDto);
    return this.etfConfigRepository.save(etf);
  }

  async update(id: number, updateEtfConfigDto: UpdateEtfConfigDto): Promise<EtfConfig> {
    await this.findOne(id);
    await this.etfConfigRepository.update(id, updateEtfConfigDto);
    return this.findOne(id);
  }

  async remove(id: number): Promise<void> {
    await this.findOne(id);
    await this.etfConfigRepository.delete(id);
  }

  async getActiveEtfList(): Promise<{ code: string; name: string; market: string }[]> {
    const activeEtfs = await this.findActive();
    return activeEtfs.map(etf => ({
      code: etf.code,
      name: etf.name,
      market: etf.market,
    }));
  }
}
