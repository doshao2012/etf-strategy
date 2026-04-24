"""
策略2：ETF超跌策略（危机模式）
算法：计算当前价格与ENE下轨的距离，列出最接近下轨的top10超跌ETF
ENE下轨 = MA10 * (1 - 0.09)

改进方案：
1. 先获取所有场内ETF的前一日成交额
2. 筛选成交额超过1亿的ETF
3. 同类ETF合并（只保留一只）
4. 再进行详细超跌分析
"""

import sys
import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re

# 全局变量：是否打印调试信息
VERBOSE = False

# 配置
MIN_MONEY_W = 10000  # 最小日均成交额（万元）- 1亿
LOOKBACK_DAYS = 20  # 成交额统计天数
MA_PERIOD = 10  # MA周期
ENE_LOWER_PCT = 0.09  # 下轨偏离度 9%

def log(message: str):
    """打印日志（仅在VERBOSE模式下）"""
    if VERBOSE:
        if not is_quiet:
                    print(message)


def get_all_etf_list() -> List[Dict]:
    """
    获取所有场内ETF列表（主流ETF）
    包含宽基、行业、海外、商品等
    """
    # 完整的ETF列表（100+只）
    all_etfs = [
        # ==================== 宽基指数ETF ====================
        {'code': '510300', 'name': '沪深300ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '510500', 'name': '中证500ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '510050', 'name': '上证50ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '159915', 'name': '创业板ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '588000', 'name': '科创50ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '588080', 'name': '科创50ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '512100', 'name': '中证1000ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '512210', 'name': '中证1000ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '563300', 'name': '中证2000ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '159901', 'name': '深100ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '159919', 'name': '沪深300ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '159922', 'name': '中证500ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '510330', 'name': '沪深300ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '159690', 'name': '创业板ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '159781', 'name': '创业板ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '588200', 'name': '科创50ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '588350', 'name': '科创50ETF', 'market': 'sh', 'category': '宽基'},

        # ==================== 科技类 ====================
        {'code': '512480', 'name': '半导体ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159813', 'name': '半导体芯片ETF', 'market': 'sz', 'category': '科技'},
        {'code': '159995', 'name': '芯片ETF', 'market': 'sz', 'category': '科技'},
        {'code': '159799', 'name': '消费电子ETF', 'market': 'sz', 'category': '科技'},
        {'code': '159861', 'name': '消费电子ETF', 'market': 'sz', 'category': '科技'},
        {'code': '515050', 'name': '5GETF', 'market': 'sh', 'category': '科技'},
        {'code': '515000', 'name': '5GETF', 'market': 'sh', 'category': '科技'},
        {'code': '159511', 'name': '5GETF', 'market': 'sz', 'category': '科技'},
        {'code': '512720', 'name': '计算机ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159852', 'name': '计算机ETF', 'market': 'sz', 'category': '科技'},
        {'code': '515230', 'name': '软件ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159851', 'name': '软件ETF', 'market': 'sz', 'category': '科技'},
        {'code': '516510', 'name': '云计算ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159865', 'name': '云计算ETF', 'market': 'sz', 'category': '科技'},
        {'code': '515040', 'name': '通信ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159511', 'name': '人工智能ETF', 'market': 'sz', 'category': '科技'},
        {'code': '515070', 'name': '人工智能ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159819', 'name': '人工智能ETF', 'market': 'sz', 'category': '科技'},
        {'code': '159660', 'name': '新能源车ETF', 'market': 'sz', 'category': '科技'},
        {'code': '515030', 'name': '新能源车ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159806', 'name': '新能源车ETF', 'market': 'sz', 'category': '科技'},
        {'code': '516390', 'name': '新能源车ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159845', 'name': '电池ETF', 'market': 'sz', 'category': '科技'},
        {'code': '561160', 'name': '电池ETF', 'market': 'sh', 'category': '科技'},

        # ==================== 新能源类 ====================
        {'code': '515790', 'name': '光伏ETF', 'market': 'sh', 'category': '新能源'},
        {'code': '159857', 'name': '光伏ETF', 'market': 'sz', 'category': '新能源'},
        {'code': '516160', 'name': '新能源ETF', 'market': 'sh', 'category': '新能源'},
        {'code': '159875', 'name': '新能源ETF', 'market': 'sz', 'category': '新能源'},
        {'code': '159862', 'name': '光伏龙头ETF', 'market': 'sz', 'category': '新能源'},
        {'code': '562800', 'name': '光伏产业ETF', 'market': 'sh', 'category': '新能源'},
        {'code': '516090', 'name': '双碳ETF', 'market': 'sh', 'category': '新能源'},
        {'code': '560850', 'name': '碳中和ETF', 'market': 'sh', 'category': '新能源'},

        # ==================== 消费类 ====================
        {'code': '512690', 'name': '酒ETF', 'market': 'sh', 'category': '消费'},
        {'code': '159739', 'name': '酒ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159928', 'name': '消费ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159972', 'name': '消费ETF', 'market': 'sz', 'category': '消费'},
        {'code': '515170', 'name': '食品饮料ETF', 'market': 'sh', 'category': '消费'},
        {'code': '159736', 'name': '食品饮料ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159996', 'name': '家电ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159799', 'name': '消费电子ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159967', 'name': '消费电子ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159883', 'name': '家电龙头ETF', 'market': 'sz', 'category': '消费'},

        # ==================== 医药类 ====================
        {'code': '513120', 'name': '创新药ETF', 'market': 'sh', 'category': '医药'},
        {'code': '159783', 'name': '创新药ETF', 'market': 'sz', 'category': '医药'},
        {'code': '513000', 'name': '创新药ETF', 'market': 'sh', 'category': '医药'},
        {'code': '512010', 'name': '医药ETF', 'market': 'sh', 'category': '医药'},
        {'code': '159938', 'name': '医药卫生ETF', 'market': 'sz', 'category': '医药'},
        {'code': '159729', 'name': '医药ETF', 'market': 'sz', 'category': '医药'},
        {'code': '512010', 'name': '医药ETF', 'market': 'sh', 'category': '医药'},
        {'code': '159729', 'name': '医药ETF', 'market': 'sz', 'category': '医药'},
        {'code': '159883', 'name': '医疗器械ETF', 'market': 'sz', 'category': '医药'},
        {'code': '159765', 'name': '生物科技ETF', 'market': 'sz', 'category': '医药'},
        {'code': '512760', 'name': 'CXO ETF', 'market': 'sh', 'category': '医药'},
        {'code': '159658', 'name': '医疗ETF', 'market': 'sz', 'category': '医药'},
        {'code': '501007', 'name': '卫生ETF', 'market': 'sh', 'category': '医药'},

        # ==================== 金融类 ====================
        {'code': '512000', 'name': '券商ETF', 'market': 'sh', 'category': '金融'},
        {'code': '159841', 'name': '券商ETF', 'market': 'sz', 'category': '金融'},
        {'code': '512880', 'name': '证券ETF', 'market': 'sh', 'category': '金融'},
        {'code': '512570', 'name': '证券公司ETF', 'market': 'sh', 'category': '金融'},
        {'code': '159849', 'name': '证券ETF', 'market': 'sz', 'category': '金融'},
        {'code': '512800', 'name': '银行ETF', 'market': 'sh', 'category': '金融'},
        {'code': '159697', 'name': '银行ETF', 'market': 'sz', 'category': '金融'},
        {'code': '159688', 'name': '银行ETF', 'market': 'sz', 'category': '金融'},
        {'code': '159951', 'name': '银行ETF', 'market': 'sz', 'category': '金融'},
        {'code': '512830', 'name': '银行ETF', 'market': 'sh', 'category': '金融'},
        {'code': '515230', 'name': '银行ETF', 'market': 'sh', 'category': '金融'},

        # ==================== 周期类 ====================
        {'code': '515220', 'name': '煤炭ETF', 'market': 'sh', 'category': '周期'},
        {'code': '515080', 'name': '煤炭ETF', 'market': 'sh', 'category': '周期'},
        {'code': '159865', 'name': '煤炭ETF', 'market': 'sz', 'category': '周期'},
        {'code': '515210', 'name': '钢铁ETF', 'market': 'sh', 'category': '周期'},
        {'code': '515230', 'name': '钢铁ETF', 'market': 'sh', 'category': '周期'},
        {'code': '516790', 'name': '有色金属ETF', 'market': 'sh', 'category': '周期'},
        {'code': '159871', 'name': '有色金属ETF', 'market': 'sz', 'category': '周期'},
        {'code': '159873', 'name': '有色金属ETF', 'market': 'sz', 'category': '周期'},
        {'code': '159981', 'name': '化工ETF', 'market': 'sz', 'category': '周期'},
        {'code': '159877', 'name': '化工ETF', 'market': 'sz', 'category': '周期'},
        {'code': '516970', 'name': '石油ETF', 'market': 'sh', 'category': '周期'},
        {'code': '516830', 'name': '天然气ETF', 'market': 'sh', 'category': '周期'},
        {'code': '510190', 'name': '华宝油气', 'market': 'sh', 'category': '周期'},
        {'code': '159737', 'name': '油气ETF', 'market': 'sz', 'category': '周期'},
        {'code': '511990', 'name': '原油ETF', 'market': 'sh', 'category': '周期'},
        {'code': '162719', 'name': '原油LOF', 'market': 'sz', 'category': '周期'},

        # ==================== 其他类 ====================
        {'code': '512660', 'name': '军工ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159638', 'name': '军工ETF', 'market': 'sz', 'category': '其他'},
        {'code': '512810', 'name': '军工龙头ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159696', 'name': '军工ETF', 'market': 'sz', 'category': '其他'},
        {'code': '512980', 'name': '传媒ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159805', 'name': '传媒ETF', 'market': 'sz', 'category': '其他'},
        {'code': '159867', 'name': '传媒ETF', 'market': 'sz', 'category': '其他'},
        {'code': '512890', 'name': '红利低波ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159725', 'name': '红利ETF', 'market': 'sz', 'category': '其他'},
        {'code': '515080', 'name': '红利ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159706', 'name': '红利ETF', 'market': 'sz', 'category': '其他'},
        {'code': '515210', 'name': '钢铁ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159786', 'name': '基建ETF', 'market': 'sz', 'category': '其他'},
        {'code': '516970', 'name': '基建ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159863', 'name': '房地产ETF', 'market': 'sz', 'category': '其他'},
        {'code': '512200', 'name': '房地产ETF', 'market': 'sh', 'category': '其他'},

        # ==================== 海外ETF ====================
        {'code': '513100', 'name': '纳指ETF', 'market': 'sh', 'category': '海外'},
        {'code': '159941', 'name': '纳指ETF', 'market': 'sz', 'category': '海外'},
        {'code': '513500', 'name': '标普500', 'market': 'sh', 'category': '海外'},
        {'code': '159655', 'name': '标普500', 'market': 'sz', 'category': '海外'},
        {'code': '513300', 'name': '恒生ETF', 'market': 'sh', 'category': '海外'},
        {'code': '159920', 'name': '恒生ETF', 'market': 'sz', 'category': '海外'},
        {'code': '513260', 'name': '恒生科技ETF', 'market': 'sh', 'category': '海外'},
        {'code': '159740', 'name': '恒生科技ETF', 'market': 'sz', 'category': '海外'},
        {'code': '513650', 'name': '德国30', 'market': 'sh', 'category': '海外'},
        {'code': '513050', 'name': '中概互联', 'market': 'sh', 'category': '海外'},
        {'code': '159607', 'name': '中概互联', 'market': 'sz', 'category': '海外'},
        {'code': '513030', 'name': '德国ETF', 'market': 'sh', 'category': '海外'},
        {'code': '164824', 'name': '德国ETF', 'market': 'sz', 'category': '海外'},
        {'code': '513100', 'name': '纳指ETF', 'market': 'sh', 'category': '海外'},

        # ==================== 商品ETF ====================
        {'code': '518880', 'name': '黄金ETF', 'market': 'sh', 'category': '商品'},
        {'code': '159934', 'name': '黄金ETF', 'market': 'sz', 'category': '商品'},
        {'code': '159985', 'name': '豆粕ETF', 'market': 'sz', 'category': '商品'},
        {'code': '159930', 'name': '能源化工', 'market': 'sz', 'category': '商品'},
        {'code': '159981', 'name': '化工ETF', 'market': 'sz', 'category': '商品'},
        {'code': '511220', 'name': '城投债ETF', 'market': 'sh', 'category': '商品'},
        {'code': '511010', 'name': '国债ETF', 'market': 'sh', 'category': '商品'},
        {'code': '159970', 'name': '有色ETF', 'market': 'sz', 'category': '商品'},
    ]

    log(f"ETF列表总数: {len(all_etfs)}")
    return all_etfs


