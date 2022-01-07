import os
import configparser
import electrum
import time
import asyncio
import logging
import logging.config
from threading import Thread
from hashlib import sha256
from db_manager import DbManager

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

  def get_event_loop(self):
    try:
      self.loop = asyncio.get_running_loop()
    except RuntimeError:
      # No loop running
      self.loop, self.stopping_fut, self.loop_thread = electrum.util.create_and_start_event_loop()

  def connect_to_network(self):
    logging.info("Connecting to network...")
    self.network = electrum.Network.get_instance()
    if not self.network:
      self.network = electrum.Network(self.conf)
    self.network.start()
    self.cmd.network = self.network

  async def wait_for_connection(self):
    while not self.network.is_connected():
      await asyncio.sleep(1)

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
    self.get_event_loop()
    self.connect_to_network()
    wallet.start_network(self.network)
    while not wallet.is_up_to_date():
      time.sleep(1)
    if stop_on_complete:
      self.stop_network()

  def load_wallet(self, wallet_id, wallet_password):
    wallet_path = self.config['SYSTEM']['wallet_dir'] + '/wallet_' + str(wallet_id)
    storage = electrum.WalletStorage(wallet_path)
    if not storage.file_exists():
      raise Exception('{} does not exist'.format(wallet_path))
    storage.decrypt(wallet_password)
    db = electrum.wallet_db.WalletDB(storage.read(), manual_upgrades=True)
    wallet = electrum.Wallet(db, storage, config=self.conf)
    return wallet

  def estimate_tx_size(self, wallet, wallet_password, destination, amount):
    try:
      # This is only used to fetch the estimated size of the tx
      tx = self.create_tx(wallet, wallet_password, destination, amount)
      tx = electrum.Transaction(tx)
      tx_size = tx.estimated_size()
      wallet.remove_transaction(tx.txid())
      return tx_size
    except Exception as e:
      raise Exception("Failed to estimate tx size for wallet: {} {}".format(wallet, e))

  def estimate_pay_to_many_size(self, wallet, wallet_password, outputs):
    try:
      # This is only used to fetch the estimated size of the tx
      tx = self.create_pay_to_many(wallet, wallet_password, outputs)
      tx = electrum.Transaction(tx)
      tx_size = tx.estimated_size()
      wallet.remove_transaction(tx.txid())
      return tx_size
    except Exception as e:
      raise Exception("Failed to estimate tx size for wallet: {} {}".format(wallet, e))

  def create_tx(self, wallet, wallet_password, destination, amount):
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

  def create_pay_to_many(self, wallet, wallet_password, outputs):
    try:
      final_outputs = []
      for address, amount in outputs:
          amount_sat = electrum.commands.satoshis_or_max(amount)
          final_outputs.append(electrum.transaction.PartialTxOutput.from_address_and_value(address, amount_sat))
      tx = wallet.create_transaction(
          final_outputs,
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
    self.get_event_loop()
    self.connect_to_network()
    while not self.network.is_connected():
      print('Connecting...')
      time.sleep(1)      
    self.broadcast(wallet, tx, amount)
    self.stop_network()

  def broadcast(self, wallet, tx, amount):
    try:
      tx = electrum.Transaction(tx)
      task = asyncio.ensure_future(self.network.broadcast_transaction(tx))
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

  async def async_broadcast(self, wallet, tx, amount):
    try:
      tx = electrum.Transaction(tx)
      task = asyncio.ensure_future(self.network.broadcast_transaction(tx))
      while not task.done():
        print('Broadcasting...')
        await asyncio.sleep(1)
      task.result()
      logging.info("Sent {} BTC from {}, txid: {}".format(amount, wallet, tx.txid()))
      print("Sent {} BTC from {}, txid: {}".format(amount, wallet, tx.txid()))
    except Exception as e:
      wallet.remove_transaction(tx.txid())
      raise Exception("Failed to broadcast wallet: {} tx: {} {}".format(wallet, tx.txid(), e))

class APICmdUtil:
  ''' Handles functions needed for API so that the API framework can be anything
  '''

  @classmethod
  async def _init_cmd_manager(cls):
    cmd_manager = ElectrumCmdUtil()
    cmd_manager.get_event_loop()
    cmd_manager.connect_to_network()
    await cmd_manager.wait_for_connection()
    return cmd_manager

  @classmethod
  async def _estimate_single_tx_fee(cls, cmd_manager, addr, btc_amount, wallet_id, wallet_password):
    wallet = cmd_manager.load_wallet(wallet_id, wallet_password)
    tx_size = cmd_manager.estimate_tx_size(wallet, wallet_password, addr, btc_amount)
    cmd_manager.network.update_fee_estimates()
    fee_estimates = cmd_manager.network.get_fee_estimates()
    sat_per_b = (fee_estimates.get(2) / 1000) / 1.0e8
    return tx_size * sat_per_b

  @classmethod
  async def presend(cls, addr, btc_amount, wallet_id, wallet_password, api_password):
    cmd_manager = await cls._init_cmd_manager()
    wallet = cmd_manager.load_wallet(wallet_id, wallet_password)
    this_tx_size = cmd_manager.estimate_tx_size(wallet, wallet_password, addr, btc_amount)
    with DbManager() as db_manager:
      unsent = db_manager.get_unsent()
    
    outputs = []
    outputs.append([addr, btc_amount])
    tx_total_size = this_tx_size
    total_amount = btc_amount

    if unsent:
      for tx in unsent:
        tx_total_size += tx.tx_size
        total_amount += tx.amount
        outputs.append([tx.address, tx.amount])

    cmd_manager.network.update_fee_estimates()
    fee_estimates = cmd_manager.network.get_fee_estimates()
    sat_per_b = (fee_estimates.get(2) / 1000) / 1.0e8

    total_size = cmd_manager.estimate_pay_to_many_size(wallet, wallet_password, outputs)
    total_fee = total_size * sat_per_b

    tx_proportion = this_tx_size / tx_total_size
    this_tx_fee = tx_proportion * total_fee

    return this_tx_fee

  @classmethod
  async def send(cls, addr, btc_amount, wallet_id, wallet_password, api_password):
    cmd_manager = await cls._init_cmd_manager()
    wallet = cmd_manager.load_wallet(wallet_id, wallet_password)
    this_tx_size = cmd_manager.estimate_tx_size(wallet, wallet_password, addr, btc_amount)
    with DbManager() as db_manager:
      obj, unsent = db_manager.insert_transaction(addr, btc_amount, wallet_id, this_tx_size)
    
    outputs = []
    outputs.append([obj.address, obj.amount])
    tx_total_size = this_tx_size
    total_amount = btc_amount

    if unsent:
      for tx in unsent:
        tx_total_size += tx.tx_size
        total_amount += tx.amount
        outputs.append([tx.address, tx.amount])

    cmd_manager.network.update_fee_estimates()
    fee_estimates = cmd_manager.network.get_fee_estimates()
    sat_per_b = (fee_estimates.get(2) / 1000) / 1.0e8

    total_size = cmd_manager.estimate_pay_to_many_size(wallet, wallet_password, outputs)
    total_fee = total_size * sat_per_b

    fee_to_amount_proportion = total_fee / total_amount

    tx_proportion = this_tx_size / tx_total_size
    this_tx_fee = tx_proportion * total_fee

    print('tx_proportion: {}, total_size: {}, total_amount: {}, total_fee: {}, fee_to_amount_proportion: {}'\
      .format(tx_proportion, total_size, total_amount, total_fee, fee_to_amount_proportion))

    batching_threshold = int(cmd_manager.config['USER']['batching_threshold']) / 100

    if batching_threshold >= fee_to_amount_proportion:
      tx = cmd_manager.create_pay_to_many(wallet, wallet_password, outputs)
      await cmd_manager.async_broadcast(wallet, tx, total_amount)
      with DbManager() as db_manager:
        db_manager.update_transaction(obj.internal_txid, electrum.Transaction(tx).txid())

    return this_tx_fee, obj.internal_txid
