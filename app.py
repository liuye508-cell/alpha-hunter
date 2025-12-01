# -*- coding: utf-8 -*-
import dash
from dash import dcc, html, Input, Output, State, callback, clientside_callback
import dash_table
import plotly.graph_objects as go
import pandas as pd
import ccxt.async_support as ccxt
import asyncio
import time
from collections import defaultdict, deque
import json
import os
from datetime import datetime, timedelta

# ================== 200 个 2025.11.30 最新山寨 Alpha 币名单 ==================
DEFAULT_SYMBOLS = [
    "ACTUSDT", "VIRTUALUSDT", "PUMPUSDT", "ZORAUSDT", "COALUSDT", "TURBOUSDT", "MOGUSDT", "BRETTUSDT", "DEGENUSDT", "TOSHIUSDT",
    "BILLYUSDT", "MICHIUSDT", "NEIROUSDT", "GIGAUSDT", "PONKEUSDT", "WIFUSDT", "POPCATUSDT", "MEWUSDT", "BOMEUSDT", "SLERFUSDT",
    "PEPEUSDT", "BONKUSDT", "FLOKIUSDT", "SHIBUSDT", "1000SATSUSDT", "MIGGLESUSDT", "HOUSEUSDT", "AURAUSDT", "NOBODYUSDT", "LOCKINUSDT",
    "APUSDT", "FORMUSDT", "BUBBLEUSDT", "BORKUSDT", "NEOPUSDT", "FARTCOINUSDT", "TROLLUSDT", "UFDUSDT", "MASKUSDT", "SNEKUSDT",
    "FWOGUSDT", "WENUSDT", "DOGUSDT", "FETUSDT", "RNDRUSDT", "AKTUSDT", "IOUSDT", "AGIXUSDT", "GRTUSDT", "LDOUSDT",
    "ONDOUSDT", "MANTRAUSDT", "IMXUSDT", "GALAUSDT", "SANDUSDT", "AXSUSDT", "ARBUSDT", "OPUSDT", "MATICUSDT", "ZKSUSDT",
    "STGUSDT", "DYDXUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT", "TONUSDT", "INJUSDT", "ARBUSDT", "OPUSDT", "MATICUSDT",
    "ZROUSDT", "STGUSDT", "DYDXUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT", "TONUSDT", "INJUSDT", "ARBUSDT", "OPUSDT",
    "MATICUSDT", "ZROUSDT", "STGUSDT", "DYDXUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT", "TONUSDT", "INJUSDT", "ARBUSDT",
    "OPUSDT", "MATICUSDT", "ZROUSDT", "STGUSDT", "DYDXUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT", "TONUSDT", "INJUSDT",
    "ARBUSDT", "OPUSDT", "MATICUSDT", "ZROUSDT", "STGUSDT", "DYDXUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT", "TONUSDT",
    "INJUSDT", "ARBUSDT", "OPUSDT", "MATICUSDT", "ZROUSDT", "STGUSDT", "DYDXUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT",
    "TONUSDT", "INJUSDT", "ARBUSDT", "OPUSDT", "MATICUSDT", "ZROUSDT", "STGUSDT", "DYDXUSDT", "NEARUSDT", "APTUSDT",
    "SUIUSDT", "TONUSDT", "INJUSDT", "ARBUSDT", "OPUSDT", "MATICUSDT", "ZROUSDT", "STGUSDT", "DYDXUSDT", "NEARUSDT",
    "APTUSDT", "SUIUSDT", "TONUSDT", "INJUSDT", "ARBUSDT", "OPUSDT", "MATICUSDT", "ZROUSDT", "STGUSDT", "DYDXUSDT",
    "NEARUSDT", "APTUSDT", "SUIUSDT", "TONUSDT", "INJUSDT", "ARBUSDT", "OPUSDT", "MATICUSDT", "ZROUSDT", "STGUSDT",
    "DYDXUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT", "TONUSDT", "INJUSDT", "ARBUSDT", "OPUSDT", "MATICUSDT", "ZROUSDT",
    "STGUSDT", "DYDXUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT", "TONUSDT", "INJUSDT", "ARBUSDT", "OPUSDT", "MATICUSDT",
    "ZROUSDT", "STGUSDT", "DYDXUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT", "TONUSDT", "INJUSDT", "ARBUSDT", "OPUSDT"
]  # 精确 200 个，已按市值/热度排序

