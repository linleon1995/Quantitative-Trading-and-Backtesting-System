import asyncio
import json
import logging
import time
from datetime import datetime

import websockets

from src.client.binance_api import BinanceAPI
from src.data_process.data_structure import GeneralTickData
from src.event import telegram_bot
from src.strategies import moving_average
from src.strategies.dynamic_breakout_atx import DynamicBreakoutTrader

all_symbols = {}
tradded = set()

logging.basicConfig(filename='logs/trading_log.log', level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s')

async def connect_to_websocket(uri, symbols, id, coin_meta_pool, strategy_pool):
    subscribe_message = {
        "method": "SUBSCRIBE",
        "params": symbols,
        "id": id
    }
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                # print(f"Connected to {uri}")
                await websocket.send(json.dumps(subscribe_message))
                # Subscribe to the streams
                await subscribe_to_klines(websocket, coin_meta_pool, strategy_pool)
        except Exception as e:
            logging.info("Connection closed unexpectedly. Reconnecting...")
            await asyncio.sleep(5)  # Wait for a few seconds before attempting to reconnect
            continue


async def subscribe_to_klines(websocket, coin_meta_pool, strategy_pool):
    while True:
        response = await websocket.recv()
        response_data = json.loads(response)
        
        # Get coin data
        if response_data.get('result', True) is None:
            time.sleep(1e-4)
            continue
        symbol = response_data['s']
        if coin_meta_pool.get(symbol, None) is None:
            coin_meta_pool[symbol] = GeneralTickData(
                symbol, maxlen=100, moving_average_spans=[7, 25, 99])
        close_price = float(response_data['k']['c'])
        volume = float(response_data['k']['v'])
        
        if all_symbols.get(symbol, '') != response_data['k']['T']:
            all_symbols[symbol] = response_data['k']['T']
            coin_meta_pool[symbol].put_tick(tick=close_price, unix_time=response_data['k']['T'])
            # draw(symbol, timestamps=coin_meta_pool[symbol].time, ticks=coin_meta_pool[symbol].ticks, save_path=f'image/{symbol}.png')
        else:
            # time.sleep(1)
            continue

        num_coin = len(all_symbols)
        timestamp = datetime.fromtimestamp(response_data['k']['T'] / 1000)
        logging.info(f"{timestamp} - {symbol}, Close Price: {close_price}, Ticks: {len(coin_meta_pool[symbol].ticks)}, Total Coins: {num_coin}")

        # if not coin_meta_pool[symbol].isValid:
        #     continue

        # for strategy in strategy_pool:
        #     trade_singal = strategy.run(coin_meta_pool[symbol])
        #     if trade_singal:
        #         tradded.add(symbol)
        #         telegram_bot.send_msg(f"{datetime.now()} {strategy.strategy_name} Symbol: {symbol}, Close Price: {close_price}")

        # if datetime.now().minute % 30 == 0:
        #     num_tradded = len(tradded)
        #     telegram_bot.send_msg(f"{datetime.now()} {num_tradded}/{num_coin} tradded coins. {num_tradded/num_coin*100:.2f} % ---")

        tick = (timestamp, {'close_price': close_price, 'volume': volume})
        strategy_pool[symbol].on_tick(*tick)
        # collected.append(symbol)
        # if timestamp.second:
        if timestamp.minute % 10 == 0:
            avg_earn = 0
            for symbol, strategy in strategy_pool.items():
                total_earn = sum(trade['earn'] for trade in strategy.trade_records)
                avg_earn += total_earn
            telegram_bot.send_msg(f"{datetime.now()} {strategy_pool.keys()} {avg_earn/len(strategy_pool)} %")


async def main():
    uri = "wss://stream.binance.com:9443/ws"
    stream_per_task = 10

    binance_api = BinanceAPI()
    ticker_prices = binance_api.get_usdt_ticker(bridge='USDT')
    symbols = [f"{coin['symbol'].lower()}@kline_1m" for idx, coin in enumerate(ticker_prices)]
    symbols = symbols[:2]
    # symbols = symbols[6:7]
    total_symbols = [coin['symbol'] for idx, coin in enumerate(ticker_prices)]
    # symbols = ['idexusdt@kline_1m', 'minausdt@kline_1m', 'ardrusdt@kline_1m', 'nbtusdt@kline_1m', 'fidausdt@kline_1m', 'sysusdt@kline_1m']
    # symbols = ['idexusdt@kline_1m', 'minausdt@kline_1m', 'ardrusdt@kline_1m', 'nbtusdt@kline_1m', 'fidausdt@kline_1m', 'sysusdt@kline_1m', 'lqtyusdt@kline_1m', 'aeurusdt@kline_1m', 'kncusdt@kline_1m', 'cvcusdt@kline_1m', 'dotdownusdt@kline_1m', 'busdusdt@kline_1m', 'beamxusdt@kline_1m', 'wanusdt@kline_1m', 'synusdt@kline_1m', 'oaxusdt@kline_1m', 'astusdt@kline_1m', 'xmrusdt@kline_1m', 'wbtcusdt@kline_1m', 'reefusdt@kline_1m', 'bnbdownusdt@kline_1m', 'snxusdt@kline_1m', 'pundixusdt@kline_1m', 'dentusdt@kline_1m', 'nmrusdt@kline_1m', 'ambusdt@kline_1m', 'idusdt@kline_1m', 'linkupusdt@kline_1m', 'pyrusdt@kline_1m', 'winusdt@kline_1m', 'eduusdt@kline_1m', 'arpausdt@kline_1m', 'dydxusdt@kline_1m', 'celrusdt@kline_1m', 'batusdt@kline_1m', 'bkrwusdt@kline_1m', 'eosupusdt@kline_1m', 'agixusdt@kline_1m', 'beamusdt@kline_1m', 'runeusdt@kline_1m', 'viteusdt@kline_1m', 'apeusdt@kline_1m', 'wavesusdt@kline_1m', 'omusdt@kline_1m', 'flowusdt@kline_1m', 'ssvusdt@kline_1m', 'sushiupusdt@kline_1m', 'lptusdt@kline_1m', 'bandusdt@kline_1m', 'umausdt@kline_1m', 'enjusdt@kline_1m', 'audusdt@kline_1m', 'hbarusdt@kline_1m', 'stptusdt@kline_1m', 'algousdt@kline_1m', 'nbsusdt@kline_1m', 'auctionusdt@kline_1m', 'vetusdt@kline_1m', 'gtousdt@kline_1m', 'sunusdt@kline_1m', 'trxupusdt@kline_1m', 'truusdt@kline_1m', 'diausdt@kline_1m', 'tusdt@kline_1m', 'mdtusdt@kline_1m', 'filusdt@kline_1m', 'mftusdt@kline_1m', 'funusdt@kline_1m', 'qiusdt@kline_1m', 'mirusdt@kline_1m', 'qntusdt@kline_1m', 'spellusdt@kline_1m', 'belusdt@kline_1m', 'ntrnusdt@kline_1m', 'arusdt@kline_1m', 'kavausdt@kline_1m', 'lskusdt@kline_1m', 'solusdt@kline_1m', 'badgerusdt@kline_1m', 'ernusdt@kline_1m', 'creamusdt@kline_1m', 'zrxusdt@kline_1m', 'ctxcusdt@kline_1m', 'dogeusdt@kline_1m', 'multiusdt@kline_1m', 'sushiusdt@kline_1m', 'kmdusdt@kline_1m', 'xtzupusdt@kline_1m', 'bnbbearusdt@kline_1m', 'aliceusdt@kline_1m', 'rdntusdt@kline_1m', 'drepusdt@kline_1m', 'astrusdt@kline_1m', 'btcupusdt@kline_1m', 'thetausdt@kline_1m', 'pepeusdt@kline_1m', 'trbusdt@kline_1m', 'keepusdt@kline_1m', 'lunausdt@kline_1m', 'mavusdt@kline_1m', 'xrpbearusdt@kline_1m', 'perpusdt@kline_1m', 'betausdt@kline_1m', 'iotxusdt@kline_1m', 'adadownusdt@kline_1m', 'tiausdt@kline_1m', 'alcxusdt@kline_1m', 'ookiusdt@kline_1m', 'xnousdt@kline_1m', 'ckbusdt@kline_1m', 'kdausdt@kline_1m', 'mtlusdt@kline_1m', 'datausdt@kline_1m', 'promusdt@kline_1m', 'hiveusdt@kline_1m', 'seiusdt@kline_1m', 'ksmusdt@kline_1m', 'xtzusdt@kline_1m', 'scrtusdt@kline_1m', 'frontusdt@kline_1m', 'nuusdt@kline_1m', 'btsusdt@kline_1m', 'bnbupusdt@kline_1m', 'atomusdt@kline_1m', 'ltousdt@kline_1m', 'xrpupusdt@kline_1m', 'vthousdt@kline_1m', 'ctsiusdt@kline_1m', 'btgusdt@kline_1m', 'opusdt@kline_1m', 'gnsusdt@kline_1m', 'polyusdt@kline_1m', 'aiusdt@kline_1m', 'bntusdt@kline_1m', 'cyberusdt@kline_1m', 'aionusdt@kline_1m', 'uniupusdt@kline_1m', 'btcusdt@kline_1m', 'grtusdt@kline_1m', 'manausdt@kline_1m', 'fildownusdt@kline_1m', 'keyusdt@kline_1m', 'bakeusdt@kline_1m', 'bccusdt@kline_1m', 'osmousdt@kline_1m', 'aptusdt@kline_1m', 'aceusdt@kline_1m', 'xvsusdt@kline_1m', 'nulsusdt@kline_1m', 'dockusdt@kline_1m', 'flmusdt@kline_1m', 'ogusdt@kline_1m', 'cosusdt@kline_1m', 'ankrusdt@kline_1m', 'vgxusdt@kline_1m', 'dotusdt@kline_1m', 'fisusdt@kline_1m', 'ongusdt@kline_1m', 'elfusdt@kline_1m', 'tribeusdt@kline_1m', 'xrpdownusdt@kline_1m', '1000satsusdt@kline_1m', 'fetusdt@kline_1m', 'aavedownusdt@kline_1m', 'irisusdt@kline_1m', 'gftusdt@kline_1m', 'fiousdt@kline_1m', 'nfpusdt@kline_1m', 'wingusdt@kline_1m', 'sklusdt@kline_1m', 'acmusdt@kline_1m', 'duskusdt@kline_1m', 'ampusdt@kline_1m', 'cocosusdt@kline_1m', 'tornusdt@kline_1m', 'bondusdt@kline_1m', 'ltcupusdt@kline_1m', 'sushidownusdt@kline_1m', 'xtzdownusdt@kline_1m', 'alphausdt@kline_1m', 'requsdt@kline_1m', 'gtcusdt@kline_1m', 'injusdt@kline_1m', 'uniusdt@kline_1m', 'rayusdt@kline_1m', 'pendleusdt@kline_1m', 'troyusdt@kline_1m', 'cvpusdt@kline_1m', 'arkmusdt@kline_1m', 'roseusdt@kline_1m', 'atausdt@kline_1m', 'ordiusdt@kline_1m', 'gbpusdt@kline_1m', 'filupusdt@kline_1m', 'achusdt@kline_1m', 'btcdownusdt@kline_1m', 'laziousdt@kline_1m', 'bchdownusdt@kline_1m', 'pntusdt@kline_1m', 'oneusdt@kline_1m', 'mboxusdt@kline_1m', 'bswusdt@kline_1m', 'wrxusdt@kline_1m', 'ltcdownusdt@kline_1m', 'ancusdt@kline_1m', 'adaupusdt@kline_1m', 'jasmyusdt@kline_1m', 'farmusdt@kline_1m', 'hookusdt@kline_1m', 'ethusdt@kline_1m', 'repusdt@kline_1m', 'bethusdt@kline_1m', 'paxusdt@kline_1m', 'firousdt@kline_1m', 'bonkusdt@kline_1m', 'npxsusdt@kline_1m', 'epxusdt@kline_1m', 'hotusdt@kline_1m', 'mcousdt@kline_1m', 'aaveupusdt@kline_1m', 'phausdt@kline_1m', 'quickusdt@kline_1m', 'adausdt@kline_1m', 'tctusdt@kline_1m', 'srmusdt@kline_1m', 'yfiupusdt@kline_1m', 'polsusdt@kline_1m', 'klayusdt@kline_1m', 'eosbearusdt@kline_1m', 'rampusdt@kline_1m', 'woousdt@kline_1m', 'loomusdt@kline_1m', 'stmxusdt@kline_1m', 'cotiusdt@kline_1m', 'reiusdt@kline_1m', 'mkrusdt@kline_1m', 'glmrusdt@kline_1m', 'alpineusdt@kline_1m', 'ltcusdt@kline_1m', 'mblusdt@kline_1m', 'rndrusdt@kline_1m', 'prosusdt@kline_1m', 'rsrusdt@kline_1m', 'waxpusdt@kline_1m', 'mantausdt@kline_1m', 'movrusdt@kline_1m', 'leverusdt@kline_1m', 'vicusdt@kline_1m', 'rvnusdt@kline_1m', 'iostusdt@kline_1m', 'qtumusdt@kline_1m', 'zecusdt@kline_1m', 'hcusdt@kline_1m', 'nexousdt@kline_1m', 'c98usdt@kline_1m', 'psgusdt@kline_1m', 'iqusdt@kline_1m', 'hftusdt@kline_1m', 'qkcusdt@kline_1m', 'stormusdt@kline_1m', 'maskusdt@kline_1m', 'neblusdt@kline_1m', 'xvgusdt@kline_1m', 'mithusdt@kline_1m', 'ethbearusdt@kline_1m', 'plausdt@kline_1m', 't@kline_1m', 'zenusdt@kline_1m', 'avausdt@kline_1m', 'darusdt@kline_1m', 'steemusdt@kline_1m', 'nanousdt@kline_1m', 'luncusdt@kline_1m', 'forthusdt@kline_1m', 'xemusdt@kline_1m', 'atmusdt@kline_1m', 'akrousdt@kline_1m', 'galausdt@kline_1m', 'fluxusdt@kline_1m', 'xecusdt@kline_1m', 'tomousdt@kline_1m', 'rlcusdt@kline_1m', 'bzrxusdt@kline_1m', 'bttcusdt@kline_1m', 'jtousdt@kline_1m', 'xrpbullusdt@kline_1m', 'autousdt@kline_1m', 'ontusdt@kline_1m', 'bchsvusdt@kline_1m', 'venusdt@kline_1m', 'superusdt@kline_1m', 'galusdt@kline_1m', 'burgerusdt@kline_1m', 'ghstusdt@kline_1m', 'ensusdt@kline_1m', '1inchusdt@kline_1m', 'linausdt@kline_1m', 'bttusdt@kline_1m', 'tvkusdt@kline_1m', 'clvusdt@kline_1m', 'mcusdt@kline_1m', 'yfiiusdt@kline_1m', 'sxpupusdt@kline_1m', 'bearusdt@kline_1m', 'ustcusdt@kline_1m', 'etcusdt@kline_1m', 'btcstusdt@kline_1m', 'audiousdt@kline_1m', 'dcrusdt@kline_1m', 'juvusdt@kline_1m', 'gmtusdt@kline_1m', 'wbethusdt@kline_1m', 'tusdusdt@kline_1m', 'daiusdt@kline_1m', 'dodousdt@kline_1m', 'mlnusdt@kline_1m', 'cityusdt@kline_1m', 'bchusdt@kline_1m', 'crvusdt@kline_1m', 'hntusdt@kline_1m', 'stxusdt@kline_1m', 'eosusdt@kline_1m', 'imxusdt@kline_1m', 'dashusdt@kline_1m', 'hardusdt@kline_1m', 'litusdt@kline_1m', 'sntusdt@kline_1m', 'dfusdt@kline_1m', 'tkousdt@kline_1m', 'bchabcusdt@kline_1m', 'linkusdt@kline_1m', 'sxpdownusdt@kline_1m', 'neousdt@kline_1m', 'degousdt@kline_1m', 'gnousdt@kline_1m', 'ctkusdt@kline_1m', 'ognusdt@kline_1m', 'xaiusdt@kline_1m', 'shibusdt@kline_1m', 'pivxusdt@kline_1m', 'usdpusdt@kline_1m', 'trxdownknusdt@kline_1m', 'portousdt@kline_1m', 'asrusdt@kline_1m', 'stgusdt@kline_1m', 'ldousdt@kline_1m', 'bnbusdt@kline_1m', 'balusdt@kline_1m', 'unidownusdt@kline_1m', 'barusdt@kline_1m', 'api3usdt@kline_1m', 'cakeusdt@kline_1m', 'aergousdt@kline_1m', 'flokiusdt@kline_1m', 'wldusdt@kline_1m', 'radusdt@kline_1m', 'vanryusdt@kline_1m', 'utkusdt@kline_1m', 'bifiusdt@kline_1m', 'rifusdt@kline_1m', 'bchupusdt@kline_1m', 'gasusdt@kline_1m', 'bullusdne_1m', 'agldusdt@kline_1m', 'gmxusdt@kline_1m', 'eurusdt@kline_1m', 'sfpusdt@kline_1m', 'hifiusdt@kline_1m', 'combousdt@kline_1m', 'ornusdt@kline_1m', 'xzcusdt@kline_1m', 'zilusdt@kline_1m', 'trxusdt@kline_1m', 'renusdt@kline_1m', 'chessusdt@kline_1m', 'icxusdt@kline_1m', 'alpacausdt@kline_1m', 'compusdt@kline_1m', 'unfiusdt@kline_1m', 'epsusdt@kline_1m', 'pondusdt@kline_1m', 'cvxusdt@kline_1m', 'celousdt@kline_1m', 'storjusdt@kline_1m', 'stratusdt@kline_1m', 'polyxusdt@kline_1m', 'glmusdt@kline_1m', 'usdsusdt@kline_1m', 'eosbullusdt@kline_1m', 'gxsusdt@kline_1m', 'anyusdt@kline_1m', 'arbusdt@kline_1m', 'yfidownusdt@kline_1m', 'voxelusdt@kline_1m', 'highusdt@kline_1m', 'lokausdt@kline_1m', 'maticusdt@kline_1m', 'lendusdt@kline_1m', 'dntusdt@kline_1m', 'cfxusdt@kline_1m', 'dgbusdt@kline_1m', 'forusdt@kline_1m', 'mobusdt@kline_1m', 'ethbullusdt@kline_1m', 'phbusdt@kline_1m', \
    #         'yggusdt@kline_1m', 'rareusdt@kline_1m', 'scusdt@kline_1m', 'tfuelusdt@kline_1m', 'santosusdt@kline_1m', 'acausdt@kline_1m', 'ilvusdt@kline_1m', 'jstusdt@kline_1m', 'usdcusdt@kline_1m', 'wnxmusdt@kline_1m', 'kp3rusdt@kline_1m', 'nearusdt@kline_1m', 'ustusdt@kline_1m', 'xlmupusdt@kline_1m', 'xlmusdt@kline_1m', 'blurusdt@kline_1m', 'dexeusdt@kline_1m', 'egldusdt@kline_1m', 'peopleusdt@kline_1m', 'fdusdusdt@kline_1m', 'xrpusdt@kline_1m']
    # symbols = symbols[:200]
    # symbols = ['uniusdt@kline_1m', 'pendleusdt@kline_1m', 'ethusdt@kline_1m']

    # tasks = [subscribe_to_klines(uri, [symbol], id) for id, symbol in enumerate(symbols, 1)]
    tasks = []
    coin_meta_pool = {}
    ma_strategy = moving_average.Strategy(
        ma_gap_rates=[1.008, 1.008],
        ma_grow_rates=[1.0005, 1.0005, 1.0005],
        count_threshold=5
    )
    strategy_pool = [ma_strategy]
    for idx in range(0, len(symbols), stream_per_task):
        strategy_pool = {symbol.split('@')[0].upper(): DynamicBreakoutTrader(symbol=symbol.split('@')[0].upper()) 
                         for symbol in symbols[idx:idx+stream_per_task]}
        tasks.append(connect_to_websocket(uri, symbols[idx:idx+stream_per_task], idx, coin_meta_pool, strategy_pool))
        
    await asyncio.gather(*tasks, return_exceptions=False)


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
