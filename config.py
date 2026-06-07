"""
股票智能监控系统 — 全局配置
================================
所有股票池、PE区间、事件日历、因子权重都在这里。
系统进化时自动更新此文件中的权重和因子。
"""

import os
import json
from datetime import datetime

# ============================================================
# 一、股票池配置（12支核心 + 2支观察）
# ============================================================
# 字段说明：
#   - code: AKShare用的股票代码
#   - name: 股票名称
#   - industry: 行业分类
#   - pe_reasonable: PE合理区间(买入触发) [下限, 上限]
#   - pe_high: PE高位区间(卖出触发) [下限, 上限]
#   - status: 当前状态 active(正常监控) / observing(观察)
#   - added_date: 加入日期

STOCKS = [
    {
        "code": "601127", "name": "赛力斯", "industry": "新能源车",
        "pe_reasonable": [15, 20], "pe_high": [35, 40],
        "status": "active", "added_date": "2026-06-06",
        "notes": "问界M6/M9放量+出海+机器人，核心风险华为依赖"
    },
    {
        "code": "603986", "name": "兆易创新", "industry": "芯片设计",
        "pe_reasonable": [25, 35], "pe_high": [60, 80],
        "status": "active", "added_date": "2026-06-06",
        "notes": "NOR Flash全球第二+MCU国产替代+DRAM放量"
    },
    {
        "code": "301308", "name": "江波龙", "industry": "存储模组",
        "pe_reasonable": [15, 25], "pe_high": [40, 50],
        "status": "active", "added_date": "2026-06-06",
        "notes": "国产存储模组龙头，UFS4.1主控自研"
    },
    {
        "code": "300394", "name": "天孚通信", "industry": "光器件",
        "pe_reasonable": [40, 50], "pe_high": [80, 100],
        "status": "active", "added_date": "2026-06-06",
        "notes": "NVIDIA CPO认证供应商，1.6T光引擎放量"
    },
    {
        "code": "603501", "name": "韦尔股份", "industry": "CIS芯片",
        "pe_reasonable": [25, 35], "pe_high": [50, 60],
        "status": "active", "added_date": "2026-06-06",
        "notes": "车载CIS市占率30%，AI眼镜增量"
    },
    {
        "code": "002371", "name": "北方华创", "industry": "半导体设备",
        "pe_reasonable": [25, 35], "pe_high": [55, 65],
        "status": "active", "added_date": "2026-06-06",
        "notes": "国产刻蚀+薄膜设备龙头，国产替代加速"
    },
    {
        "code": "688008", "name": "澜起科技", "industry": "内存接口",
        "pe_reasonable": [35, 45], "pe_high": [65, 80],
        "status": "active", "added_date": "2026-06-06",
        "notes": "DDR5内存接口全球第一，PCIe Retimer放量"
    },
    {
        "code": "688012", "name": "中微公司", "industry": "刻蚀设备",
        "pe_reasonable": [40, 55], "pe_high": [90, 110],
        "status": "active", "added_date": "2026-06-06",
        "notes": "国产刻蚀设备龙头，薄膜沉积第二增长曲线"
    },
    {
        "code": "600584", "name": "长电科技", "industry": "封装测试",
        "pe_reasonable": [40, 55], "pe_high": [80, 95],
        "status": "active", "added_date": "2026-06-06",
        "notes": "全球OSAT第三，XDFOI先进封装量产"
    },
    {
        "code": "688525", "name": "佰维存储", "industry": "存储+封测",
        "pe_reasonable": [25, 35], "pe_high": [50, 60],
        "status": "active", "added_date": "2026-06-06",
        "notes": "Meta智能眼镜独家存储，晶圆级封测稀缺标的"
    },
    {
        "code": "002920", "name": "德赛西威", "industry": "智驾域控",
        "pe_reasonable": [18, 25], "pe_high": [35, 45],
        "status": "active", "added_date": "2026-06-06",
        "notes": "智驾域控市占率第一，机器人域控2026量产"
    },
    {
        "code": "300475", "name": "香农芯创", "industry": "存储分销",
        "pe_reasonable": [10, 15], "pe_high": [20, 25],
        "status": "active", "added_date": "2026-06-06",
        "notes": "SK海力士核心分销商，海普存储自有品牌放量"
    },
]