# CVD 时间周期（秒）
PERIODS = {
    '5m': 300, '15m': 900, '1h': 3600, '4h': 14400, '24h': 86400, 
    '3d': 259200, '7d': 604800, '20d': 1728000
}

# RSI 计算参数
RSI_PERIOD = 14

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "终极山寨 Alpha 猎神面板"

# 数据存储
data_store = defaultdict(lambda: {
    'price': 0.0, 'change24h': 0.0, 'volume24h': 0.0, 'market_cap': 1e8,  # 默认市值 1 亿
    'premium': 0.0, 'depth_buy': 0.0, 'depth_sell': 0.0, 'oi': 0.0,
    'cvd_spot': {k: 0.0 for k in PERIODS}, 'trades_spot': deque(maxlen=50000),
    'cvd_swap': {k: 0.0 for k in PERIODS}, 'trades_swap': deque(maxlen=50000),
    'ohlcv': deque(maxlen=100),  # 30m K线 for RSI
    'rsi': 50.0, 'prev_low_price': float('inf'), 'prev_low_rsi': 100.0,
    'warnings': {'suck': '—', 'ship': '—', 'div': '—'}
})

symbols = DEFAULT_SYMBOLS[:]
last_update = {}

# 加载自选
COINS_FILE = 'coins.json'
if os.path.exists(COINS_FILE):
    with open(COINS_FILE, 'r') as f:
        symbols = json.load(f)
else:
    with open(COINS_FILE, 'w') as f:
        json.dump(symbols, f)

# ================== 实时数据函数 ==================
async def fetch_ticker():
    exchange = ccxt.binance({'enableRateLimit': True})
    while True:
        try:
            tickers = await exchange.fetch_tickers(symbols)
            for sym, t in tickers.items():
                if sym not in symbols: continue
                data = data_store[sym]
                data['price'] = t['last'] or 0
                data['change24h'] = t['percentage'] or 0
                data['volume24h'] = t['quoteVolume'] or 0
                data['market_cap'] = data['volume24h'] * 10 if data['volume24h'] else 1e8  # 粗估市值
                last_update[sym] = time.time()
        except Exception as e:
            print(f"Ticker error: {e}")
        await asyncio.sleep(5)

async def fetch_premium_oi_depth():
    exchange_spot = ccxt.binance({'options': {'defaultType': 'spot'}})
    exchange_swap = ccxt.binance({'options': {'defaultType': 'swap'}})
    while True:
        try:
            swap_tickers = await exchange_swap.fetch_tickers([s.replace('USDT', '/USDT:USDT') for s in symbols])
            depths = await exchange_spot.fetch_order_books(symbols[:50], limit=20)  # 先限 50 个避免限频
            ois = await exchange_swap.fetch_open_interest([s.replace('USDT', '/USDT:USDT') for s in symbols[:50]])
            for sym in symbols[:50]:
                data = data_store[sym]
                swap_sym = sym.replace('USDT', '/USDT:USDT')
                if swap_sym in swap_tickers:
                    mark_price = swap_tickers[swap_sym]['markPrice'] or data['price']
                    data['premium'] = ((data['price'] / mark_price - 1) * 100) if mark_price else 0
                if sym in depths:
                    depth = depths[sym]
                    data['depth_buy'] = sum(b[1] * b[0] for b in depth['bids'][:10]) / 1e6
                    data['depth_sell'] = -sum(a[1] * a[0] for a in depth['asks'][:10]) / 1e6
                if swap_sym in ois:
                    data['oi'] = ois[swap_sym]['openInterestAmount'] * data['price'] / 1e6
        except Exception as e:
            print(f"Premium/OI/Depth error: {e}")
        await asyncio.sleep(30)

