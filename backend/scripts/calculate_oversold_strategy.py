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
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# 全局变量：是否打印调试信息
VERBOSE = False

# 配置
MIN_MONEY_W = 10000  # 最小日均成交额（万元）- 1亿
LOOKBACK_DAYS = 20  # 成交额统计天数
MA_PERIOD = 10  # MA周期
ENE_LOWER_PCT = 0.09  # 下轨偏离度 9%

# 缓存文件路径
# 运行时数据目录：Docker 里由 ETF_DATA_DIR 指向持久卷（否则每次重建容器数据全丢），
# 裸机运行不设该变量，仍落在 backend/ 下。
DATA_DIR = os.environ.get('ETF_DATA_DIR') or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VOLUME_CACHE_FILE = os.path.join(DATA_DIR, 'volume_cache.json')
HISTORY_CACHE_FILE = os.path.join(DATA_DIR, 'history_cache.json')
KLINE_CACHE_FILE = os.path.join(DATA_DIR, 'kline_cache.json')
MAX_WORKERS = 20  # 并行请求数

# 内存缓存：K线数据（filter_by_volume 时预取，calculate_oversold_analysis 复用）
_kline_cache = {}


def load_kline_cache() -> Dict:
    """加载K线缓存"""
    try:
        if os.path.exists(KLINE_CACHE_FILE):
            with open(KLINE_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            cache_date = cache.get('_date', '')
            today = datetime.now().strftime('%Y-%m-%d')
            if cache_date == today:
                log(f"K线缓存有效: {len(cache)} 只ETF")
                return cache
            else:
                log("K线缓存过期，重新获取")
    except Exception:
        pass
    return {'_date': datetime.now().strftime('%Y-%m-%d')}


def save_kline_cache(cache: Dict):
    """保存K线缓存"""
    try:
        with open(KLINE_CACHE_FILE, 'w') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass

def log(message: str):
    """打印日志（仅在VERBOSE模式下）"""
    if VERBOSE:
        if not is_quiet:
                    print(message, file=sys.stderr)


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
        {'code': '515880', 'name': '通信ETF', 'market': 'sh', 'category': '科技'},
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
        {'code': '159766', 'name': '旅游ETF', 'market': 'sz', 'category': '消费'},

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
        {'code': '513350', 'name': '油气ETF', 'market': 'sh', 'category': '周期'},
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
        {'code': '513310', 'name': '中韩芯片', 'market': 'sh', 'category': '科技'},
        {'code': '588170', 'name': '科创半导', 'market': 'sh', 'category': '科技'},
        {'code': '563360', 'name': 'A500基金', 'market': 'sh', 'category': '宽基'},
        {'code': '159516', 'name': '半导体设备', 'market': 'sz', 'category': '科技'},
        {'code': '513090', 'name': '香港证券', 'market': 'sh', 'category': '金融'},
        {'code': '159570', 'name': '港股通创新药', 'market': 'sz', 'category': '医药'},
        {'code': '159949', 'name': '创业板50', 'market': 'sz', 'category': '宽基'},
        {'code': '520500', 'name': '恒生新药', 'market': 'sh', 'category': '医药'},
        {'code': '159131', 'name': '港股通信息', 'market': 'sz', 'category': '科技'},
        {'code': '512400', 'name': '有色ETF', 'market': 'sh', 'category': '周期'},
        {'code': '517520', 'name': '黄金股', 'market': 'sh', 'category': '周期'},
        {'code': '159363', 'name': '创业板人工智能', 'market': 'sz', 'category': '科技'},
        {'code': '513330', 'name': '恒生互联', 'market': 'sh', 'category': '海外'},
        {'code': '159992', 'name': '创新药', 'market': 'sz', 'category': '医药'},
        {'code': '589720', 'name': '科创新药', 'market': 'sh', 'category': '医药'},
        {'code': '510210', 'name': '综指ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '159892', 'name': '恒生医药', 'market': 'sz', 'category': '医药'},
        {'code': '159967', 'name': '创业板成长', 'market': 'sz', 'category': '宽基'},
        {'code': '513780', 'name': '港股新药', 'market': 'sh', 'category': '医药'},
        {'code': '159530', 'name': '机器人', 'market': 'sz', 'category': '科技'},
        {'code': '159509', 'name': '纳指科技', 'market': 'sz', 'category': '海外'},
        {'code': '159326', 'name': '电网设备', 'market': 'sz', 'category': '新能源'},
        {'code': '588220', 'name': '科创100', 'market': 'sh', 'category': '宽基'},
        {'code': '159206', 'name': '卫星ETF', 'market': 'sz', 'category': '科技'},
        {'code': '513060', 'name': '恒生医疗', 'market': 'sh', 'category': '医药'},
        {'code': '512170', 'name': '医疗ETF', 'market': 'sh', 'category': '医药'},
        {'code': '513010', 'name': '港股科技', 'market': 'sh', 'category': '海外'},
        {'code': '520700', 'name': '创新药WJ', 'market': 'sh', 'category': '医药'},
        {'code': '513750', 'name': '港股非银', 'market': 'sh', 'category': '金融'},
        {'code': '510880', 'name': '红利ETF', 'market': 'sh', 'category': '其他'},
        {'code': '562590', 'name': '半导材料', 'market': 'sh', 'category': '科技'},
        {'code': '159869', 'name': '游戏ETF', 'market': 'sz', 'category': '其他'},
        {'code': '512070', 'name': '证券保险', 'market': 'sh', 'category': '金融'},
        {'code': '159611', 'name': '电力ETF', 'market': 'sz', 'category': '新能源'},
        {'code': '513190', 'name': 'H股金融', 'market': 'sh', 'category': '金融'},
        {'code': '159870', 'name': '化工ETF', 'market': 'sz', 'category': '周期'},
        {'code': '588060', 'name': '上证科创', 'market': 'sh', 'category': '宽基'},
        {'code': '560860', 'name': '工业有色', 'market': 'sh', 'category': '周期'},
        {'code': '159732', 'name': '消费电子', 'market': 'sz', 'category': '科技'},
        {'code': '159518', 'name': '标普油气', 'market': 'sz', 'category': '海外'},
        {'code': '515180', 'name': '100红利', 'market': 'sh', 'category': '其他'},
        {'code': '159980', 'name': '有色ETF', 'market': 'sz', 'category': '周期'},
        {'code': '159755', 'name': '电池ETF', 'market': 'sz', 'category': '新能源'},
        {'code': '159566', 'name': '储能电池', 'market': 'sz', 'category': '新能源'},
        {'code': '513290', 'name': '纳指生物', 'market': 'sh', 'category': '海外'},
        {'code': '513630', 'name': '香港红利', 'market': 'sh', 'category': '海外'},
        {'code': '516080', 'name': '创新医药', 'market': 'sh', 'category': '医药'},
        {'code': '520510', 'name': '港股医疗', 'market': 'sh', 'category': '医药'},
        {'code': '159366', 'name': '港股医疗', 'market': 'sz', 'category': '医药'},
        {'code': '159502', 'name': '标普生物', 'market': 'sz', 'category': '海外'},
        {'code': '159263', 'name': '价值ETF', 'market': 'sz', 'category': '其他'},
        {'code': '513520', 'name': '日经ETF', 'market': 'sh', 'category': '海外'},
        {'code': '510100', 'name': 'SZ50ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '159387', 'name': '创业板新能源', 'market': 'sz', 'category': '新能源'},
        {'code': '512710', 'name': '军工龙头', 'market': 'sh', 'category': '其他'},
        {'code': '513530', 'name': '港股红利', 'market': 'sh', 'category': '海外'},
        {'code': '589070', 'name': '科创芯片设计', 'market': 'sh', 'category': '科技'},
        {'code': '588160', 'name': '科创新材', 'market': 'sh', 'category': '科技'},
        {'code': '510760', 'name': '上证ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '516650', 'name': '有色50', 'market': 'sh', 'category': '周期'},
        {'code': '513400', 'name': '道琼斯', 'market': 'sh', 'category': '海外'},
        {'code': '512040', 'name': '国信价值', 'market': 'sh', 'category': '其他'},
        {'code': '588790', 'name': '科创智能', 'market': 'sh', 'category': '科技'},
        {'code': '515450', 'name': '红利50', 'market': 'sh', 'category': '其他'},
        {'code': '159667', 'name': '工业母机', 'market': 'sz', 'category': '其他'},
        {'code': '159227', 'name': '航空航天', 'market': 'sz', 'category': '其他'},
        {'code': '588010', 'name': '科创材料', 'market': 'sh', 'category': '科技'},
        {'code': '516150', 'name': '稀土基金', 'market': 'sh', 'category': '周期'},
        {'code': '560280', 'name': '工程机械', 'market': 'sh', 'category': '其他'},
        {'code': '588760', 'name': 'AI科创', 'market': 'sh', 'category': '科技'},
        {'code': '513700', 'name': '香港医药', 'market': 'sh', 'category': '医药'},
        {'code': '159323', 'name': '港股通汽车', 'market': 'sz', 'category': '其他'},
        {'code': '159698', 'name': '粮食ETF', 'market': 'sz', 'category': '其他'},
        {'code': '513690', 'name': '恒生股息', 'market': 'sh', 'category': '海外'},
        {'code': '520600', 'name': '汽车港股', 'market': 'sh', 'category': '其他'},
        {'code': '159105', 'name': '恒生生物', 'market': 'sz', 'category': '医药'},
        {'code': '588230', 'name': '科创200', 'market': 'sh', 'category': '宽基'},
        {'code': '159687', 'name': '亚太精选', 'market': 'sz', 'category': '海外'},
        {'code': '159141', 'name': '科创创业AI', 'market': 'sz', 'category': '科技'},
        {'code': '562950', 'name': '消电50', 'market': 'sh', 'category': '科技'},
        {'code': '520990', 'name': '国新红利', 'market': 'sh', 'category': '其他'},
        {'code': '588130', 'name': '科创药', 'market': 'sh', 'category': '医药'},
        {'code': '516020', 'name': '化工ETF', 'market': 'sh', 'category': '周期'},
        {'code': '515300', 'name': '红利300', 'market': 'sh', 'category': '其他'},
        {'code': '515400', 'name': '大数据', 'market': 'sh', 'category': '科技'},
        {'code': '510980', 'name': '上证综合', 'market': 'sh', 'category': '宽基'},
        {'code': '159207', 'name': '高股息', 'market': 'sz', 'category': '其他'},
        {'code': '513910', 'name': '红利央企', 'market': 'sh', 'category': '其他'},
        {'code': '159825', 'name': '农业ETF', 'market': 'sz', 'category': '其他'},
        {'code': '510900', 'name': '恒生中国', 'market': 'sh', 'category': '海外'},
        {'code': '513920', 'name': '央企40', 'market': 'sh', 'category': '其他'},
        {'code': '159929', 'name': '医药ETF', 'market': 'sz', 'category': '医药'},
    ]

    log(f"ETF列表总数: {len(all_etfs)}")
    return all_etfs


def get_etf_volume(etf_code: str, market: str) -> Optional[float]:
    """
    获取ETF前一日成交额（万元），顺便缓存K线数据供后续复用
    """
    try:
        # 获取最近9天的K线数据（成交额用最后一天，K线缓存给后续分析）
        symbol = f"{market}{etf_code}"
        url = f"http://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get?param={symbol},day,,,10,qfq"

        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            result = response.json()
            klines = result.get('data', {}).get(symbol, {}).get('qfqday', [])
            # 部分ETF没有前复权数据，降级使用不复权
            if not klines:
                klines = result.get('data', {}).get(symbol, {}).get('day', [])
            if klines and len(klines) > 0:
                # 转换为统一格式并缓存
                data = []
                for k in klines:
                    data.append({
                        'day': k[0],
                        'close': k[2],
                        'high': k[3],
                        'low': k[4],
                        'open': k[1],
                        'volume': k[5]
                    })
                _kline_cache[symbol] = data

                # 最后一天算成交额（腾讯API成交量单位是手，转为股再计算）
                item = data[-1]
                volume = float(item.get('volume', 0)) * 100  # 手→股
                close = float(item.get('close', 0))
                money = volume * close / 10000
                return money
    except Exception as e:
        log(f"获取成交额失败 {etf_code}: {e}")
    return None


def load_volume_cache() -> Dict:
    """加载成交额缓存"""
    try:
        if os.path.exists(VOLUME_CACHE_FILE):
            with open(VOLUME_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            # 检查是否当天缓存
            cache_date = cache.get('_date', '')
            today = datetime.now().strftime('%Y-%m-%d')
            if cache_date == today:
                log(f"成交额缓存有效: {len(cache)} 只ETF")
                return cache
            else:
                log("成交额缓存过期，重新获取")
    except Exception:
        pass
    return {'_date': datetime.now().strftime('%Y-%m-%d')}


def save_volume_cache(cache: Dict):
    """保存成交额缓存"""
    try:
        with open(VOLUME_CACHE_FILE, 'w') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass


def get_historical_from_cache(etf_code: str, market: str) -> Optional[List]:
    """从动量策略的history_cache.json读取历史K线（避免重复请求）"""
    try:
        if os.path.exists(HISTORY_CACHE_FILE):
            with open(HISTORY_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            cache_key = f"{market}{etf_code}"  # e.g. "sz159915"
            data_key = f"{market}_{etf_code}"  # e.g. "sz_159915"
            for k in (cache_key, data_key):
                if k in cache and cache[k].get('data'):
                    return cache[k]['data']
    except Exception:
        pass
    return None


def filter_by_volume(etf_list: List[Dict], min_volume: float = 5000) -> List[Dict]:
    """
    筛选成交额超过min_volume的ETF（并行请求 + 缓存）
    """
    # 加载缓存
    volume_cache = load_volume_cache()
    has_cache = len(volume_cache) > 1  # 除了_date还有数据
    
    # 收集需要请求的ETF
    to_fetch = []
    for etf in etf_list:
        key = f"{etf['market']}_{etf['code']}"
        if key in volume_cache:
            etf['volume'] = volume_cache[key]
        else:
            to_fetch.append(etf)
    
    # 并行获取缺失的成交额
    if to_fetch:
        log(f"并行获取 {len(to_fetch)} 只ETF成交额...")
        def fetch_volume(etf):
            volume = get_etf_volume(etf['code'], etf['market'])
            return etf, volume
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_volume, etf): etf for etf in to_fetch}
            for future in as_completed(futures):
                etf, volume = future.result()
                key = f"{etf['market']}_{etf['code']}"
                if volume is not None:
                    volume_cache[key] = volume
                    etf['volume'] = volume
                    log(f"获取: {etf['name']} ({etf['code']}), 成交额: {volume:.0f}万")
                else:
                    log(f"失败: {etf['name']} ({etf['code']})")
        
        save_volume_cache(volume_cache)
    
    # 筛选
    filtered_etfs = [etf for etf in etf_list if etf.get('volume', 0) >= min_volume]
    log(f"\n筛选后ETF数量: {len(filtered_etfs)}")
    return filtered_etfs


# ==================== 分组：宽基 vs 行业/概念 ====================
#
# 宽基组 = 整体市场敞口，不押单一行业：
#   - 宽基指数（沪深300、中证500/1000/2000、创业板、科创50/100/200、A500…）
#   - 商品（黄金、豆粕、原油、有色、能源化工，以及债券类）
#   - 海外宽基指数（纳指、标普500、日经、德国、恒生、恒生科技…）
# 其余（科技、医药、消费、金融、新能源、周期、军工、传媒、红利、地产…）
# 一律归入「行业/概念」组。
#
# 海外需要按代码区分：纳指/标普/恒生是宽基，而"纳指科技""港股医药""中概互联"
# 这类是主题，靠 category 分不开，所以单独列宽基白名单。
BROAD_CATEGORIES = {'宽基', '商品', '债券'}
OVERSEAS_BROAD_CODES = {
    '513100', '159941',            # 纳指
    '513500', '159655',            # 标普500
    '513300', '159920',            # 恒生
    '513260', '159740',            # 恒生科技
    '513650', '513030', '164824',  # 德国
    '513520',                      # 日经
    '513400',                      # 道琼斯
    '159687',                      # 亚太精选
    '510900',                      # 恒生中国
}


def etf_group(etf: Dict) -> str:
    """返回 'broad'（宽基/商品/债券）或 'sector'（行业/概念）。"""
    cat = etf.get('category') or ''
    if cat in BROAD_CATEGORIES:
        return 'broad'
    if cat == '海外' and str(etf.get('code')) in OVERSEAS_BROAD_CODES:
        return 'broad'
    return 'sector'


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




def get_historical_data(etf_code: str, market: str, count: int = 10) -> pd.DataFrame:
    """获取历史K线数据（优先从各级缓存读取）"""
    try:
        symbol = f"{market}{etf_code}"

        # 1. 优先用内存K线缓存（filter_by_volume 时预取）
        if symbol in _kline_cache and len(_kline_cache[symbol]) >= count:
            data = _kline_cache[symbol]
            df = pd.DataFrame(data[-count:])
            df['date'] = pd.to_datetime(df['day'])
            df['close'] = df['close'].astype(float)
            log(f"内存缓存命中: {etf_code}")
            return df

        # 2. 再从动量策略缓存读取
        cached = get_historical_from_cache(etf_code, market)
        if cached and len(cached) >= count:
            _kline_cache[symbol] = cached  # 回写到内存缓存
            df = pd.DataFrame(cached[-count:])
            df['date'] = pd.to_datetime(df['day'])
            df['close'] = df['close'].astype(float)
            log(f"磁盘缓存命中: {etf_code}")
            return df

        # 3. 缓存不够再从API获取
        symbol = f"{market}{etf_code}"
        url = f"http://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get?param={symbol},day,,,{count+10},qfq"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            result = response.json()
            klines = result.get('data', {}).get(symbol, {}).get('qfqday', [])
            # 部分ETF没有前复权数据，降级使用不复权
            if not klines:
                klines = result.get('data', {}).get(symbol, {}).get('day', [])
            if klines:
                # 转换为统一格式
                data = []
                for k in klines:
                    data.append({
                        'day': k[0],
                        'close': k[2],
                        'high': k[3],
                        'low': k[4],
                        'open': k[1],
                        'volume': k[5]
                    })
                _kline_cache[symbol] = data  # 回写到内存缓存
                df = pd.DataFrame(data[-count:])
                df['date'] = pd.to_datetime(df['day'])
                df['close'] = df['close'].astype(float)
                return df
    except Exception:
        pass
    return pd.DataFrame()


def get_realtime_price(etf_code: str, market: str) -> tuple[Optional[float], Optional[float], Optional[str]]:
    """获取实时价格、涨跌幅和交易日期(YYYY-MM-DD)"""
    try:
        if market == 'sz':
            url = f"http://qt.gtimg.cn/q=sz{etf_code}"
        else:
            url = f"http://qt.gtimg.cn/q=sh{etf_code}"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            content = response.text.strip()
            if '=' in content and '"' in content:
                data_str = content.split('"')[1]
                fields = data_str.split('~')
                if len(fields) >= 4 and fields[3]:
                    price = float(fields[3])
                    today_pct = float(fields[32]) if len(fields) > 32 and fields[32] else None
                    trade_date = fields[30][:8] if len(fields) > 30 and fields[30] else None
                    if trade_date:
                        trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
                    return price, today_pct, trade_date
    except Exception:
        pass
    return None, None, None


def calculate_oversold_analysis(etf_list: List[Dict]) -> List[Dict]:
    """计算超跌分析（并行请求）"""
    results = []
    
    def analyze_one(etf):
        try:
            historical_df = get_historical_data(etf['code'], etf['market'], count=10)
            if historical_df.empty or len(historical_df) < 10:
                return None
            
            current_price, today_pct, trade_date = get_realtime_price(etf['code'], etf['market'])
            if current_price is None:
                return None
            
            # 检查腾讯交易日期与K线最新日期是否一致（判断是否交易日）
            closes = historical_df['close'].astype(float)
            last_day = str(historical_df['day'].iloc[-1]) if 'day' in historical_df.columns else ''
            
            if trade_date and trade_date == last_day:
                # 交易日且K线已包含今天（收盘后），直接取10日均线
                dynamic_ma10 = closes.sum() / 10
            elif trade_date and trade_date != last_day:
                # 交易日盘中：K线不含今天，去掉最旧的一条，加入实时价（保持10条）
                dynamic_ma10 = (closes.sum() - closes.iloc[0] + current_price) / 10
            else:
                # 非交易日（周末/节假日），使用原始K线数据
                dynamic_ma10 = closes.sum() / 10
            
            lower_band = dynamic_ma10 * (1 - ENE_LOWER_PCT)
            dist_to_lower = (current_price - lower_band) / lower_band * 100
            
            return {
                'code': etf['code'],
                'name': etf['name'],
                'market': etf['market'],
                'current_price': round(current_price, 3),
                'today_pct': today_pct,
                'ma10': round(dynamic_ma10, 3),
                'lower_band': round(lower_band, 3),
                'dist_to_lower': round(dist_to_lower, 2),
                'avg_money': round(etf.get('volume', 0), 0),
                'category': etf.get('category', '其他'),
                'group': etf_group(etf)
            }
        except Exception:
            return None
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(analyze_one, etf) for etf in etf_list]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    results.sort(key=lambda x: x['dist_to_lower'])
    return results


# ==================== 历史超跌回溯（近 3 年） ====================
#
# 规则：T 日盘中最低价触及 ENE 下轨即视为「碰轨买入」（成交价取 min(开盘价, 下轨)，
# 低开在下轨下方时按开盘价成交）；随后看 T+1 ~ T+3 的盘中最高价，取其中最高的一档
# 作为本次的最大浮盈，并记录它出现在 +1 / +2 / +3 哪一日。
#
# 数据用日线的 open/high/low/close（前复权），是分时行情的近似：日线 high 即当日
# 盘中最高，low 即盘中最低，与「盘中」的定义一致，只是无法捕捉同一日内更细的顺序。
#
# 连续碰轨不做合并：只要落在不同交易日，每天都单独算一笔（同一波下跌连续下跌时
# 会出现多笔重叠的买入，各自按当日下轨价成交、各自看后 3 日）。
BT_YEARS = 3            # 回溯年数
BT_FETCH_DAYS = 800     # 拉取日线根数（3 年约 730 根，留出 MA10 预热余量，接口上限）
BT_HORIZON = 3          # 买入后观察 3 个交易日
BT_MAX_TRADES = 6       # 明细最多返回最近 6 次
BT_CACHE_TTL = 1800     # 回溯结果缓存 30 分钟（盘中高低点会变，不宜整天复用）
BT_CACHE_FILE = os.path.join(DATA_DIR, 'oversold_backtest_cache.json')


def _fetch_daily(symbol: str, count: int) -> List[Dict]:
    """拉取前复权日线，返回 [{day, open, high, low, close}, ...]"""
    try:
        url = (f"http://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get"
               f"?param={symbol},day,,,{count},qfq")
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json().get('data', {}).get(symbol, {})
        klines = data.get('qfqday') or data.get('day') or []
        out = []
        for k in klines:
            if len(k) < 6:
                continue
            out.append({'day': k[0], 'open': k[1], 'close': k[2],
                        'high': k[3], 'low': k[4]})
        return out
    except Exception:
        return []


def _backtest_one(etf: Dict) -> Optional[Dict]:
    """单只 ETF 的历史超跌回溯统计。失败返回 None。"""
    try:
        symbol = f"{etf['market']}{etf['code']}"
        rows = _fetch_daily(symbol, BT_FETCH_DAYS)
        if len(rows) < MA_PERIOD + BT_HORIZON + 10:
            return None

        df = pd.DataFrame(rows)
        for col in ('open', 'high', 'low', 'close'):
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['open', 'high', 'low', 'close']).reset_index(drop=True)
        if len(df) < MA_PERIOD + BT_HORIZON + 10:
            return None

        lower = df['close'].rolling(MA_PERIOD).mean() * (1 - ENE_LOWER_PCT)
        n = len(df)
        recs = []
        for i in range(MA_PERIOD - 1, n - BT_HORIZON):
            lb = lower.iloc[i]
            if pd.isna(lb) or lb <= 0:
                continue
            low_i = float(df['low'].iloc[i])
            # low<=0 属于停牌/数据缺失，不能当成"跌破下轨"
            if low_i <= 0 or low_i > float(lb):
                continue
            # 连续触轨按不同交易日各自独立计算，不做合并去重
            buy = min(float(df['open'].iloc[i]), float(lb))
            if buy <= 0:
                continue
            seg = df['high'].iloc[i + 1:i + 1 + BT_HORIZON].values.astype(float)
            if len(seg) < BT_HORIZON:
                continue
            k = int(np.argmax(seg))
            recs.append({
                'date': str(df['day'].iloc[i]),
                'buy': round(buy, 4),
                'max_ret': round((float(seg[k]) / buy - 1) * 100, 2),
                'day': k + 1,
                'max_date': str(df['day'].iloc[i + 1 + k]),
            })

        # 只保留最近 3 年（以最后一根 K 线为基准）
        cutoff = pd.to_datetime(df['day'].iloc[-1]) - pd.DateOffset(years=BT_YEARS)
        recs = [r for r in recs if pd.to_datetime(r['date']) >= cutoff]
        if not recs:
            return {'years': BT_YEARS, 'count': 0, 'recent': [], 'by_day': []}

        rets = [r['max_ret'] for r in recs]
        by_day = []
        for d in (1, 2, 3):
            hit = [r['max_ret'] for r in recs if r['day'] == d]
            if hit:
                by_day.append({'day': d, 'count': len(hit),
                               'avg': round(float(np.mean(hit)), 2)})

        recent = sorted(recs, key=lambda r: r['date'], reverse=True)[:BT_MAX_TRADES]
        return {
            'years': BT_YEARS,
            'count': len(recs),
            'win_rate': round(sum(1 for x in rets if x > 0) / len(rets) * 100, 1),
            'avg_max': round(float(np.mean(rets)), 2),
            'median_max': round(float(np.median(rets)), 2),
            'best_max': round(max(rets), 2),
            'worst_max': round(min(rets), 2),
            'by_day': by_day,
            'recent': recent,
        }
    except Exception:
        return None


def _load_bt_cache() -> Dict:
    try:
        with open(BT_CACHE_FILE, 'r') as f:
            c = json.load(f)
        if isinstance(c, dict) and isinstance(c.get('items'), dict):
            return c['items']
    except Exception:
        pass
    return {}


def _save_bt_cache(items: Dict):
    try:
        with open(BT_CACHE_FILE, 'w') as f:
            json.dump({'items': items}, f, ensure_ascii=False)
    except Exception:
        pass


def attach_backtest(etfs: List[Dict]) -> List[Dict]:
    """给前端要展示的标的补上近 3 年超跌回溯（带 30 分钟缓存）。"""
    if not etfs:
        return etfs
    items = _load_bt_cache()
    now = time.time()
    todo = []
    for etf in etfs:
        key = f"{etf['market']}{etf['code']}"
        hit = items.get(key)
        # 口径（回溯年数）变了就作废旧缓存，别拿 2 年的结果冒充 3 年
        valid = bool(hit) and (hit.get('bt') or {}).get('years') == BT_YEARS
        if valid and now - float(hit.get('ts') or 0) < BT_CACHE_TTL:
            etf['bt'] = hit['bt']
        elif valid and hit.get('bt'):
            etf['bt'] = hit['bt']   # 过期但抓取失败时退回旧结果
            todo.append(etf)
        else:
            todo.append(etf)

    if todo:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(_backtest_one, e): e for e in todo}
            for future in as_completed(futures):
                etf = futures[future]
                try:
                    bt = future.result()
                except Exception:
                    bt = None
                if bt:
                    etf['bt'] = bt
                    items[f"{etf['market']}{etf['code']}"] = {'ts': now, 'bt': bt}
        # 每天的前 10 名单会变，顺手清掉 7 天没再出现的条目，避免缓存无限膨胀
        items = {k: v for k, v in items.items()
                 if now - float(v.get('ts') or 0) < 7 * 86400}
        _save_bt_cache(items)
    return etfs