def get_etf_volume(etf_code: str, market: str) -> Optional[float]:
    """
    获取ETF前一日成交额（万元）
    使用新浪财经API获取历史K线数据
    """
    try:
        # 新浪财经API获取最近1天的数据（昨日数据）
        if market == 'sz':
            url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz{etf_code}&scale=240&ma=no&datalen=1"
        else:
            url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh{etf_code}&scale=240&ma=no&datalen=1"

        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                item = data[0]
                # 成交额 = 成交量 * 收盘价
                volume = float(item.get('volume', 0))
                close = float(item.get('close', 0))
                money = volume * close / 10000  # 换算成万元
                return money
    except Exception as e:
        log(f"获取成交额失败 {etf_code}: {e}")
    return None


def filter_by_volume(etf_list: List[Dict], min_volume: float = 5000) -> List[Dict]:
    """
    筛选成交额超过min_volume的ETF
    """
    filtered_etfs = []
    for etf in etf_list:
        volume = get_etf_volume(etf['code'], etf['market'])
        if volume is not None and volume >= min_volume:
            etf['volume'] = volume
            filtered_etfs.append(etf)
            log(f"保留: {etf['name']} ({etf['code']}), 成交额: {volume:.0f}万")
        else:
            log(f"过滤: {etf['name']} ({etf['code']}), 成交额: {volume if volume else 0:.0f}万")

    log(f"\n筛选后ETF数量: {len(filtered_etfs)}")
    return filtered_etfs


