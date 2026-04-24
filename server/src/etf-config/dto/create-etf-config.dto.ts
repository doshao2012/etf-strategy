import { IsString, IsNotEmpty, IsBoolean, IsOptional } from 'class-validator';

export class CreateEtfConfigDto {
  @IsString()
  @IsNotEmpty()
  code: string;

  @IsString()
  @IsNotEmpty()
  name: string;

  @IsString()
  @IsNotEmpty()
  market: string;

  @IsBoolean()
  @IsOptional()
  isActive?: boolean;
}
