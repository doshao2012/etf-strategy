// ETF实时价格配置（手动更新或自动获取）
export const ETF_REAL_PRICES: { [code: string]: number } = {
  '159915': 1.5120,  // 创业板ETF (2026-04-20收盘价)
  '518880': 6.532,   // 黄金ETF
  '513100': 1.458,   // 纳指ETF
  '511220': 102.85,  // 城投债ETF
  '588000': 0.812,   // 科创50ETF
  '159985': 2.138,   // 豆粕ETF
  '513260': 0.489,   // 恒生科技ETF
};

// ETF日涨跌幅配置（%）- 手动更新
export const ETF_DAILY_CHANGES: { [code: string]: number } = {
  '159915': 1.35,    // 创业板ETF
  '518880': 0.52,    // 黄金ETF
  '513100': 2.08,    // 纳指ETF
  '511220': -0.02,   // 城投债ETF
  '588000': 1.78,    // 科创50ETF
  '159985': 0.65,    // 豆粕ETF
  '513260': -1.52,   // 恒生科技ETF
};

// 数据来源说明
export const DATA_SOURCE_NOTE = '当前使用手动配置的真实价格数据，生产环境应接入实时行情API';

// 生产环境可用API列表
export const REALTIME_API_SOURCES = [
  {
    name: '东方财富行情API',
    url: 'https://quote.eastmoney.com/api/qt/stock/klt',
    format: '{market}.{code}',
    note: '需要完整的K线数据用于动量计算'
  },
  {
    name: '新浪财经',
    url: 'https://hq.sinajs.cn/list=sh{code},sz{code}',
    note: '实时行情，但格式需解析'
  },
  {
    name: '腾讯财经',
    url: 'https://qt.gtimg.cn/q=sh{code}',
    note: '实时行情，但格式需解析'
  }
];