if __name__ == '__main__':
    import sys
    is_quiet = '--quiet' in sys.argv    
    if not is_quiet:
        if not is_quiet:
                    print("ETF超跌策略分析", file=sys.stderr)
        if not is_quiet:
                    print("=" * 60, file=sys.stderr)
    
    # 第一步：获取所有ETF列表
    if not is_quiet:
            print("\n第一步：获取所有场内ETF列表", file=sys.stderr)
    all_etfs = get_all_etf_list()
    if not is_quiet:
            print(f"获取到 {len(all_etfs)} 只ETF", file=sys.stderr)
    
    # 第二步：筛选高流动性ETF（并行获取成交额）
    if not is_quiet:
            print("\n第二步：筛选高流动性ETF（成交额 > 1亿）", file=sys.stderr)
    
    volume_cache = load_volume_cache()
    
    # 加载K线缓存（按日期判断有效性，同一天使用缓存避免重复请求）
    _kline_cache = load_kline_cache()
    
    filtered_etfs = []
    to_fetch = []
    for etf in all_etfs:
        key = f"{etf['market']}_{etf['code']}"
        if key in volume_cache:
            etf['volume'] = volume_cache[key]
            filtered_etfs.append(etf)
        else:
            to_fetch.append(etf)
    
    if to_fetch:
        if not is_quiet:
                print(f"并行获取 {len(to_fetch)} 只ETF成交额...", file=sys.stderr)
        def fetch_volume(etf):
            volume = get_etf_volume(etf['code'], etf['market'])
            return etf, volume
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_volume, etf): etf for etf in to_fetch}
            for future in as_completed(futures):
                etf, volume = future.result()
                key = f"{etf['market']}_{etf['code']}"
                if volume is not None and volume >= MIN_MONEY_W:
                    volume_cache[key] = volume
                    etf['volume'] = volume
                    filtered_etfs.append(etf)
        save_volume_cache(volume_cache)
    else:
        # 缓存命中，只需加上volume字段
        for etf in all_etfs:
            key = f"{etf['market']}_{etf['code']}"
            if key in volume_cache:
                etf['volume'] = volume_cache[key]
    
    # 保存K线缓存（按日期判断：同一天直接复用，跨天自动刷新）
    save_kline_cache(_kline_cache)
    
    if not is_quiet:
            print(f"筛选后剩余 {len(filtered_etfs)} 只ETF", file=sys.stderr)
    
    # 第三步：合并同类ETF
    if not is_quiet:
            print("\n第三步：合并同类ETF", file=sys.stderr)
    merged_etfs = merge_duplicate_etfs(filtered_etfs)
    if not is_quiet:
            print(f"合并后剩余 {len(merged_etfs)} 只ETF", file=sys.stderr)
    
    # 第四步：计算超跌分析
    if not is_quiet:
            print("\n第四步：计算超跌分析", file=sys.stderr)
    oversold_etfs = calculate_oversold_analysis(merged_etfs)
    
    # 输出结果（始终输出JSON）
    broad_etfs = [e for e in oversold_etfs if e['group'] == 'broad']
    sector_etfs = [e for e in oversold_etfs if e['group'] == 'sector']
    broad_top = broad_etfs[:10]
    sector_top = sector_etfs[:10]

    # 只给前端展示的这 20 只补「近 3 年超跌回溯」，不为全量 100+ 只拉 3 年日线
    attach_backtest(broad_top + sector_top)

    result = {
        'code': 200,
        'msg': 'success',
        'data': {
            'summary': {
                'total': len(merged_etfs),
                'analyzed': len(oversold_etfs),
                'broadTotal': len(broad_etfs),
                'sectorTotal': len(sector_etfs)
            },
            # 两个组各自按距离 ENE 下轨从近到远排序，各取前 10
            'broad': broad_top,
            'sector': sector_top,
            # 兼容字段：全局最超跌的 10 只（老前端仍可读）
            'etfs': oversold_etfs[:10]
        }
    }
    print(json.dumps(result, ensure_ascii=False))