def merge_duplicate_etfs(etf_list: List[Dict]) -> List[Dict]:
    """
    合并同类ETF，只保留成交额最大的一只

    规则：
    1. 提取ETF名称中的核心词（去掉"ETF"后缀）
    2. 相同核心词的视为同一类
    3. 保留成交额最大的一只
    """
    log("\n开始合并同类ETF...")

    # 提取核心名称的函数
    def extract_core_name(name: str) -> str:
        # 去掉"ETF"后缀
        core = name.replace('ETF', '')
        # 去掉"华宝"、"国泰"等基金公司前缀（简单处理）
        core = re.sub(r'(华宝|国泰|华夏|易方达|南方|嘉实|广发|华安|银华|富国|华泰柏瑞|信诚|建信|海富通|招商|中欧|景顺长城)', '', core)
        return core.strip()

    # 按核心名称分组
    core_map = {}
    for etf in etf_list:
        core_name = extract_core_name(etf['name'])
        if core_name not in core_map:
            core_map[core_name] = []
        core_map[core_name].append(etf)

    # 每组保留成交额最大的一只
    merged_etfs = []
    for core_name, etfs in core_map.items():
        if len(etfs) > 1:
            # 按成交额降序排序
            etfs.sort(key=lambda x: x.get('volume', 0), reverse=True)
            merged_etfs.append(etfs[0])
        else:
            merged_etfs.append(etfs[0])

    log(f"\n合并后ETF数量: {len(merged_etfs)}")
    return merged_etfs