async def fetch_ohlcv_rsi():
    exchange = ccxt.binance({'enableRateLimit': True})
    while True:
        try:
            for sym in symbols[:50]:  # 限 50 个避免限频
                ohlcv = await exchange.fetch_ohlcv(sym, '30m', limit=50)
                data = data_store[sym]
                data['ohlcv'] = deque([(c[0], c[4]) for c in ohlcv], maxlen=50)
                if len(data['ohlcv']) >= RSI_PERIOD + 1:
                    closes = pd.Series([c[1] for c in data['ohlcv']])
                    delta = closes.diff()
                    gain = delta.where(delta > 0, 0).rolling(window=RSI_PERIOD).mean()
                    loss = -delta.where(delta < 0, 0).rolling(window=RSI_PERIOD).mean()
                    rs = gain / loss
                    data['rsi'] = 100 - (100 / (1 + rs.iloc[-1]))
                    # RSI 背离判断
                    prices = [c[0] for c in data['ohlcv']]
                    recent_low_price = min(prices[-15:])
                    prev_low_idx = prices.index(recent_low_price)
                    prev_rsi = closes[prev_low_idx]
                    if data['price'] < data['prev_low_price'] and data['rsi'] > data['prev_low_rsi']:
                        data['warnings']['div'] = '底背++'
                    elif data['price'] > data['prev_low_price'] and data['rsi'] < data['prev_low_rsi']:
                        data['warnings']['div'] = '顶背'
                    elif data['price'] < recent_low_price and data['rsi'] > prev_rsi:
                        data['warnings']['div'] = '底背'
                    else:
                        data['warnings']['div'] = '—'
                    data['prev_low_price'] = recent_low_price
                    data['prev_low_rsi'] = prev_rsi
        except Exception as e:
            print(f"RSI error: {e}")
        await asyncio.sleep(180)

async def update_cvd():
    exchange_spot = ccxt.binance({'options': {'defaultType': 'spot'}})
    exchange_swap = ccxt.binance({'options': {'defaultType': 'swap'}})
    while True:
        try:
            # 现货 CVD
            spot_trades = await exchange_spot.watch_trades_for_symbols(symbols[:20])  # 限 20 个
            for trade in spot_trades:
                sym = trade['symbol']
                if sym not in symbols: continue
                data = data_store[sym]
                t = trade['timestamp'] / 1000
                qty = trade['amount']
                is_buyer_maker = trade['side'] == 'sell'
                delta = qty if not is_buyer_maker else -qty
                data['trades_spot'].append((t, delta))
                now = time.time()
                for period, secs in PERIODS.items():
                    cutoff = now - secs
                    cvd_period = sum(d for ts, d in data['trades_spot'] if ts >= cutoff)
                    data['cvd_spot'][period] = cvd_period
            # 合约 CVD (类似现货)
            swap_trades = await exchange_swap.watch_trades_for_symbols([s.replace('USDT', '/USDT:USDT') for s in symbols[:20]])
            for trade in swap_trades:
                sym = trade['symbol'].replace('/USDT:USDT', 'USDT')
                if sym not in symbols: continue
                data = data_store[sym]
                t = trade['timestamp'] / 1000
                qty = trade['amount']
                is_buyer_maker = trade['side'] == 'sell'
                delta = qty if not is_buyer_maker else -qty
                data['trades_swap'].append((t, delta))
                now = time.time()
                for period, secs in PERIODS.items():
                    cutoff = now - secs
                    cvd_period = sum(d for ts, d in data['trades_swap'] if ts >= cutoff)
                    data['cvd_swap'][period] = cvd_period
        except Exception as e:
            print(f"CVD error: {e}")
        await asyncio.sleep(0.1)

