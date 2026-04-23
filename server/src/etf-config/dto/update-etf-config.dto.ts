import { PartialType } from '@nestjs/mapped-types';
import { CreateEtfConfigDto } from './create-etf-config.dto';

export class UpdateEtfConfigDto extends PartialType(CreateEtfConfigDto) {}
