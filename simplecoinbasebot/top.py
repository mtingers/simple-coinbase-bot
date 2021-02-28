"""
TODO:
    1. Refactor code so it's organized (now that I have an idea of what it'll do)
    2. Add more sorting by changing stat dict to something that's easier to sort
"""
import os
import sys
import glob
import pickle
from decimal import Decimal
import time
from pprint import pprint
from os import system, name
from datetime import timedelta, datetime
import threading
import re
from collections import OrderedDict
from operator import getitem
from .color import colors
from .getch import getch, getchb
from .termsize import get_terminal_size
import cbpro

os.environ['TZ'] = 'UTC'
time.tzset()

GETCH_LOCK = threading.Lock()
g_last_input = None
g_filter = ''
g_paused = False
g_show_orders = False
g_print_buf = ''

PRICE_CACHE = {}
PRICE_CACHE_RATE = 83.1331 #update every N seconds

def pdiff(old, new):
    try:
        return round(( (Decimal(new) - Decimal(old)) / Decimal(old)) * Decimal('100.0'), 2)
    except:
        return 'unk'

def parse_datetime(d):
    return str(d).split('.')[0].split('Z')[0]

def print_b(msg):
    global g_print_buf
    g_print_buf = '{}{}\n'.format(g_print_buf, msg)

def clear():
    #global g_print_buf
    #g_print_buf = ''
    if name == 'nt':
        system('cls')
    else:
        system('clear')

def get_current_price(coin):
    last_update = time.time()
    current_price = Decimal('0.0')
    if not coin in PRICE_CACHE:
        public_client = cbpro.PublicClient()
        ticker = public_client.get_product_ticker(product_id=coin)
        try:
            current_price = Decimal(ticker['price'])
        except Exception as err:
            return None
    else:
        # check cache age
        if time.time() - PRICE_CACHE[coin]['last_update'] > PRICE_CACHE_RATE:
            public_client = cbpro.PublicClient()
            ticker = public_client.get_product_ticker(product_id=coin)
            current_price = Decimal(ticker['price'])
        else:
            last_update = PRICE_CACHE[coin]['last_update']
            current_price  = PRICE_CACHE[coin]['price']
    PRICE_CACHE[coin] = {'price':current_price, 'last_update':last_update}
    return Decimal(current_price)

def get_input():
    global g_last_input
    global g_paused
    global g_filter
    global g_show_orders
    while 1:
        with GETCH_LOCK:
            g_last_input = getch()
        if g_last_input == 'q':
            print('exiting...')
            break
        elif g_last_input == 'o':
            g_show_orders = True
        elif g_last_input == 's':
            g_show_orders = False
        elif g_last_input == 'f':
            with GETCH_LOCK:
                g_paused = True
                buf = 'Enter filter regex (e.g. BT.*): '
                start_len = len(buf)
                c = ''
                fbuf = ''
                sys.stdout.write('\n')
                sys.stdout.write(buf)
                sys.stdout.flush()
                skip_next = 0
                while c not in ('\n', '\r'):
                    c = getchb()
                    # skip escape sequence (arrow keys, etc)
                    if ord(c) == 27:
                        skip_next = 1
                        continue
                    if skip_next == 1:
                        skip_next = 2
                        continue
                    if skip_next == 2:
                        skip_next = 0
                        continue
                    if ord(c) == 127:
                        if len(buf) > start_len:
                            buf = buf[:-1]
                            sys.stdout.write('\r')
                            sys.stdout.write(buf+' ')
                        if fbuf:
                            fbuf = fbuf[:-1]
                    elif c == '\n':
                        break
                    else:
                        buf += c
                        fbuf += c
                    sys.stdout.write('\r')
                    sys.stdout.write(buf)
                    sys.stdout.flush()

                g_filter = fbuf.strip()
                print('\n')
                try:
                    re.compile(g_filter, flags=re.IGNORECASE)
                except:
                    print('Failed to compile regex: {}'.format(g_filter))
                    g_filter = ''
                g_paused = False
        time.sleep(0.001)