# 观察池（不进入日常预测，作行业风向标）
OBSERVING = [
    {"code": "688981", "name": "中芯国际", "industry": "晶圆代工",
     "watch_reason": "国产芯片制造风向标，PB 4-5x关注"},
    {"code": "300308", "name": "中际旭创", "industry": "光模块",
     "watch_reason": "光模块龙头风向标，PE 40-50x关注"},
]

# ============================================================
# 二、预测因子初始权重（系统会自动调整）
# ============================================================
FACTOR_WEIGHTS = {
    "pe_position": 0.25,      # PE位置信号
    "momentum": 0.20,          # 短期动量信号
    "event_proximity": 0.25,   # 事件临近信号
    "sector_correlation": 0.15, # 板块联动信号
    "market_sentiment": 0.15,  # 大盘情绪信号
}

# 因子描述（用于报告解释）
FACTOR_DESCRIPTIONS = {
    "pe_position": "PE估值位置：当前PE相对合理区的位置，越接近合理区越看涨",
    "momentum": "短期动量：近5日涨跌幅与成交量变化趋势",
    "event_proximity": "事件驱动：未来7天内会议的利好/利空预判",
    "sector_correlation": "板块联动：同行业股票的涨跌相关性",
    "market_sentiment": "大盘情绪：沪深300走势与北向资金方向",
}

# ============================================================
# 三、事件日历（2026年6月-12月）
# ============================================================
# 字段说明：
#   - date: 事件日期
#   - title: 事件名称
#   - type: conference(会议) / product(产品发布) / earnings(财报) / policy(政策)
#   - affected_stocks: 受影响的股票代码列表
#   - impact: 影响方向 bullish(利好) / bearish(利空) / neutral(中性)
#   - impact_level: 影响程度 high / medium / low
#   - logic: 影响逻辑

EVENTS = [
    # ====== 6月 ======
    {
        "date": "2026-06-12", "title": "华为HDC开发者大会",
        "type": "conference",
        "affected_stocks": ["601127", "002920"],
        "impact": "bullish", "impact_level": "high",
        "logic": "赛力斯:ADS智驾升级→问界品牌力提升；德赛西威:华为智驾开放→竞合博弈"
    },
    {
        "date": "2026-06-14", "title": "VLSI Symposium芯片技术顶会(夏威夷)",
        "type": "conference",
        "affected_stocks": ["603986", "002371", "688012"],
        "impact": "bullish", "impact_level": "medium",
        "logic": "学术顶会论文→芯片设计/设备公司技术背书"
    },
    {
        "date": "2026-06-28", "title": "NVIDIA Vera Rubin全面投产",
        "type": "product",
        "affected_stocks": ["300394"],
        "impact": "bullish", "impact_level": "high",
        "logic": "新一代GPU→1.6T光模块需求加速→天孚光引擎订单增长"
    },

    # ====== 7-8月 ======
    {
        "date": "2026-07-15", "title": "A股半年报披露季开始",
        "type": "earnings",
        "affected_stocks": ["ALL"],
        "impact": "neutral", "impact_level": "high",
        "logic": "Q2业绩密集披露，存储股业绩最强但需防利好出尽"
    },
    {
        "date": "2026-08-04", "title": "FMS 2026全球存储峰会(圣克拉拉)",
        "type": "conference",
        "affected_stocks": ["603986", "301308", "688525", "300475"],
        "impact": "bullish", "impact_level": "high",
        "logic": "DRAM/NAND新技术路线→存储模组+设计公司新品方向明确"
    },
    {
        "date": "2026-08-23", "title": "Hot Chips 38芯片架构顶会(斯坦福)",
        "type": "conference",
        "affected_stocks": ["688008", "603986"],
        "impact": "bullish", "impact_level": "high",
        "logic": "AI芯片架构路线图→内存接口/互连芯片需求预判"
    },
    {
        "date": "2026-08-26", "title": "FMW全球闪存峰会(武汉)",
        "type": "conference",
        "affected_stocks": ["301308", "688525", "603986"],
        "impact": "bullish", "impact_level": "high",
        "logic": "长江存储3D NAND最新进展→国产存储生态链受益"
    },

    # ====== 9月 ======
    {
        "date": "2026-09-02", "title": "SEMICON Taiwan半导体供应链盛会",
        "type": "conference",
        "affected_stocks": ["002371", "688012", "600584"],
        "impact": "bullish", "impact_level": "high",
        "logic": "台积电Capex指引+先进封装趋势→设备/封测公司订单预期"
    },
    {
        "date": "2026-09-10", "title": "苹果iPhone 18 Pro发布(首款折叠屏)",
        "type": "product",
        "affected_stocks": ["603501", "600584"],
        "impact": "bullish", "impact_level": "high",
        "logic": "摄像头升级→CIS需求利好韦尔；先进封装→长电订单"
    },

    # ====== 10月 ======
    {
        "date": "2026-10-13", "title": "SEMICON West(旧金山)",
        "type": "conference",
        "affected_stocks": ["002371", "688012", "600584"],
        "impact": "bullish", "impact_level": "medium",
        "logic": "全球半导体设备/材料趋势→国产替代逻辑强化"
    },

    # ====== 11-12月 ======
    {
        "date": "2026-11-27", "title": "广州国际车展",
        "type": "conference",
        "affected_stocks": ["601127", "002920", "603501"],
        "impact": "bullish", "impact_level": "high",
        "logic": "问界M6/M9亮相→赛力斯催化；新车智驾方案→德赛域控需求；多摄像头→韦尔CIS"
    },
    {
        "date": "2026-12-06", "title": "IEDM 2026器件工艺顶会(旧金山)",
        "type": "conference",
        "affected_stocks": ["002371", "688012"],
        "impact": "bullish", "impact_level": "high",
        "logic": "2nm/GAA技术论文→设备研发方向，影响技术路线预期"
    },
    {
        "date": "2026-12-09", "title": "SEMICON Japan",
        "type": "conference",
        "affected_stocks": ["002371", "688012", "600584"],
        "impact": "neutral", "impact_level": "medium",
        "logic": "日本设备/材料强势，对中国设备公司偏中性"
    },
]