def get_historical_data(etf_code: str, market: str, count: int = 9) -> pd.DataFrame:
    """获取历史K线数据"""
    try:
        if market == 'sz':
            url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz{etf_code}&scale=240&ma=no&datalen={count}"
        else:
            url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh{etf_code}&scale=240&ma=no&datalen={count}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['day'])
                return df
    except Exception:
        pass
    return pd.DataFrame()


def get_realtime_price(etf_code: str, market: str) -> Optional[float]:
    """获取实时价格"""
    try:
        if market == 'sz':
            url = f"http://qt.gtimg.cn/q=sz{etf_code}"
        else:
            url = f"http://qt.gtimg.cn/q=sh{etf_code}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            content = response.text.strip()
            if '=' in content and '"' in content:
                data_str = content.split('"')[1]
                fields = data_str.split('~')
                if len(fields) >= 4 and fields[3]:
                    return float(fields[3])
    except Exception:
        pass
    return None


def calculate_oversold_analysis(etf_list: List[Dict]) -> List[Dict]:
    """计算超跌分析"""
    results = []
    for etf in etf_list:
        try:
            historical_df = get_historical_data(etf['code'], etf['market'], count=9)
            if historical_df.empty or len(historical_df) < 9:
                continue
            
            current_price = get_realtime_price(etf['code'], etf['market'])
            if current_price is None:
                continue
            
            sum_past_9 = historical_df['close'].astype(float).sum()
            dynamic_ma10 = (sum_past_9 + current_price) / 10
            lower_band = dynamic_ma10 * (1 - ENE_LOWER_PCT)
            dist_to_lower = (current_price - lower_band) / lower_band * 100
            
            result = {
                'code': etf['code'],
                'name': etf['name'],
                'market': etf['market'],
                'current_price': round(current_price, 3),
                'ma10': round(dynamic_ma10, 3),
                'lower_band': round(lower_band, 3),
                'dist_to_lower': round(dist_to_lower, 2),
                'avg_money': round(etf.get('volume', 0), 0),
                'category': etf.get('category', '其他')
            }
            results.append(result)
        except Exception:
            continue
    results.sort(key=lambda x: x['dist_to_lower'])
    return results


