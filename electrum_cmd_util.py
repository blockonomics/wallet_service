import os
import configparser
import electrum
import time
import asyncio
import logging
import logging.config
from threading import Thread
from hashlib import sha256

CONFIG_FILE = 'config.ini'

class ElectrumCmdUtil():
  '''Utility class for Electrum commands and helper methods'''

  def __init__(self):
    self.set_logging()
    self.config = configparser.ConfigParser()
    self.config.read(CONFIG_FILE)
    self.network = None
    if self.config['SYSTEM']['use_testnet'] == 'True':
      electrum.constants.set_testnet()
    conf = {'fee_level': self.config['SYSTEM']['fee_level'], 'auto_connect': True}
    self.conf = electrum.SimpleConfig(conf)
    self.cmd = electrum.Commands(config = self.conf)

  def start_event_loop(self):
    self.loop, self.stopping_fut, self.loop_thread = electrum.util.create_and_start_event_loop()

  def connect_to_network(self):
    logging.info("Connecting to network...")
    self.network = electrum.Network(self.conf)
    self.network._loop_thread = self.loop_thread
    self.network.start()
    self.cmd.network = self.network

  def set_logging(self):
    level = logging.INFO
    logging.config.dictConfig({
      'version': 1,
      'disable_existing_loggers': False,
      'formatters': {
          'standard': {
              'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
          },
      },
      'handlers': { 
          'default': {
              'level': level,
              'class': 'logging.handlers.RotatingFileHandler',
              'formatter': 'standard',
              'filename': 'debug.log',
              'maxBytes': 4194304,
              'backupCount': 10, 
           },
      },
      'loggers': {
              '': {
                  'handlers': ['default'],        
                  'level': level,
                  'propagate': True  
              }
          }
      })

  def get_balance(self, wallet):
    try:
      balances = wallet.get_balance()
      return balances
    except Exception as e:
      raise Exception('Error while loading balance from {}: {}'.format(wallet, e))

  def get_history(self, wallet):
    try:
      history = wallet.get_full_history()
      return history
    except Exception as e:
      raise Exception('Error while loading balance from {}: {}'.format(wallet, e))

  def get_xpub(self, wallet):
    return wallet.get_master_public_key()

  def get_unused(self, wallet):
    self.cmd.wallet = wallet
    try:
      address = self.cmd.getunusedaddress()
      return address
    except Exception as e:
      print(e)

  def get_seed(self, wallet, wallet_password):
    self.cmd.wallet = wallet
    seed = self.cmd.getseed(password = wallet_password)
    return seed

  def create_wallet(self, wallet_id, wallet_password):
    wallet_path = self.config['SYSTEM']['wallet_dir'] + '/wallet_' + str(wallet_id)
    conf = electrum.SimpleConfig({'wallet_path':wallet_path})
    wallet = electrum.wallet.create_new_wallet(path=wallet_path, config=conf, password=wallet_password)['wallet']
    wallet.synchronize()
    wallet.change_gap_limit(200)
    logging.info("%s created", wallet)
    xpub = wallet.get_master_public_key()
    seed = wallet.get_seed(wallet_password)
    return [xpub, seed]

  def stop_network(self):
    asyncio.ensure_future(self.network.stop())
    self.stopping_fut.set_result('done')
    self.stopping_fut.cancel()

  def wait_for_wallet_sync(self, wallet, stop_on_complete = False):
    self.start_event_loop()
    self.connect_to_network()
    wallet.start_network(self.network)
    while not wallet.is_up_to_date():
      time.sleep(1)
    if stop_on_complete:
      self.stop_network()

  def load_wallet(self, wallet_path, wallet_password):
    storage = electrum.WalletStorage(wallet_path)
    if not storage.file_exists():
      raise Exception('{} does not exist'.format(wallet_path))
    storage.decrypt(wallet_password)
    db = electrum.wallet_db.WalletDB(storage.read(), manual_upgrades=True)
    wallet = electrum.Wallet(db, storage, config=self.conf)
    return wallet

  def estimate_tx_size(self, wallet, wallet_password, destination, amount):
    self.cmd.wallet = wallet
    try:
      # The fee here can be anything, this tx wont be broadcast anywhere
      # This is only used to fetch the estimated size of the tx
      tx = self.cmd.payto(destination, amount, password=wallet_password, fee=0.00000002)
      tx = electrum.Transaction(tx)
      tx_size = tx.estimated_size()
      return tx_size
    except Exception as e:
      raise Exception("Failed to estimate tx size for wallet: {} {}".format(wallet, e))    

  def create_tx(self, wallet, wallet_password, destination, amount):
    logging.info("Creating tx, wallet: %s, destination: %s, amount: %s", wallet, destination, amount)
    try:
      amount_sat = electrum.commands.satoshis_or_max(amount)
      outputs = [electrum.transaction.PartialTxOutput.from_address_and_value(destination, amount_sat)]
      tx = wallet.create_transaction(
          outputs,
          fee=None,
          feerate=None,
          change_addr=None,
          domain_addr=None,
          domain_coins=None,
          unsigned=False,
          rbf=True,
          password=wallet_password,
          locktime=None)
      result = tx.serialize()
      return result
    except Exception as e:
      raise Exception("Failed to create tx for wallet: {} {}".format(wallet, e))

  def send_to(self, wallet, wallet_password, destination, amount):
    logging.info("Trying to send full balance of %s", wallet)
    tx = self.create_tx(wallet, wallet_password, destination, amount)
    self.start_event_loop()
    self.connect_to_network()
    while not self.network.is_connected():
      print('Connecting...')
      time.sleep(1)      
    self.__broadcast(wallet, tx, amount, self.network)
    self.stop_network()

  def __broadcast(self, wallet, tx, amount, network):
    try:
      tx = electrum.Transaction(tx)
      task = asyncio.ensure_future(network.broadcast_transaction(tx))
      while not task.done():
        print('Broadcasting...')
        time.sleep(1)
      task.result()
      logging.info("Sent {} BTC from {}, txid: {}".format(amount, wallet, tx.txid()))
      print("Sent {} BTC from {}, txid: {}".format(amount, wallet, tx.txid()))
    except Exception as e:
      self.stop_network()
      wallet.remove_transaction(tx.txid())
      raise Exception("Failed to broadcast wallet: {} tx: {} {}".format(wallet, tx.txid(), e))