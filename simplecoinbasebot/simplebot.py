"""
NOTE: Buys are market orders since it does not matter anymore with coinbase fees.
Sells are limits.
"""
import sys
import os
import pickle
import decimal
decimal.getcontext().rounding = decimal.ROUND_DOWN
from decimal import Decimal
# truncate instead of rounding up
import time
from datetime import datetime
import configparser
import smtplib
import cbpro
from filelock import Timeout, FileLock
from random import uniform

class SimpleCoinbaseBot:
    def __init__(self, config):
        self.config = config
        self.log_file = config['general'].get('log_file')
        self.cache_file = config['general'].get('cache_file')
        if not self.cache_file.endswith('.cache'):
            raise Exception('ERROR: Cache filenames must end in .cache')
        self.lock_file = self.cache_file.replace('.cache', '.lock')
        self.lock = FileLock(self.lock_file, timeout=1)
        try:
            self.lock.acquire()
        except:
            print('ERROR: Failed to acquire lock: {}'.format(self.lock_file))
            print('Is another process already running with this config?')
            exit(1)

        self.cache = {}
        self.sleep_seconds = config['general'].getint('sleep_seconds')
        self.sell_at_percent = Decimal(config['market'].get('sell_at_percent'))
        self.buy_wallet_max = Decimal(config['market'].get('buy_wallet_max'))
        self.buy_wallet_min = Decimal(config['market'].get('buy_wallet_min'))
        self.coin = config['market'].get('coin')
        tmp = Decimal(config['market'].get('buy_wallet_percent'))
        self.buy_percent_of_wallet = round(tmp/100, 4)
        self.max_sells_outstanding = config['limits'].getint('max_sells_outstanding')
        self.max_buys_per_hour = config['limits'].getint('max_buys_per_hour')
        self.mail_to = config['notify'].get('mail_to').split(',')
        self.mail_from = config['notify'].get('mail_from')
        self.mail_host = config['notify'].get('mail_host')
        self.debug_log_response = config['debug'].getboolean('debug_log_response')
        if self.debug_log_response:
            self.debug_log_response_file = config['debug'].get('debug_log_response_file')
        self.client = self.authenticate()
        self.wallet = None
        self.current_price = None
        self.fee = None
        self.open_sells = []
        self.product_info = None
        self.min_size = None
        self.max_size = None
        self.size_decimal_places = None
        self.usd_decimal_places = None
        self.can_buy = False
        self.current_price_target = None
        self.current_price_increase = None
        self.last_buy = None
        # Run all and validate it worked on init
        self.get_all()
        self.__assert()
        self._open_cache()
        self.logit('SimpleCoinbaseBot started: {} size-precision:{} usd-precision:{} current-fee:{} min-size:{} max-size:{}'.format(
            self.coin, self.size_decimal_places, self.usd_decimal_places, self.fee, self.min_size, self.max_size
        ))
        self.logit('SimpleCoinbaseBot started: {} sleep_seconds:{} sell_at_percent:{} max_sells_outstanding:{} max_buys_per_hour:{}'.format(
            self.coin, self.sleep_seconds, self.sell_at_percent, self.max_sells_outstanding, self.max_buys_per_hour
        ))

    def _open_cache(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "rb") as f:
                self.cache = pickle.load(f)

    def _write_cache(self):
        with open(self.cache_file+'-tmp', "wb") as f:
            pickle.dump(self.cache, f)
            os.fsync(f)
        if os.path.exists(self.cache_file):
            os.rename(self.cache_file, self.cache_file+'-prev')
        os.rename(self.cache_file+'-tmp', self.cache_file)

    def _log(self, path, msg):
        now = datetime.now()
        print('{} {}'.format(now, str(msg).strip()))
        with open(path, 'a') as f:
            f.write('{} {}\n'.format(now, str(msg).strip()))

    def logdebug(self, msg):
        if self.debug_log_response:
            self._log(self.debug_log_response_file, msg)

    def logit(self, msg):
        if not self.coin in msg:
            msg = '{} {}'.format(self.coin, msg)
        self._log(self.log_file, msg)

    def authenticate(self):
        key = self.config['auth'].get('key')
        passphrase = self.config['auth'].get('passphrase')
        b64secret = self.config['auth'].get('b64secret')
        auth_client = cbpro.AuthenticatedClient(key, b64secret, passphrase)
        return auth_client

    def get_current_price(self):
        ticker = self.client.get_product_ticker(product_id=self.coin)
        self.logdebug(ticker)
        current_price = ticker['price']
        return Decimal(current_price)

    def get_product_info(self):
        self.product_info = None
        products = self.client.get_products()
        for p in products:
            if p['id'] == self.coin:
                self.product_info = p
                break
        assert(self.product_info != None)
        self.min_size = Decimal(self.product_info['base_min_size'])
        self.max_size = Decimal(self.product_info['base_max_size'])
        # counting the zeros will give the number of decimals to round to
        self.size_decimal_places = self.product_info['base_increment'].split('1')[0].count('0')
        self.usd_decimal_places = self.product_info['quote_increment'].split('1')[0].count('0')

    def get_usd_wallet(self):
        wallet = None
        accounts = self.client.get_accounts()
        for account in accounts:
            if account['currency'] == 'USD':
                wallet = account['available']
                self.logdebug(account)
                break
        return Decimal(wallet)

    def get_open_sells(self):
        orders = self.client.get_orders()
        self.logdebug(orders)
        open_sells = []
        for order in orders:
            o = order
            if order['side'] == 'sell' and order['product_id'] == self.coin:
                order['price'] = Decimal(order['price'])
                order['size'] = Decimal(order['size'])
                open_sells.append(order)
        return open_sells

    def get_fee(self):
        """ current pip cbpro version doesn't have my get_fees() patch, so manually query it """
        #{'taker_fee_rate': '0.0035', 'maker_fee_rate': '0.0035', 'usd_volume': '21953.58'}
        fees = self.client._send_message('get', '/fees')
        assert('taker_fee_rate' in fees)
        self.logdebug(fees)
        if Decimal(fees['taker_fee_rate']) > Decimal(fees['maker_fee_rate']):
            return Decimal(fees['taker_fee_rate'])
        return Decimal(fees['maker_fee_rate'])

    def _rand_msleep(self):
        time.sleep(uniform(0.1, 0.75))

    def get_all(self):
        self._rand_msleep()
        self.wallet = self.get_usd_wallet()
        self._rand_msleep()
        self.get_product_info()
        self._rand_msleep()
        self.current_price = self.get_current_price()
        #self.open_sells = self.get_open_sells()
        self.fee = self.get_fee()
        self._rand_msleep()
        self.get_current_price_target()
        self._rand_msleep()
        self.can_buy = self.check_if_can_buy()

    def sendemail(self, subject, msg=None):
        """ TODO: Add auth, currently setup to relay locally or relay-by-IP """
        for email in self.mail_to:
            if not email.strip():
                continue
            headers = "From: %s\r\nTo: %s\r\nSubject: %s %s\r\n\r\n" % (
                self.mail_from, email, self.coin, subject)
            if not msg:
                msg2 = subject
            else:
                msg2 = msg
            msg2 = headers + msg2
            server = smtplib.SMTP(self.mail_host)
            server.sendmail(self.mail_from, email, msg2)
            server.quit()
            time.sleep(0.1)

    def __assert(self):
        assert(self.wallet != None)
        assert(self.current_price != None)

    def maybe_buy_sell(self):
        self.__assert()
        if not self.can_buy:
            return

        # Check if USD wallet has enough available
        if self.wallet < Decimal(self.product_info['min_market_funds']):
            self.logit('WARNING: Wallet value too small (<${}): {}'.format(
                self.product_info['min_market_funds'], self.wallet))
            return

        # Calculate and check if size is large enough (sometimes it's not if available wallet is too small)
        buy_amount = round(Decimal(self.buy_percent_of_wallet) * Decimal(self.wallet), self.usd_decimal_places)
        buy_size = round(Decimal(buy_amount)/self.current_price, self.size_decimal_places)
        if buy_size <= self.min_size:
            self.logit('WARNING: Buy size is too small {} < {} wallet:{}.'.format(
                buy_size, self.min_size, self.wallet))
            return

        # Check if USD wallet has enough available
        if buy_amount < Decimal(self.product_info['min_market_funds']):
            self.logit('WARNING: Buy amount too small (<${}): {}'.format(
                self.product_info['min_market_funds'], buy_amount))
            return

        # Make sure buy_amount is within buy_wallet_min/max
        if buy_amount < self.buy_wallet_min:
            self.logit('WARNING: buy_wallet_min hit. Setting to min.')
            buy_amount = self.buy_wallet_min
        elif buy_amount > self.buy_wallet_max:
            self.logit('WARNING: buy_wallet_max hit. Setting to max.')
            buy_amount = self.buy_wallet_max

        # adjust size to fit with fee
        buy_size = round(Decimal(buy_size) - Decimal(buy_size)*Decimal(self.fee), self.size_decimal_places)
        self.logit('BUY: price:{} amount:{} size:{}'.format(
            self.current_price, buy_amount, buy_size))
        rc = self.client.place_market_order(
            product_id=self.coin,
            side='buy',
            funds=str(buy_amount)
        )
        self.logdebug(rc)
        self.logit('BUY-RESPONSE: {}'.format(rc))
        order_id = rc['id']
        errors = 0
        self.last_buy = None
        # Wait until order is completely filled
        if order_id in self.cache:
            self.logit('ERROR: order_id exists in cache. ????: {}'.format(order_id))
        self.cache[order_id] = {
            'first_status':rc, 'last_status':None, 'time':time.time(),
            'sell_order':None, 'sell_order_completed':None, 'completed':False, 'profit_usd':None
        }
        self._write_cache()
        done = False
        error = False
        status_errors = 0
        time.sleep(5)
        while 1:
            try:
                buy = self.client.get_order(order_id)
                self.cache[order_id]['last_status'] = buy
                self._write_cache()
                self.logdebug(buy)
                if 'settled' in buy:
                    if buy['settled']:
                        self.logit('FILLED: size:{} funds:{}'.format(buy['filled_size'], buy['funds']))
                        self.last_buy = buy
                        done = True
                        break
                else:
                    if 'message' in buy:
                        self.logit('WARNING: Failed to get order status: {}'.format(buy['message']))
                        self.logit('WARNING: Order status failure may be temporary, due to coinbase issues or exchange delays. Check: https://status.pro.coinbase.com')
                        status_errors += 1
                    else:
                        self.logit('WARNING: Failed to get order status: {}'.format(order_id))
                        status_errors += 1
                    time.sleep(10)
                if status_errors > 10:
                    errors += 1
            except Exception as err:
                self.logit('WARNING: get_order() failed:', err)
                errors += 1
                time.sleep(8)
            if errors > 5:
                self.logit('WARNING: Failed to get order. Manual intervention needed.: {}'.format(
                    order_id))
                break
            time.sleep(2)

        # Buy order done, now place sell
        if done:
            rc = self.client.place_limit_order(
                product_id=self.coin,
                side='sell',
                price=str(self.current_price_target),
                size=str(round(Decimal(self.last_buy['filled_size']), self.size_decimal_places)),
            )
            self.logdebug(rc)
            self.logit('SELL-RESPONSE: {}'.format(rc))
            msg = 'BUY-FILLED: size:{} funds:{}\n'.format(buy['filled_size'], buy['funds'])
            msg = '{} SELL-PLACED: size:{} price:{}'.format(
                msg, self.last_buy['filled_size'], self.current_price_target)
            for m in msg.split('\n'):
                self.logit(m.strip())
            self.sendemail('BUY/SELL', msg=msg)
            self.cache[order_id]['sell_order'] = rc
            self._write_cache()
            self.last_buy = None
        else:
            # buy was placed but could not get order status
            if 'message' in buy:
                msg = 'BUY-PLACED-NOSTATUS: {}\n'.format(buy['message'])
            else:
                msg = 'BUY-PLACED-NOSTATUS: size:{} funds:{}\n'.format(
                    buy['filled_size'], buy['funds'])
            self.logit(msg)
            self.sendemail('BUY-ERROR', msg=msg)
        return buy

    def check_sell_orders(self):
        """ Check if any sell orders have completed """
        for buy_order_id, v in self.cache.items():
            if self.cache[buy_order_id]['completed']:
                continue
            if not v['sell_order']:
                self.logit('WARNING: No sell_order for buy {}. This should not happen.'.format(
                    buy_order_id))
                if time.time() - v['time'] > 60*30:
                    self.logit('WARNING: Writing as done since it has no sell_order associated.')
                    self.cache[buy_order_id]['completed'] = True
                    self._write_cache()
                continue
            sell = self.client.get_order(v['sell_order']['id'])
            if 'message' in sell:
                self.logit('WARNING: Failed to get sell order status (retrying later): {}'.format(
                    sell['message']))
                continue

            if 'status' in sell and sell['status'] != 'open':
                # calculate profit from buy to sell
                # done, remove buy/sell
                self.cache[buy_order_id]['completed'] = True
                self.cache[buy_order_id]['sell_order_completed'] = sell
                if sell['status'] == 'done':
                    sell_filled_size = Decimal(sell['filled_size'])
                    sell_value = Decimal(sell['executed_value'])
                    buy_filled_size = Decimal(v['last_status']['filled_size'])
                    buy_value = Decimal(v['last_status']['executed_value'])
                    #buy_sell_diff = round((sell_price*sell_filled_size) - (buy_price*buy_filled_size), 2)
                    buy_sell_diff = round(sell_value - buy_value, 2)
                    self.cache[buy_order_id]['profit_usd'] = buy_sell_diff
                    msg = 'SELL-COMPLETED: ~duration:{:.2f} bought_val:{} sold_val:{} profit_usd:{}'.format(
                        time.time() - v['time'],
                        round(buy_value, 2),
                        round(sell_value, 2),
                        buy_sell_diff
                    )
                    self.logit(msg)
                    self.sendemail('SELL-COMPLETED', msg=msg)
                else:
                    self.logit('SELL-COMPLETED-WITH-OTHER-STATUS: {}'.format(sell['status']))
                self._write_cache()
            time.sleep(0.75)

    def get_current_price_target(self):
        current_percent_increase = (self.fee*2)+(self.sell_at_percent/100)
        self.current_price_target = round(
            self.current_price * current_percent_increase + self.current_price,
            self.usd_decimal_places
        )
        self.current_price_increase = self.current_price * current_percent_increase
        return self.current_price_target

    @property
    def total_open_orders(self):
        total = 0
        for buy_order_id, v in self.cache.items():
            if not v['completed']:
                total += 1
        return total

    @property
    def total_sells_in_past_hour(self):
        current_time = time.time()
        last_hour_time = current_time - (60*60)
        total = 0
        for buy_order_id, v in self.cache.items():
            if v['time'] >= last_hour_time:
                total += 1
        return total

    def check_if_can_buy(self):
        """ Check orders if a sell price is <= current_price_target
            If so, this means no buy is allowed until that order is filled or out of range.
            Only allow within the fee range though to keep buy/sells further apart.
        """
        self.get_current_price_target()

        # Check how many buys were placed in past hour and total open
        if self.total_sells_in_past_hour > self.max_buys_per_hour:
            self.logit('WARNING: max_buys_per_hour({}) hit'.format(self.max_buys_per_hour))
            return

        # Don't count other orders now, only ones being tracked here
        #if len(self.open_sells) >= self.max_sells_outstanding:
        if self.total_open_orders >= self.max_sells_outstanding:
            self.logit('WARNING: max_sells_outstanding hit ({} of {})'.format(
                self.total_open_orders, self.max_sells_outstanding))
            return False
        can = True
        for buy_order_id, v in self.cache.items(): #self.open_sells:
            if v['completed']:
                continue
            sell_order = v['sell_order']
            if not sell_order:
                continue
            sell_price = Decimal(sell_order['price'])
            adjusted_sell_price = round(sell_price - (self.fee*2*sell_price), self.usd_decimal_places)
            if adjusted_sell_price <= self.current_price_target:
                can = False
        return can

    def run(self):
        # Throttle startups randomly
        time.sleep(uniform(1, 5))
        while 1:
            self.get_all()
            self.logit('STATUS: price:{} fee:{} wallet:{} open-sells:{} price-target:{} can-buy:{}'.format(
                self.current_price, self.fee, self.wallet, self.total_open_orders, self.current_price_target,
                self.can_buy,
            ))
            self.maybe_buy_sell()
            self.check_sell_orders()
            time.sleep(self.sleep_seconds)

def usage():
    print('{} <config-path>'.format(sys.argv[0]))
    exit(1)

def main():
    if len(sys.argv) != 2:
        usage()
    config_path = sys.argv[1]
    config = configparser.ConfigParser()
    config.read(config_path)
    bot = SimpleCoinbaseBot(config)
    bot.run()


if __name__ == '__main__':
    main()