if __name__ == '__main__':
    import sys
    is_quiet = '--quiet' in sys.argv
    
    if not is_quiet:
        if not is_quiet:
                    print("ETF超跌策略分析")
        if not is_quiet:
                    print("=" * 60)
    
    # 第一步：获取所有ETF列表
    if not is_quiet:
            print("\n第一步：获取所有场内ETF列表")
    all_etfs = get_all_etf_list()
    if not is_quiet:
            print(f"获取到 {len(all_etfs)} 只ETF")
    
    # 第二步：筛选高流动性ETF
    if not is_quiet:
            print("\n第二步：筛选高流动性ETF（成交额 > 1亿）")
    filtered_etfs = []
    for etf in all_etfs:
        volume = get_etf_volume(etf['code'], etf['market'])
        if volume is not None and volume >= MIN_MONEY_W:
            etf['volume'] = volume
            filtered_etfs.append(etf)
    if not is_quiet:
            print(f"筛选后剩余 {len(filtered_etfs)} 只ETF")
    
    # 第三步：合并同类ETF
    if not is_quiet:
            print("\n第三步：合并同类ETF")
    merged_etfs = merge_duplicate_etfs(filtered_etfs)
    if not is_quiet:
            print(f"合并后剩余 {len(merged_etfs)} 只ETF")
    
    # 第四步：计算超跌分析
    if not is_quiet:
            print("\n第四步：计算超跌分析")
    oversold_etfs = calculate_oversold_analysis(merged_etfs)
    
    # 输出结果
    if is_quiet:
        result = {
            'code': 200,
            'msg': 'success',
            'data': {
                'summary': {
                    'total': len(merged_etfs),
                    'analyzed': len(oversold_etfs)
                },
                'etfs': oversold_etfs[:10]
            }
        }
        print(json.dumps(result, ensure_ascii=False))
    else:
        if not is_quiet:
                    print(f"\n成功分析 {len(oversold_etfs)} 只ETF")
        if not is_quiet:
                    print("\nTop 10 超跌ETF:")
        for i, etf in enumerate(oversold_etfs[:10]):
            if not is_quiet:
                            print(f"{i+1}. {etf['name']} ({etf['code']})")
            if not is_quiet:
                            print(f"   当前价: {etf['current_price']}, MA10: {etf['ma10']}")
            if not is_quiet:
                            print(f"   ENE下轨: {etf['lower_band']}, 距离下轨: {etf['dist_to_lower']}%")
