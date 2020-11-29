"""
NOTE: Buys are market orders since it does not matter anymore with coinbase fees.
Sells are limits.
"""
import sys
import decimal
decimal.getcontext().rounding = decimal.ROUND_DOWN
from decimal import Decimal
# truncate instead of rounding up
import time
from datetime import datetime
import configparser
import smtplib
import cbpro

class Bot1:
    """ A simple bot that buys whenever it can. It can only not buy if there is currently
    an open sell order <= to the current target price
    """
    def __init__(self, config):
        self.config = config
        self.mailto = config['general'].get('mail_to').split(',')
        self.mail_from = config['general'].get('mail_from')
        self.mail_host = config['general'].get('mail_host')
        self.logfile = config['general'].get('logfile')
        self.coin = config['general'].get('coin')
        self.max_sells = config['general'].getint('max_sells')
        self.sell_at_percent = config['general'].getfloat('sell_at_percent')
        self.sleepsecs = config['general'].getint('sleepsecs')
        self.debug_log_response = config['general'].getboolean('debug_log_response')
        if self.debug_log_response:
            self.debug_log_response_file = config['general'].get('debug_log_response_file')
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
        tmp = float(config['general'].get('buy_wallet_percent'))
        self.buy_percent_of_wallet = round(Decimal(tmp/100.0), 4)
        self.last_buy = None
        # Run all and validate it worked on init
        self.get_all()
        self.__assert()
        self.logit('Bot1 started: {} size-precision:{} usd-precision:{} current-fee:{} min-size:{} max-size:{}'.format(
            self.coin, self.size_decimal_places, self.usd_decimal_places, self.fee, self.min_size, self.max_size
        ))

    def _log(self, path, msg):
        now = datetime.now()
        print('{} {}'.format(now, str(msg).strip()))
        with open(path, 'a') as f:
            f.write('{} {}\n'.format(now, str(msg).strip()))

    def logdebug(self, msg):
        if self.debug_log_response:
            self._log(self.debug_log_response_file, msg)

    def logit(self, msg):
        self._log(self.logfile, msg)

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
        # counting the zeros will give use the number of decimals to round to
        self.size_decimal_places = self.product_info['base_increment'].split('1')[0].count('0')
        #print("self.product_info['quote_increment']", self.product_info['quote_increment'])
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
                #print('{} {} {} {} {} {}'.format(o['side'], o['size'], o['price'], o['status'], o['settled'], o['filled_size']))
                order['price'] = Decimal(order['price'])
                order['size'] = Decimal(order['size'])
                open_sells.append(order)
        return open_sells

    def get_fee(self):
        """ current pip doesn't have get_fees() so manually construct it """
        #{'taker_fee_rate': '0.0035', 'maker_fee_rate': '0.0035', 'usd_volume': '21953.58'}
        fees = self.client._send_message('get', '/fees')
        self.logdebug(fees)
        if Decimal(fees['taker_fee_rate']) > Decimal(fees['maker_fee_rate']):
            return Decimal(fees['taker_fee_rate'])
        return Decimal(fees['maker_fee_rate'])

    def get_all(self):
        self.wallet = self.get_usd_wallet()
        self.get_product_info()
        self.current_price = self.get_current_price()
        self.open_sells = self.get_open_sells()
        self.fee = self.get_fee()
        self.get_current_price_target()
        self.can_buy = self.check_if_can_buy()

    def sendemail(self, subject, msg=None):
        """ TODO: Add auth, currently setup to relay locally or relay-by-IP """
        for email in self.mailto:
            if not email.strip():
                continue
            headers = "From: %s\r\nTo: %s\r\nSubject: %s %s\r\n\r\n" % (self.mail_from, email, self.coin, subject)
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

    def maybe_buy(self):
        self.__assert()
        if not self.can_buy:
            return
        if self.wallet < Decimal(self.product_info['min_market_funds']):
            self.logit('WARNING: Wallet value too small (<${}): {}'.format(self.product_info['min_market_funds'], self.wallet))
        buy_amount = round(Decimal(self.buy_percent_of_wallet) * Decimal(self.wallet), self.usd_decimal_places)
        buy_size = round(Decimal(buy_amount)/self.current_price, self.size_decimal_places)
        if buy_size <= self.min_size:
            self.logit('WARNING: Buy size is too small {} < {} wallet:{}.'.format(buy_size, self.min_size, self.wallet))
            buy_amount = round(self.wallet, self.usd_decimal_places)
        # adjust to fee
        buy_size = round(Decimal(buy_size) - Decimal(buy_size)*Decimal(self.fee), self.size_decimal_places)
        msg = 'BUY: price:{} amount:{} size:{}'.format(self.current_price, buy_amount, buy_size)
        self.logit(msg)
        self.sendemail('BOUGHT', msg=msg)
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
        time.sleep(1.5)
        while 1:
            try:
                buy = self.client.get_order(order_id)
                self.logdebug(buy)
                if buy['settled']:
                    self.logit('FILLED: size:{} funds:{}'.format(buy['filled_size'], buy['funds']))
                    self.last_buy = buy
                    break
            except Exception as err:
                self.logit('get_order() failed:', err)
                errors += 1
                time.sleep(10)
            if errors > 2:
                self.logit('WARNING: Failed to get order id. You will manually need to fix this buy/sell.: {}'.format(order_id))
                break
            time.sleep(1)
        return buy

    def maybe_sell(self):
        self.__assert()
        if not self.last_buy:
            return
        msg = 'SELL: size:{} price:{}'.format(self.last_buy['filled_size'], self.current_price_target)
        self.logit(msg)
        self.sendemail('SELL', msg=msg)
        rc = self.client.place_limit_order(
            product_id=self.coin,
            side='sell',
            price=str(self.current_price_target),
            size=self.last_buy['filled_size'],
        )
        self.logdebug(rc)
        self.last_buy = None
        self.logit('SELL-RESPONSE: {}'.format(rc))
        time.sleep(1)

    def get_current_price_target(self):
        current_percent_increase = (self.fee*2)+Decimal(self.sell_at_percent/100.0)
        self.current_price_target = round(self.current_price * current_percent_increase + self.current_price, self.usd_decimal_places)
        self.current_price_increase = self.current_price * current_percent_increase
        return self.current_price_target

    def check_if_can_buy(self):
        """ Check orders if a sell price is <= current_price_target
            If so, this means no buy is allowed until that order is filled or out of range.
            Only allow within the fee range though to keep buy/sells further apart.
        """
        self.get_current_price_target()
        if len(self.open_sells) >= self.max_sells:
            self.logit('WARNING: max_sells hit ({} of {})'.format(len(self.open_sells), self.max_sells))
            return False
        can = True
        for sell in self.open_sells:
            adjusted_sell_price = round(sell['price'] - (self.fee*2*sell['price']), self.usd_decimal_places)
            #print('check_if_can_buy: {}:{} <= {}'.format(sell['price'], adjusted_sell_price, self.current_price_target))
            if adjusted_sell_price <= self.current_price_target:
                can = False
        return can

    def run(self):
        while 1:
            self.get_all()
            self.logit('STATUS: price:{} fee:{} wallet:{} open-sells:{} price-target:{} can-buy:{}'.format(
                self.current_price, self.fee, self.wallet, len(self.open_sells), self.current_price_target,
                self.can_buy,
            ))
            self.maybe_buy()
            self.maybe_sell()
            time.sleep(self.sleepsecs)

def main(config_path):
    config = configparser.ConfigParser()
    config.read(config_path)
    bot = Bot1(config)
    bot.run()

def usage():
    print('{} <config-path>'.format(sys.argv[0]))
    exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        usage()
    main(sys.argv[1])

