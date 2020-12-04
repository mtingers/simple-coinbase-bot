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
from .color import colors
from .getch import getch, getchb

os.environ['TZ'] = 'UTC'
time.tzset()

GETCH_LOCK = threading.Lock()
g_last_input = None
g_filter = ''
g_paused = False

def clear():
    if name == 'nt':
        system('cls')
    else:
        system('clear')

def get_input():
    global g_last_input
    global g_paused
    global g_filter
    while 1:
        with GETCH_LOCK:
            g_last_input = getch()
        if g_last_input == 'q':
            print('exiting...')
            break
        if g_last_input == 'f':
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
        """
        data = input()
        print(data)
        g_last_input = data.strip()
        if g_last_input == 'q':
            return
        time.sleep(.25)
        """
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
    if d == 0:
        return pattern % (h, m, s)
    return ('%dd' + pattern) % (d, h, m, s)

def avg(l):
    if len(l) < 1:
        return Decimal(0.0)
    return Decimal(sum(l))/len(l)

def top():
    clear()
    print('')
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
                stats[coin] = {'epoch_diffs':[], 'profits':[], 'open_orders':0, 'done_orders':0, 'avg_close_time':0.0, 'error_orders':0, }
            first_status = v['first_status']
            epoch = time.mktime(time.strptime(first_status['created_at'].split('.')[0], '%Y-%m-%dT%H:%M:%S'))
            if v['completed'] and 'sell_order_completed' in v and v['sell_order_completed']:
                date_only = v['sell_order_completed']['done_at'].split('T')[0]
                if not date_only in profit_dates:
                    profit_dates[date_only] = []
                profit_dates[date_only].append(v['profit_usd'])
                end_epoch = time.mktime(time.strptime(v['sell_order_completed']['done_at'].split('.')[0], '%Y-%m-%dT%H:%M:%S'))
                epoch_diff = end_epoch - epoch
                cur_diff = cur_time - end_epoch
                if cur_diff < (86400/12):
                    recent.append((coin, v))
                profit = v['profit_usd']
                stats[coin]['epoch_diffs'].append(epoch_diff)
                stats[coin]['profits'].append(profit)
                stats[coin]['done_orders'] += 1
            elif v['completed']:
                stats[coin]['error_orders'] += 1
            else:
                start_epoch = time.mktime(time.strptime(v['first_status']['created_at'].split('.')[0], '%Y-%m-%dT%H:%M:%S'))
                open_times.append(cur_time - start_epoch)
                stats[coin]['open_orders'] += 1

    sorted_keys = sorted(stats.keys())
    print('[{}q{}]{}uit {}[{}f{}]{}ilter {:>59} UTC'.format(
        colors.fg.red, colors.reset, colors.fg.lightgrey,
        colors.reset, colors.fg.pink, colors.reset, colors.fg.lightgrey,
        str(datetime.now()).split('.')[0])
    )
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
    for key in sorted_keys:
        coin = key
        if not re.search(g_filter, coin, re.IGNORECASE):
            continue
        v = stats[key]
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
        #if v['epoch_diffs']:
        agg_epoch.append(round(avg(v['epoch_diffs']), 2) if v['epoch_diffs'] else Decimal('0.0'))
        agg_profits.append(round(avg(stats[coin]['profits']), 2))
        total_open_orders += v['open_orders']
        total_done_orders += v['done_orders']
        total_error_orders += v['error_orders']
        total_profits += round(sum(v['profits']), 2)
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
    draw_line(3)
    if open_times:
        min_open_time = sec2time(round(min(open_times), 2))
        max_open_time = sec2time(round(max(open_times), 2))
        avg_open_time = sec2time(round(avg(open_times), 2))
    else:
        min_open_time = Decimal('0.0')
        max_open_time = Decimal('0.0')
        avg_open_time = Decimal('0.0')
    print('{}{:>16} {:>16} {:>16} {:>16}'.format(colors.fg.lightgrey, 'Open order times', 'Min', 'Max', 'Avg'))
    print('{}{:>16} {:>16} {:>16} {:>16}'.format(colors.fg.lightred, ' ', min_open_time, max_open_time, avg_open_time))

    # Last 7 days with profits
    #print('{}{:>26}'.format(colors.fg.lightgrey, 'Last 7 days profits'))
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

    draw_line(3)
    if y:
        max_y = max(y)
        width = 50
        for i in range(len(y)):
            key = x[i]
            yy = y[i]
            nstars = int((yy/max_y) * width)
            print('{}{}{}{:>11} {}{}'.format(colors.fg.cyan, key, colors.fg.green, '$'+str(yy), colors.fg.darkgrey, '*'*nstars))
    if recent:
        draw_line(3)
        print('{}{}'.format(colors.fg.lightgrey, 'Recently completed orders'), colors.fg.blue)
        #print('Recently completed orders:', colors.fg.lightblue)

    print('    {:>8} {:>11} {:>17} {:>19}'.format('Coin', 'Profit', 'Duration', 'Completed'), colors.fg.green)
    for coin, v in recent:
        if not re.search(g_filter, coin, re.IGNORECASE):
            continue
        first_status = v['first_status']
        epoch = time.mktime(time.strptime(first_status['created_at'].split('.')[0], '%Y-%m-%dT%H:%M:%S'))
        end_epoch = time.mktime(time.strptime(v['sell_order_completed']['done_at'].split('.')[0], '%Y-%m-%dT%H:%M:%S'))
        epoch_diff = end_epoch - epoch
        cur_diff = cur_time - end_epoch
        profit = round(v['profit_usd'], 2)
        print('    {:>8} {:>11} {:>17} {:>19}'.format(
            coin, '$'+str(profit), sec2time(epoch_diff), str(sec2time(cur_diff))+' ago')
        )
    print(colors.reset)

def usage():
    print('usage: {} <cache-dir>'.format(sys.argv[0]))
    exit(1)

def main():
    global g_last_input
    global g_paused
    global g_filter
    if len(sys.argv) != 2:
        usage()
    files = glob.glob(sys.argv[1]+'/*.cache')
    if not files:
        print('ERROR: empty directory')
        exit(1)
    input_thread = threading.Thread(target=get_input)
    input_thread.start()

    running = True
    while running:
        while g_paused:
            time.sleep(0.1)
        with GETCH_LOCK:
            if g_last_input == 'q':
                running = False
                break
            top()
        time.sleep(1.25)

if __name__ == '__main__':
    main()
