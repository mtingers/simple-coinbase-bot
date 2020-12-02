import os
import sys
import glob
import pickle
from decimal import Decimal
import time
from pprint import pprint
from os import system, name
from datetime import timedelta, datetime
from color import colors

os.environ['TZ'] = 'UTC'
time.tzset()

def clear():
    if name == 'nt':
        system('cls')
    else:
        system('clear')

def sec2time(sec, n_msec=3):
    ''' Convert seconds to 'D days, HH:MM:SS.FFF' '''
    if hasattr(sec,'__len__'):
        return [sec2time(s) for s in sec]
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if n_msec > 0:
        pattern = '%%02d:%%02d:%%0%d.%df' % (n_msec+3, n_msec)
    else:
        pattern = r'%02d:%02d:%02d'
    if d == 0:
        return pattern % (h, m, s)
    return ('%d days, ' + pattern) % (d, h, m, s)


def top():
    clear()
    print('')
    files = glob.glob(sys.argv[1]+'/*.cache')
    stats = {}
    stats_incomplete = {}
    recent = []
    cur_time = time.time()
    open_times = []
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
            if not coin in stats:
                stats[coin] = {'epoch_diffs':[], 'profits':[], 'open_orders':0, 'done_orders':0, 'avg_close_time':0.0, 'error_orders':0, }
            first_status = v['first_status']
            epoch = time.mktime(time.strptime(first_status['created_at'].split('.')[0], '%Y-%m-%dT%H:%M:%S'))
            if v['completed'] and 'sell_order_completed' in v and v['sell_order_completed']:
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
    print('{:>100}-UTC'.format(str(datetime.now()).split('.')[0]))
    print('{}{}{}'.format(colors.fg.darkgrey, '-'*105, colors.reset))
    print('{}{:>7} {}{:>15} {}{:>15} {}{:>15} {}{:>15} {}{:>15} {}{:>15}{}'.format(
        colors.fg.lightcyan, 'Coin',
        colors.fg.green, 'Profits',
        colors.fg.yellow, 'Open',
        colors.fg.blue, 'Done',
        colors.fg.red, 'Error',
        colors.fg.orange, 'Avg-Time',
        colors.fg.pink, 'Avg-Profit',
        colors.reset,
    ))
    print('{}{}{}'.format(colors.fg.darkgrey, '-'*105, colors.reset))
    total_profits = Decimal('0.0')
    total_open_orders = 0
    total_done_orders = 0
    total_error_orders = 0
    agg_epoch = []
    agg_profits = []
    for key in sorted_keys:
        coin = key
        v = stats[key]
        print('{}{:>7} {}{:>15} {}{:>15} {}{:>15} {}{:>15} {}{:>15} {}{:>15}{}'.format(
            colors.fg.lightcyan, coin,
            colors.fg.green, '$'+str(round(sum(v['profits']), 2)),
            colors.fg.yellow, v['open_orders'],
            colors.fg.blue, v['done_orders'],
            colors.fg.red, v['error_orders'],
            colors.fg.orange, sec2time(round(sum(v['epoch_diffs'])/len(v['epoch_diffs']), 2), 0) if v['epoch_diffs'] else 'None',
            colors.fg.pink, '$'+str(round(sum(stats[coin]['profits'])/len(stats[coin]['profits']), 2)),
            colors.reset,
        ))
        #if v['epoch_diffs']:
        agg_epoch.append(round(sum(v['epoch_diffs'])/len(v['epoch_diffs']), 2) if v['epoch_diffs'] else Decimal('0.0'))
        agg_profits.append(round(sum(stats[coin]['profits'])/len(stats[coin]['profits']), 2))
        total_open_orders += v['open_orders']
        total_done_orders += v['done_orders']
        total_error_orders += v['error_orders']
        total_profits += round(sum(v['profits']), 2)
    print('{}{}{}'.format(colors.fg.darkgrey, '-'*105, colors.reset))
    print('{}{:>7} {}{:>15} {}{:>15} {}{:>15} {}{:>15} {}{:>15} {}{:>15}{}'.format(
            colors.fg.darkgrey, 'all',
            colors.fg.green, '$'+str(total_profits),
            colors.fg.yellow, total_open_orders,
            colors.fg.blue, total_done_orders,
            colors.fg.red, total_error_orders,
            colors.fg.orange, sec2time(round(sum(agg_epoch)/len(agg_epoch), 2), 0),
            colors.fg.pink, '$'+str(round(sum(agg_profits)/len(agg_profits), 2)),
            colors.reset,
    ))

    print('{}{}{}'.format(colors.fg.darkgrey, '-'*105, colors.reset))
    min_open_time = sec2time(round(min(open_times), 2), 0)
    max_open_time = sec2time(round(max(open_times), 2), 0)
    avg_open_time = sec2time(round(sum(open_times)/len(open_times), 2), 0)
    print(colors.fg.lightgrey)
    print('{:>24} {:>15} {:>15} {:>15}'.format('Open order durations', 'Min', 'Max', 'Avg'))
    print('{:>24} {:>15} {:>15} {:>15}'.format('', min_open_time, max_open_time, avg_open_time))

    if recent:
        print('{}{}{}'.format(colors.fg.darkgrey, '-'*105, colors.reset))
        print(colors.fg.lightgrey)
        print('Recently completed:', colors.fg.lightblue)
    for coin, v in recent:
        first_status = v['first_status']
        epoch = time.mktime(time.strptime(first_status['created_at'].split('.')[0], '%Y-%m-%dT%H:%M:%S'))
        end_epoch = time.mktime(time.strptime(v['sell_order_completed']['done_at'].split('.')[0], '%Y-%m-%dT%H:%M:%S'))
        epoch_diff = end_epoch - epoch
        cur_diff = cur_time - end_epoch
        profit = round(v['profit_usd'], 2)
        print('    {} ${} duration:{} ago:{}'.format(coin, profit, sec2time(epoch_diff, 0), sec2time(cur_diff, 0)))
    print(colors.reset)

def main():
    while 1:
        top()
        time.sleep(10)

if __name__ == '__main__':
    main()
