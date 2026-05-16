# 加密货币指南

## 主要币种概览

### 主流加密货币
| 币种 | 代号 | 市值排名 | 特点 | 数据来源 |
|------|------|----------|------|----------|
| 比特币 | BTC | #1 | 数字黄金, 总量2100万 | CoinGecko |
| 以太坊 | ETH | #2 | 智能合约, DeFi生态 | CoinGecko |
| 币安币 | BNB | #3 | 币安交易所代币 | CoinGecko |
| XRP | XRP | #4 | 跨境支付网络 | CoinGecko |
| 狗狗币 | DOGE | #5 | 社区驱动, Meme币 | CoinGecko |
| 艾达币 | ADA | #6 | 卡尔达诺区块链 | CoinGecko |
| Solana | SOL | #7 | 高性能公链 | CoinGecko |
| DOT | DOT | #8 | 波卡生态 | CoinGecko |
| MATIC | MATIC | #9 | Polygon侧链 | CoinGecko |
| LTC | LTC | #10 | 比特币分叉, 更快 | CoinGecko |

### 稳定币
| 币种 | 代号 | 锚定 | 发行方 |
|------|------|------|--------|
| Tether | USDT | 1:1 USD | Tether Limited |
| USD Coin | USDC | 1:1 USD | Circle |
| Dai | DAI | 1:1 USD (算法) | MakerDAO |
| Binance USD | BUSD | 1:1 USD | Binance/Paxos |

## 数据来源与API

### CoinGecko API (免费，无需API Key)
```
GET https://api.coingecko.com/api/v3/simple/price
    ?ids=bitcoin,ethereum
    &vs_currencies=usd
    &include_24hr_change=true
```

### Binance API (公开数据)
```
GET https://api.binance.com/api/v3/klines
    ?symbol=BTCUSDT
    &interval=1d
    &limit=100
```

### 常用API端点

#### 获取实时价格
```python
import aiohttp

async def get_crypto_price(coin_id: str) -> dict:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_market_cap": "true",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            return await resp.json()
```

#### 获取历史价格
```python
async def get_crypto_history(coin_id: str, days: int = 30) -> dict:
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            return await resp.json()
```

## 分析框架

### 链上指标

#### NVT (Network Value to Transactions)
- 计算: 市值 / 日交易额
- 含义: 类似P/E ratio
- 高位: >100 可能泡沫
- 低位: <40 可能低估

#### 活跃地址数
- 观察: 趋势变化
- 意义: 网络实际使用情况

#### 矿工/持币者行为
- 交易所净流量: 流入=抛压, 流出=囤积
- 长期持有者持仓: HODL Wave

### 市场情绪

#### Fear & Greed Index
- 来源: alternative.me
- 范围: 0-100
- <25 = 极度恐惧, >75 = 极度贪婪

#### 谷歌趋势
- 搜索词: "Bitcoin"
- 用途: 散户情绪指标

### 宏观关联

#### 与纳指相关性
- 近年来相关性: 0.6-0.8
- 风险资产属性明显
- 流动性驱动

#### 与黄金关系
- 避险叙事: 正相关
- 实际利率: 负相关

## 交易策略

### 趋势跟踪
- 均线策略: MA50/MA200金叉死叉
- 动量策略: RSI超买超卖

### 均值回归
- Bollinger Bands
- 历史波动率区间

### 跨市场
- 与美元指数负相关
- 与黄金正相关(避险叙事)

## 风险提示

### 主要风险
| 风险类型 | 描述 | 缓解措施 |
|----------|------|----------|
| 波动风险 | 日波幅可达10%-20% | 仓位管理 |
| 流动性风险 | 小币种可能无法卖出 | 选择主流币 |
| 监管风险 | 各国政策不确定性 | 分散地区 |
| 技术风险 | 交易所被盗/宕机 | 使用硬件钱包 |
| 合约风险 | DeFi智能合约漏洞 | 审计报告 |

### 投资原则
1. **只投自己能承受损失的资金**
2. **配置比例建议 <5% 总资产**
3. **选择主流币种**
4. **不要追逐暴涨币种**
5. **做好止损计划**