# 持续性的风险事件（非特定日期）
ONGOING_RISKS = [
    {
        "title": "美国对华芯片出口管制升级",
        "affected_stocks": ["688981", "002371", "688012"],
        "impact": "bearish", "impact_level": "high",
        "logic": "管制升级短期压制估值，但国产替代逻辑中长期加强"
    },
    {
        "title": "存储周期见顶担忧（多家机构预警2026年中）",
        "affected_stocks": ["603986", "301308", "688525", "300475"],
        "impact": "bearish", "impact_level": "high",
        "logic": "一旦市场共识形成，存储股集体回调"
    },
    {
        "title": "HBM长约谈判僵局",
        "affected_stocks": ["300475"],
        "impact": "bearish", "impact_level": "medium",
        "logic": "SK海力士HBM定价不确定→香农分销利润受影响"
    },
]

# ============================================================
# 四、邮件配置模板
# ============================================================
EMAIL_CONFIG = {
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465,
    "sender_email": "",       # 用户自行在管理端配置
    "sender_password": "",    # 用户自行在管理端配置（SMTP授权码）
    "recipients": [],         # 收件人列表，用户在管理端添加
    "send_time": "08:00",     # 默认每天8:00发送
}

# ============================================================
# 五、系统路径
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# 知识库文件路径
KB_PREDICTIONS = os.path.join(DATA_DIR, "predictions.json")    # 预测历史
KB_ACCURACY = os.path.join(DATA_DIR, "accuracy.json")          # 准确率统计+因子权重
KB_EVENTS_IMPACT = os.path.join(DATA_DIR, "events_impact.json") # 事件实际影响追踪
KB_STOCK_PATTERNS = os.path.join(DATA_DIR, "stock_patterns.json") # 个股规律
KB_DISCOVERED_FACTORS = os.path.join(DATA_DIR, "discovered_factors.json") # 自动发现的因子
KB_NEWS_ARCHIVE = os.path.join(DATA_DIR, "news_archive.json")  # 新闻存档

# ============================================================
# 六、辅助函数
# ============================================================
def get_stock_by_code(code: str) -> dict:
    """根据代码获取股票配置"""
    for s in STOCKS:
        if s["code"] == code:
            return s
    for s in OBSERVING:
        if s["code"] == code:
            return s
    return None

def get_active_stocks() -> list:
    """获取所有活跃监控股票"""
    return [s for s in STOCKS if s["status"] == "active"]

def get_upcoming_events(days: int = 7) -> list:
    """获取未来N天内的事件"""
    today = datetime.now().strftime("%Y-%m-%d")
    upcoming = []
    for evt in EVENTS:
        if today <= evt["date"] <= today_repr(days):
            upcoming.append(evt)
    return sorted(upcoming, key=lambda x: x["date"])

def today_repr(offset_days: int = 0) -> str:
    """获取日期字符串"""
    from datetime import timedelta
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")