def draw_line(thickness):
    if thickness == 1:
        print('{}{}{}'.format(colors.fg.darkgrey, u'\u2581'*80, colors.reset))
    elif thickness == 2:
        print('{}{}{}'.format(colors.fg.darkgrey, u'\u2582'*80, colors.reset))
    elif thickness == 3:
        print('{}{}{}'.format(colors.fg.darkgrey, u'\u2583'*80, colors.reset))
    elif thickness == 4:
        print('{}{}{}'.format(colors.fg.darkgrey, u'\u2584'*80, colors.reset))
    elif thickness == 5:
        print('{}{}{}'.format(colors.fg.darkgrey, u'\u2585'*80, colors.reset))
    else:
        print('{}{}{}'.format(colors.fg.darkgrey, u'\u2586'*80, colors.reset))

def sec2time(sec):
    if hasattr(sec,'__len__'):
        return [sec2time(s) for s in sec]
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    pattern = r'%2dh %2dm %2ds'
    if h == 0 and m == 0:
        return r'%2ds' % (s)
    if h == 0 and d == 0:
        return r'%2dm %2ds' % (m, s)
    if d == 0:
        #return pattern % (h, m, s)
        return r'%2dh %2dm %2ds'  % (h, m, s)
    return ('%dd' + pattern) % (d, h, m, s)

def avg(l):
    if len(l) < 1:
        return Decimal(0.0)
    return Decimal(sum(l))/len(l)


def show_orders():
    files = glob.glob(sys.argv[1]+'/*.cache')
    if not files:
        print('ERROR: empty directory')
        exit(1)
    stats = {}
    stats_incomplete = {}
    recent = []
    cur_time = time.time()
    open_times = []
    profit_dates = {}
    print('[{}q{}]{}uit {}[{}f{}]{}ilter {}[{}s{}]{}tats{:>51} UTC'.format(
        colors.fg.red, colors.reset, colors.fg.lightgrey,
        colors.reset, colors.fg.pink, colors.reset, colors.fg.lightgrey,
        colors.reset, colors.fg.green, colors.reset, colors.fg.lightgrey,
        parse_datetime(datetime.now()))
    )
    draw_line(1)
    print('Open orders:')
    print('{:>15} {:>9} {:>13} {:>13} {:>14} {:>11}'.format(
        'Duration', 'Coin', 'Bought', 'Sell-Price', 'Size', 'Diff%',
    ))
    w, h = get_terminal_size()
    hn = 0
    total = 0
    for f in files:
        data = None
        coin = None
        with open(f, "rb") as fd:
            data = pickle.load(fd)
        if not data:
            continue
        for order_id in data: #.items():
            v = data[order_id]
            data[order_id]['created_at'] = v['first_status']['created_at']
        sorted_data = OrderedDict(sorted(data.items(), key = lambda x: getitem(x[1], 'created_at'), reverse=True))
        #sorted_keys = sorted(data.keys(), reverse=True)
        for order_id, v in sorted_data.items():
            if not v['first_status']:
                continue
            coin = v['first_status']['product_id']
            if g_filter:
                if not re.search(g_filter, coin, re.IGNORECASE):
                    continue
            if v['completed'] or not v['sell_order']:
                continue
            sell = v['sell_order']
            created_at = time.mktime(time.strptime(parse_datetime(sell['created_at']), '%Y-%m-%dT%H:%M:%S'))
            duration = cur_time - created_at
            try:
                price = sell['price']
            except Exception as err:
                price = str(err)
            size = sell['size']
            bought_price = round(Decimal(v['last_status']['executed_value']) / Decimal(v['last_status']['filled_size']), 4)
            if hn+10 < h:
                cur_price = get_current_price(sell['product_id'])
                #print('{:>17} {:>9} {:>16} {:>16} {:>18}'.format(
                print('{:>15} {:>9} {:>13} {:>13} {:>14} {:>11}'.format(
                    sec2time(duration),
                    sell['product_id'],
                    bought_price, price,
                    size,
                    pdiff(bought_price, cur_price),
                    #round(cur_price - bought_price, 2)
                ))
            hn += 1
    if hn > h:
        print('{}... truncated ({}/{} displayed) ...{}'.format(colors.fg.red, h, hn, colors.reset))

