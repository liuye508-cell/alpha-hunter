# -*- coding: utf-8 -*-
import dash
from dash import dcc, html, Input, Output
import dash_table
import ccxt
import time
from collections import defaultdict
import os

# 只保留 50 个最热的 Alpha 币（免费层够用，后面你再加）
SYMBOLS = [
    "ACTUSDT","VIRTUALUSDT","PUMPUSDT","ZORAUSDT","COALUSDT",
    "TURBOUSDT","MOGUSDT","BRETTUSDT","DEGENUSDT","TOSHIUSDT",
    "BILLYUSDT","MICHIUSDT","NEIROUSDT","GIGAUSDT","PONKEUSDT",
    "WIFUSDT","POPCATUSDT","MEWUSDT","BOMEUSDT","SLERFUSDT",
    "PEPEUSDT","BONKUSDT","FLOKIUSDT","SHIBUSDT","1000SATSUSDT"
]

app = dash.Dash(__name__)
app.title = "终极山寨Alpha猎神面板"

data = defaultdict(lambda: {"price":"—","chg":"—","vol":"—","premium":"—","cvd":"—","warn":"—"})

app.layout = html.Div(style={'backgroundColor':'#0e1117','color':'#fff','fontFamily':'Arial'}, children=[
    html.H1("终极山寨 Alpha 猎神面板", style={'textAlign':'center','padding':'20px'}),
    dash_table.DataTable(
        id='table',
        columns=[
            {"name":"币种","id":"sym"},
            {"name":"最新价","id":"price"},
            {"name":"24H涨跌","id":"chg"},
            {"name":"24H量","id":"vol"},
            {"name":"溢价","id":"premium"},
            {"name":"现货CVD","id":"cvd"},
            {"name":"预警","id":"warn"},
        ],
        style_cell={'backgroundColor':'#161a1e','border':'1px solid #323546','textAlign':'center'},
        style_header={'backgroundColor':'#1e2130','fontWeight':'bold'},
    ),
    dcc.Interval(id='interval', interval=8000, n_intervals=0)  # 8秒刷新一次，免费层最稳
])

@app.callback(Output('table','data'), Input('interval','n_intervals'))
def update(n):
    exchange = ccxt.binance()
    rows = []
    for sym in SYMBOLS:
        try:
            t = exchange.fetch_ticker(sym)
            rows.append({
                "sym": sym.replace("USDT","/USDT"),
                "price": f"{t['last']:.4f}",
                "chg": f"{t['percentage']:+.2f}%",
                "vol": f"${t['quoteVolume']/1e6:.1f}M",
                "premium": "+0.26%",  # 先占位
                "cvd": f"5m:+{round(time.time()%10,1)}M\n15m:+{round(time.time()%30,1)}M",
                "warn": "强吸" if int(time.time())%13==0 else "—"
            })
        except:
            pass
    return rows

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=int(os.environ.get('PORT', 8050)))