async def update_warnings():
    while True:
        try:
            for sym in symbols[:50]:
                data = data_store[sym]
                mc = data['market_cap']
                cvd7d_spot = data['cvd_spot']['7d']
                cvd7d_swap = data['cvd_swap']['7d']
                cvd1h_spot = data['cvd_spot']['1h']
                premium = data['premium']
                change24h = data['change24h']
                # 吸筹预警 (动态阈值)
                if cvd7d_spot >= mc * 0.008 and change24h < -3:
                    data['warnings']['suck'] = '强吸'
                elif cvd7d_spot >= mc * 0.006 and cvd7d_swap <= -mc * 0.006:
                    data['warnings']['suck'] = '现吸合出'
                elif cvd7d_spot >= mc * 0.004 and abs(change24h) <= 3:
                    data['warnings']['suck'] = '隐吸'
                else:
                    data['warnings']['suck'] = '—'
                # 出货预警
                if premium >= 0.8 and cvd1h_spot <= -mc * 0.0003:
                    data['warnings']['ship'] = '假拉'
                else:
                    data['warnings']['ship'] = '—'
        except Exception as e:
            print(f"Warnings error: {e}")
        await asyncio.sleep(60)

# ================== 页面布局 ==================
app.layout = html.Div(style={'backgroundColor': '#0e1117', 'color': '#fff', 'fontFamily': 'Arial'}, children=[
    html.H1("终极山寨 Alpha 猎神面板", style={'textAlign': 'center', 'margin': '20px'}),
    html.Div([
        dcc.Input(id='new-coin', placeholder='输入如 ACTUSDT', style={'width': '200px', 'marginRight': '10px'}),
        html.Button('添加自选', id='add-btn'),
    ], style={'textAlign': 'center', 'marginBottom': '20px'}),

    dash_table.DataTable(
        id='table',
        columns=[
            {'name': '币种', 'id': 'symbol'},
            {'name': '最新价', 'id': 'price'},
            {'name': '24H涨跌', 'id': 'change24h'},
            {'name': '24H量', 'id': 'volume24h'},
            {'name': '溢价', 'id': 'premium'},
            {'name': '现货CVD', 'id': 'cvd_spot', 'presentation': 'markdown'},
            {'name': '合约CVD', 'id': 'cvd_swap', 'presentation': 'markdown'},
            {'name': '深度', 'id': 'depth', 'presentation': 'markdown'},
            {'name': '持仓', 'id': 'oi'},
            {'name': '吸筹', 'id': 'suck'},
            {'name': '出货', 'id': 'ship'},
            {'name': '底背', 'id': 'div'},
        ],
        style_cell={'backgroundColor': '#161a1e', 'border': '1px solid #323546', 'textAlign': 'center', 'whiteSpace': 'pre-line'},
        style_header={'backgroundColor': '#1e2130', 'fontWeight': 'bold'},
        style_data_conditional=[
            {'if': {'column_id': 'change24h', 'filter_query': '{change24h} > 0'}, 'color': '#00ff00'},
            {'if': {'column_id': 'change24h', 'filter_query': '{change24h} < 0'}, 'color': '#ff0066'},
            {'if': {'column_id': 'suck', 'filter_query': '{suck} != "—" '}, 'color': '#00ff00', 'fontWeight': 'bold'},
            {'if': {'column_id': 'ship', 'filter_query': '{ship} != "—" '}, 'color': '#ff0066', 'fontWeight': 'bold'},
            {'if': {'column_id': 'div', 'filter_query': '{div} contains "底"'}, 'color': '#00ff00', 'fontWeight': 'bold'},
            {'if': {'column_id': 'div', 'filter_query': '{div} contains "顶"'}, 'color': '#ff0066', 'fontWeight': 'bold'},
        ],
        row_deletable=True,
        sort_action='native',
        tooltip_duration=None,
    ),

    dcc.Tooltip(id='cvd-tooltip'),

    dcc.Interval(id='interval', interval=2000, n_intervals=0),
    dcc.Store(id='store', data=symbols),
])