def top():
    clear()
    print('')
    if g_show_orders:
        return show_orders()

    files = glob.glob(sys.argv[1]+'/*.cache')
    if not files:
        print('ERROR: empty directory')
        exit(1)
    stats = {}
    stats_incomplete = {}
    recent = []
    cur_time = time.time()
    open_times = []
    profit_dates = {}
    w, h = get_terminal_size()
    hn = 0
    open_percents = []
    for f in files:
        data = None
        coin = None
        with open(f, "rb") as fd:
            data = pickle.load(fd)
        if not data:
            continue

        for order_id, v in data.items():
            if not v['first_status']:
                continue
            coin = v['first_status']['product_id']
            if g_filter:
                if not re.search(g_filter, coin, re.IGNORECASE):
                    continue
            if not coin in stats:
                stats[coin] = {
                    'epoch_diffs':[], 'profits':[], 'profits_total':Decimal('0.0'),
                    'open_orders':0, 'done_orders':0, 'avg_close_time':0.0, 'error_orders':0,
                }
            first_status = v['first_status']
            epoch = time.mktime(time.strptime(parse_datetime(first_status['created_at']), '%Y-%m-%dT%H:%M:%S'))
            if v['completed'] and 'sell_order_completed' in v and v['sell_order_completed'] and v['profit_usd']:
                # NOTE: Getting some completed orders w/o all the information filled in (done_at)
                # This seems to happen when failing to retreive status in the bot code
                date_only = v['sell_order_completed']['done_at'].split('T')[0]
                if not date_only in profit_dates:
                    profit_dates[date_only] = []
                profit_dates[date_only].append(v['profit_usd'])
                end_epoch = time.mktime(time.strptime(parse_datetime(v['sell_order_completed']['done_at']), '%Y-%m-%dT%H:%M:%S'))
                epoch_diff = end_epoch - epoch
                cur_diff = cur_time - end_epoch
                if cur_diff < (86400/12):
                    recent.append((coin, v))
                profit = v['profit_usd']
                stats[coin]['epoch_diffs'].append(epoch_diff)
                stats[coin]['profits'].append(profit)
                stats[coin]['profits_total'] += profit
                stats[coin]['done_orders'] += 1
            elif v['completed']:
                stats[coin]['error_orders'] += 1
            else:
                cur_price = get_current_price(coin)
                try:
                    cur_perc = (100*(cur_price/Decimal(v['sell_order']['price']))) - Decimal('100.0')
                    open_percents.append(cur_perc)
                except Exception as err:
                    # I think sometimes the state drifts after a cancel
                    # and v['sell'] was removed but v['completed'] is not True yet
                    #print('ERR:', err, v['sell_order'])
                    pass
                start_epoch = time.mktime(time.strptime(parse_datetime(v['first_status']['created_at']), '%Y-%m-%dT%H:%M:%S'))
                open_times.append(cur_time - start_epoch)
                stats[coin]['open_orders'] += 1

    #sorted_keys = sorted(stats.keys())
    #sorted_keys = sorted(stats.items(), key=lambda item: item['profits'])
    sorted_keys = OrderedDict(sorted(stats.items(), key = lambda x: getitem(x[1], 'profits_total'), reverse=True))
    print('[{}q{}]{}uit {}[{}f{}]{}ilter {}[{}o{}]{}rders{:>50} UTC'.format(
        colors.fg.red, colors.reset, colors.fg.lightgrey,
        colors.reset, colors.fg.pink, colors.reset, colors.fg.lightgrey,
        colors.reset, colors.fg.blue, colors.reset, colors.fg.lightgrey,
        parse_datetime(datetime.now())
    ))
    draw_line(1)
    print('{}{:>8} {}{:>13} {}{:>7} {}{:>7} {}{:>7} {}{:>12} {}{:>19}{}'.format(
        colors.fg.lightcyan, 'Coin',
        colors.fg.green, 'Profits',
        colors.fg.yellow, 'Open',
        colors.fg.blue, 'Done',
        colors.fg.red, 'Error',
        colors.fg.pink, 'Avg-Profit',
        colors.fg.orange, 'Avg-Time',
        colors.reset,
    ))
    draw_line(1)
    total_profits = Decimal('0.0')
    total_open_orders = 0
    total_done_orders = 0
    total_error_orders = 0
    agg_epoch = []
    agg_profits = []
    for key,v  in sorted_keys.items():
        coin = key
        if not re.search(g_filter, coin, re.IGNORECASE):
            continue
        #v = stats[key]
        if hn+10 < h:
            print('{}{:>8} {}{:>13} {}{:>7} {}{:>7} {}{:>7} {}{:>12} {}{:>19}{}'.format(
                colors.fg.lightcyan, coin,
                colors.fg.green, '$'+str(round(sum(v['profits']), 2)),
                colors.fg.yellow, v['open_orders'],
                colors.fg.blue, v['done_orders'],
                colors.fg.red, v['error_orders'],
                colors.fg.pink, '$'+str(round(avg(stats[coin]['profits']), 2)),
                colors.fg.orange, sec2time(round(avg(v['epoch_diffs']), 2)) if v['epoch_diffs'] else 'None',
                colors.reset,
            ))
        hn += 1
        #if v['epoch_diffs']:
        agg_epoch.append(round(avg(v['epoch_diffs']), 2) if v['epoch_diffs'] else Decimal('0.0'))
        agg_profits.append(round(avg(stats[coin]['profits']), 2))
        total_open_orders += v['open_orders']
        total_done_orders += v['done_orders']
        total_error_orders += v['error_orders']
        total_profits += round(sum(v['profits']), 2)
    if hn+12 < h:
        draw_line(1)
        print('{}{:>8} {}{:>13} {}{:>7} {}{:>7} {}{:>7} {}{:>12} {}{:>19}{}'.format(
                colors.fg.darkgrey, 'all',
                colors.fg.green, '$'+str(total_profits),
                colors.fg.yellow, total_open_orders,
                colors.fg.blue, total_done_orders,
                colors.fg.red, total_error_orders,
                colors.fg.pink, '$'+str(round(avg(agg_profits), 2)),
                colors.fg.orange, sec2time(round(avg(agg_epoch), 2)),
                colors.reset,
        ))
        print('')
        hn += 3
    if hn+10 < h:
        draw_line(3)
    hn += 1
    if open_times:
        min_open_time = sec2time(round(min(open_times), 2))
        max_open_time = sec2time(round(max(open_times), 2))
        avg_open_time = sec2time(round(avg(open_times), 2))
    else:
        min_open_time = Decimal('0.0')
        max_open_time = Decimal('0.0')
        avg_open_time = Decimal('0.0')
    if hn+12 < h:
        print('{}{:>16} {:>16} {:>16} {:>16}'.format(colors.fg.lightgrey, 'Open order times', 'Min', 'Max', 'Avg'))
        print('{}{:>16} {:>16} {:>16} {:>16}'.format(colors.fg.lightred, ' ', min_open_time, max_open_time, avg_open_time))
    hn += 2
    if hn+10 < h:
        cur_drift = round(avg(open_percents), 2)
        if cur_drift < 0:
            print('{}Avg-drift: {}{}%'.format(colors.reset, colors.fg.red, cur_drift))
        else:
            print('{}Avg-drift: {}{}%'.format(colors.reset, colors.fg.green, cur_drift))
    hn+=1
    # Last 7 days with profits
    #print('{}{:>26}'.format(colors.fg.lightgrey, 'Last 7 days profits'))
    sorted_dates_val = OrderedDict(sorted(profit_dates.items(), key = lambda x: x[1], reverse=True))
    sorted_dates = sorted(profit_dates.keys(), reverse=True)
    x = []
    y = []
    for key in sorted_dates[:7]:
        if not re.search(g_filter, key, re.IGNORECASE):
            continue
        val = profit_dates[key]
        date_total = round(sum(val), 2)
        x.append(key)
        y.append(date_total)
        #print(colors.fg.cyan, '    {} {}{:>15}'.format(key, colors.fg.green, '$'+str(date_total)))

    if hn+10 < h:
        draw_line(3)
    hn += 1
    if y:
        total_profit = []
        max_y = max(y)
        width = 50
        for i in range(len(y)):
            key = x[i]
            yy = y[i]
            nstars = int((yy/max_y) * width)
            if hn+10 < h:
                print('{}{}{}{:>11} {}{}'.format(colors.fg.cyan, key, colors.fg.green, '$'+str(yy), colors.fg.darkgrey, '*'*nstars))
            hn += 1
            total_profit.append(yy)
        if hn+10 < h:
            nstars = int((avg(total_profit)/max_y) * width)
            print('{}{}{}{:>11} {}{}^'.format(colors.fg.cyan, 'Daily Avg ', colors.fg.green, '$'+str(round(avg(total_profit), 2)), colors.fg.darkgrey, ' '*(nstars-1)))
    if recent:
        if hn+10 < h:
            draw_line(3)
            print('{}{}{}'.format(colors.fg.lightgrey, 'Recently completed orders', colors.fg.blue))
        hn += 2
        #print('Recently completed orders:', colors.fg.lightblue)
        print('    {:>8} {:>11} {:>17} {:>19}{}'.format('Coin', 'Profit', 'Duration', 'Completed', colors.fg.green))
        # bubble sort, why not
        for i in range(len(recent)-1):
            for j in range(len(recent)-i-1):
                if recent[j][1]['sell_order_completed']['done_at'] < recent[j+1][1]['sell_order_completed']['done_at']:
                    tmp = recent[j+1]
                    recent[j+1] = recent[j]
                    recent[j] = tmp

        for coin, v in recent:
            if not re.search(g_filter, coin, re.IGNORECASE):
                continue
            first_status = v['first_status']
            epoch = time.mktime(time.strptime(parse_datetime(first_status['created_at']), '%Y-%m-%dT%H:%M:%S'))
            end_epoch = time.mktime(time.strptime(parse_datetime(v['sell_order_completed']['done_at']), '%Y-%m-%dT%H:%M:%S'))
            epoch_diff = end_epoch - epoch
            cur_diff = cur_time - end_epoch
            profit = round(v['profit_usd'], 2)
            if hn+10 < h:
                print('    {:>8} {:>11} {:>17} {:>19}'.format(
                    coin, '$'+str(profit), sec2time(epoch_diff), str(sec2time(cur_diff))+' ago')
                )
            hn += 1
    print(colors.reset)

def usage():
    print('usage: {} <cache-dir>'.format(sys.argv[0]))
    exit(1)

def main():
    global g_last_input
    global g_paused
    global g_filter
    global g_show_orders
    global g_print_buf
    if len(sys.argv) != 2:
        usage()
    files = glob.glob(sys.argv[1]+'/*.cache')
    if not files:
        print('ERROR: empty directory')
        exit(1)
    input_thread = threading.Thread(target=get_input)
    input_thread.start()

    sleep_time = 1.33
    running = True
    while running:
        #clear()
        while g_paused:
            time.sleep(0.1)
        with GETCH_LOCK:
            if g_last_input == 'q':
                running = False
                break
            top()
            if g_filter:
                print('{}{}filter: {}{}'.format(colors.bg.blue, colors.fg.lightgrey, g_filter, colors.reset))
            if g_show_orders:
                sleep_time = 2.11
            else:
                sleep_time = 1.33
        time.sleep(sleep_time)

if __name__ == '__main__':
    main()