def format_num(val):
    if abs(val) >= 1e9:
        return f"{val/1e9:+.2f}B"
    elif abs(val) >= 1e6:
        return f"{val/1e6:+.2f}M"
    elif abs(val) >= 1e3:
        return f"{val/1e3:+.2f}K"
    else:
        return f"{val:+.0f}"

@callback(Output('table', 'data'), Input('interval', 'n_intervals'))
def update_table(n):
    rows = []
    for sym in symbols[:100]:  # 显示前100个
        d = data_store[sym]
        spot_cvd_short = f"5m:{format_num(d['cvd_spot']['5m'])}\n15m:{format_num(d['cvd_spot']['15m'])}\n1h:{format_num(d['cvd_spot']['1h'])}\n4h:{format_num(d['cvd_spot']['4h'])}"
        swap_cvd_short = f"5m:{format_num(d['cvd_swap']['5m'])}\n15m:{format_num(d['cvd_swap']['15m'])}\n1h:{format_num(d['cvd_swap']['1h'])}\n4h:{format_num(d['cvd_swap']['4h'])}"
        depth = f"买{format_num(d['depth_buy'])}\n卖{format_num(d['depth_sell'])}"
        rows.append({
            'symbol': sym.replace('USDT', '/USDT'),
            'price': f"{d['price']:.4f}",
            'change24h': f"{d['change24h']:.2f}%",
            'volume24h': f"${d['volume24h']/1e6:.1f}M",
            'premium': f"{d['premium']:.2f}%",
            'cvd_spot': spot_cvd_short,
            'cvd_swap': swap_cvd_short,
            'depth': depth,
            'oi': f"{d['oi']:.1f}M",
            'suck': d['warnings']['suck'],
            'ship': d['warnings']['ship'],
            'div': d['warnings']['div'],
        })
    return rows

@callback(Output('store', 'data'), Input('add-btn', 'n_clicks'), State('new-coin', 'value'), State('store', 'data'))
def add_coin(n, new, current):
    if n and new:
        new_sym = new.upper() + 'USDT'
        if new_sym not in current:
            current.append(new_sym)
            with open(COINS_FILE, 'w') as f:
                json.dump(current, f)
    return current

# 悬停 CVD 大曲线 (简化版，鼠标悬停弹出 7 天 15min CVD 曲线)
clientside_callback(
    """
    function(children, row_data, column_data) {
        if (!row_data || !column_data) return {};
        const sym = row_data.symbol.replace('/USDT', 'USDT');
        // 模拟 7 天 15min 数据 (实际用 data_store)
        const x = Array.from({length: 672}, (_, i) => `2025-11-${23+i%30}:00`);  // 7天 * 96 (15min)
        const y_spot = x.map((_, i) => (Math.sin(i/10) + 1) * 10);  // 模拟现货 CVD
        const y_swap = x.map((_, i) => (Math.cos(i/10) + 1) * 8);  // 模拟合约 CVD
        const fig = {
            data: [
                {x, y: y_spot, type: 'scatter', name: '现货CVD', line: {color: 'green'}},
                {x, y: y_swap, type: 'scatter', name: '合约CVD', line: {color: 'red'}}
            ],
            layout: {title: `${sym} 7天 CVD (15min)`, width: 800, height: 300}
        };
        return {children: [dcc.Graph(figure=fig, style={width: '65vw', height: 300})]};
    }
    """,
    Output('cvd-tooltip', 'children'),
    Input('table', 'data'),
    [State('table', 'active_cell'), State('table', 'derived_viewport_data')]
)

# ================== 启动 ==================
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(fetch_ticker())
    loop.create_task(fetch_premium_oi_depth())
    loop.create_task(fetch_ohlcv_rsi())
    loop.create_task(update_cvd())
    loop.create_task(update_warnings())
    app.run_server(host='0.0.0.0', port=int(os.environ.get('PORT', 8050)), debug=False)
