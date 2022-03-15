import os
import configparser
import electrum
import time
import asyncio
import logging
import logging.config
import cryptocode
from threading import Thread
from hashlib import sha256
from db_manager import DbManager

CONFIG_FILE = 'config.ini'

class ElectrumCmdUtil():
  '''Utility class for Electrum commands and helper methods'''

  def __init__(self):
    self.set_logging()
    self.config_file = CONFIG_FILE
    self.config = configparser.ConfigParser()
    self.config.read(CONFIG_FILE)
    self.network = None
    if self.config['SYSTEM']['use_testnet'] == 'True':
      electrum.constants.set_testnet()
    conf = {'fee_level': int(self.config['SYSTEM']['fee_level']), 'auto_connect': True}
    self.conf = electrum.SimpleConfig(conf)
    self.cmd = electrum.Commands(config = self.conf)
    self.wallet = None
    self.wallet_password = None

  def get_event_loop(self):
    try:
      self.loop = asyncio.get_running_loop()
    except RuntimeError:
      # No loop running
      logging.info('No event loop, creating')
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
      logging.info(self.network.get_status_value('status'))
      await asyncio.sleep(1)

  async def wait_for_fee_estimates(self):
    while not self.network.get_fee_estimates():
      await asyncio.sleep(1)

  async def log_network_status(self):
    if self.network != None:
      logging.info("Network: %s", self.network.get_status_value('status'))
      while self.network.get_status_value('status') == 'disconnected':
        logging.info("Network disconnected, trying to restart...")
        await asyncio.sleep(5)
    else:
      logging.info("Network: no network")
    # Only log fee if we have received it at least once
    if self.conf.fee_per_kb():
      logging.info("Currently used fee %i sat/kb", self.conf.fee_per_kb())


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

  def _get_wallet_path(self, wallet_id):
    wallet_dir = self.config['SYSTEM']['wallet_dir']
    if not os.path.isdir(wallet_dir):
      os.mkdir(wallet_dir)
    return self.config['SYSTEM']['wallet_dir'] + '/wallet_' + str(wallet_id)

  def create_wallet(self, wallet_id, wallet_password):
    wallet_path = self._get_wallet_path(wallet_id)
    conf = electrum.SimpleConfig({'wallet_path':wallet_path})
    wallet = electrum.wallet.create_new_wallet(path=wallet_path, config=conf, password=wallet_password)['wallet']
    wallet.synchronize()
    wallet.change_gap_limit(200)
    logging.info("%s created", wallet)
    xpub = wallet.get_master_public_key()
    seed = wallet.get_seed(wallet_password)
    return [xpub, seed]

  def load_wallet(self, wallet_id, wallet_password):
    wallet_path = self._get_wallet_path(wallet_id)
    storage = electrum.WalletStorage(wallet_path)
    if not storage.file_exists():
      raise Exception('{} does not exist'.format(wallet_path))
    storage.decrypt(wallet_password)
    db = electrum.wallet_db.WalletDB(storage.read(), manual_upgrades=True)
    wallet = electrum.Wallet(db, storage, config=self.conf)
    return wallet

  def set_wallet(self, wallet_id, wallet_password):
    self.wallet_password = wallet_password
    self.wallet = self.load_wallet(wallet_id, wallet_password)

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

  def get_tx_size(self, destination = None, amount = None, outputs = None):
    try:
      # Fee here does not matter, but we have to provide it if not dynamic fee is available at the moment
      tx = self.create_tx(destination = destination, amount = amount, outputs = outputs, fee = 0.00000001)
      tx = electrum.Transaction(tx)
      tx_size = tx.estimated_size()
      self.wallet.remove_transaction(tx.txid())
      return tx_size
    except Exception as e:
      raise Exception("Failed to estimate tx size for wallet: {} {}".format(self.wallet, e))

  def create_tx(self, destination = None, amount = None, outputs = None, fee = None):
    try:
      final_outputs = []
      if destination and amount:
        amount_sat = electrum.commands.satoshis_or_max(amount)
        final_outputs = [electrum.transaction.PartialTxOutput.from_address_and_value(destination, amount_sat)]
      else:
        for address, amount in outputs:
          amount_sat = electrum.commands.satoshis_or_max(amount)
          final_outputs.append(electrum.transaction.PartialTxOutput.from_address_and_value(address, amount_sat))
      tx = self.wallet.create_transaction(
          final_outputs,
          fee=electrum.commands.satoshis(fee),
          feerate=None,
          change_addr=None,
          domain_addr=None,
          domain_coins=None,
          unsigned=False,
          rbf=True,
          password=self.wallet_password,
          locktime=None)
      result = tx.serialize()
      return result
    except Exception as e:
      raise Exception("Failed to create tx for wallet: {} {}".format(self.wallet, e))

  def send_to(self, destination, amount):
    logging.info("Trying to send full balance of %s", self.wallet)
    tx = self.create_tx(destination = destination, amount = amount)
    self.get_event_loop()
    self.connect_to_network()
    while not self.network.is_connected():
      print('Connecting...')
      time.sleep(1)      
    self.broadcast(tx, amount)
    self.stop_network()

  def broadcast(self, tx, amount):
    try:
      tx = electrum.Transaction(tx)
      task = asyncio.ensure_future(self.network.broadcast_transaction(tx))
      while not task.done():
        print('Broadcasting...')
        time.sleep(1)
      task.result()
      logging.info("Sent {} BTC from {}, txid: {}".format(amount, self.wallet, tx.txid()))
      print("Sent {} BTC from {}, txid: {}".format(amount, self.wallet, tx.txid()))
    except Exception as e:
      self.stop_network()
      self.wallet.remove_transaction(tx.txid())
      raise Exception("Failed to broadcast wallet: {} tx: {} {}".format(self.wallet, tx.txid(), e))

  async def async_broadcast(self, tx):
    try:
      tx = electrum.Transaction(tx)
      logging.info('Trying to broadcast {}...'.format(tx.txid()))
      await self.network.broadcast_transaction(tx)
      logging.info("{} sent txid: {}".format(self.wallet, tx.txid()))
    except Exception as e:
      self.wallet.remove_transaction(tx.txid())
      raise Exception("Failed to broadcast wallet: {} tx: {} {}".format(self.wallet, tx.txid(), e))

class APICmdUtil:

  def __init__(self, cmd_manager, wallet_id = None, wallet_password = None):
    self.cmd_manager = cmd_manager
    self.threshold_multiplier = 1
    self.last_batch = None
    if wallet_id != None:
      self.wallet_id = wallet_id
      self.cmd_manager.set_wallet(wallet_id, wallet_password)

  async def _get_tx_weighted_fee(self, addr, btc_amount):
    total_amount, total_size, total_fee = await self._get_details_of_unsent(addr, btc_amount)
    tx_proportion = int(btc_amount * 1.0e8) / total_amount
    this_tx_fee = tx_proportion * total_fee
    return this_tx_fee

  async def _get_details_of_unsent(self, addr = None, btc_amount = None, set_password = False):
    if addr:
      total_amount = int(btc_amount * 1.0e8)
      outputs = [[addr, btc_amount]]
    else:
      total_amount = 0
      outputs = []

    with DbManager() as db_manager:
      unsent = db_manager.get_unsent(self.wallet_id)

    if not unsent and not total_amount:
      return None, None, None

    if set_password:
      wallet_password = cryptocode.decrypt(unsent[0].wallet_password, unsent[0].sr_id)
      self.cmd_manager.set_wallet(self.wallet_id, wallet_password)

    for tx in unsent:
      total_amount += tx.amount
      outputs.append([tx.address, tx.amount / 1.0e8])

    total_size = self.cmd_manager.get_tx_size(outputs = outputs)
    total_fee = self.cmd_manager.conf.estimate_fee(total_size, allow_fallback_to_static_rates = True) / 1.0e8

    return total_amount, total_size, total_fee

  async def presend(self, addr, btc_amount):
    '''Create a transaction to estimate fee only, dry run of send. 
      Fee level estimates for one transaction is proportionally calculated as one tx / total = percent of fee
    '''
    this_tx_fee = await self._get_tx_weighted_fee(addr, btc_amount)
    return this_tx_fee

  async def send(self, addr, btc_amount):
    '''Schedules send of a transaction. 
      Fee level estimates for one transaction is calculated as one tx / total = percent of fee
      Continue to batch incoming sends until (tx_fee)/(total amount being sent) is less than percent threshold. Default 5%
    '''
    this_tx_fee = await self._get_tx_weighted_fee(addr, btc_amount)

    with DbManager() as db_manager:
      obj = db_manager.insert_transaction(addr, int(btc_amount * 1.0e8), self.wallet_id, self.cmd_manager.wallet_password)
      sr_id = obj.sr_id

    return this_tx_fee, sr_id

  async def send_batch(self):
    ''' Check if batch meets fee to send ratio. In case ratio is met
        create and broadcast the transaction, record changes in DB
        In case of failure in broadcast, delete transaction from wallet
        history to avoid missing utxo errors
    '''
    wallets = os.listdir('./'+self.cmd_manager.config['SYSTEM']['wallet_dir'])
    for wallet in wallets:
      self.wallet_id = wallet.split('_')[1]

      total_amount, total_size, total_fee = await self._get_details_of_unsent(set_password = True)
      if not total_amount:
        logging.info('{}: No transactions queued'.format(wallet))
        continue

      fee_to_amount_proportion = int(total_fee * 1.0e8) / total_amount
      current_fa_ratio = (int(self.cmd_manager.config['USER']['fa_ratio_min']) / 100) * self.threshold_multiplier

      logging.info('{}: Current fee to send ratio: {}, current fee to amount: {}'\
        .format(wallet, current_fa_ratio, fee_to_amount_proportion))

      if current_fa_ratio >= fee_to_amount_proportion:

        with DbManager() as db_manager:
          unsent = db_manager.get_unsent(self.wallet_id)
          outputs = []
          for tx in unsent:
            outputs.append([tx.address, tx.amount / 1.0e8])
          serialized_tx = self.cmd_manager.create_tx(outputs = outputs, fee = total_fee)
          tx = electrum.Transaction(serialized_tx)
          self.cmd_manager.wallet.add_transaction(tx)
          self.cmd_manager.wallet.save_db()
          try:
            await self.cmd_manager.async_broadcast(serialized_tx)
            db_manager.update_transactions(self.wallet_id, tx.txid(), total_fee, total_amount)
            self.threshold_multiplier = 1
          except Exception as e:
            self.cmd_manager.wallet.remove_transaction(tx.txid())
            self.cmd_manager.wallet.save_db()
            raise e

    if current_fa_ratio * 2 <= int(self.cmd_manager.config['USER']['fa_ratio_max']) / 100:
      self.threshold_multiplier *= 2 if self.threshold_multiplier != 1 else 2

  @classmethod
  async def get_tx(cls, sr_id):
    with DbManager() as db_manager:
      obj = db_manager.get_tx(sr_id)
    if not obj:
      return {}
    if obj.txid:
      result = {'txid': obj.txid, 'sr_timestamp': obj.sr_timestamp, 'tx_timestamp': obj.tx_timestamp,
     'addr': obj.address, 'amount': '{:.8f}'.format(obj.amount / 1.0e8), 'tx_fee': obj.fee}
    else:
      result = {'sr_timestamp': obj.sr_timestamp,
     'addr': obj.address, 'amount': '{:.8f}'.format(obj.amount / 1.0e8)}

    return result

  @classmethod
  async def get_send_history(cls, limit):
    with DbManager() as db_manager:
      objs = db_manager.get_sent_txs(limit)
    txs = []
    for tx in objs:
      txs.append({
        'tx_timestamp': tx.tx_timestamp,
        'sr_id': tx.sr_id,
        'tx_id': tx.txid
        })
    return txs

  @classmethod
  async def get_queue(cls, cmd_util):
    wallets = os.listdir('./'+cmd_util.cmd_manager.config['SYSTEM']['wallet_dir'])
    queue = {}
    for wallet in wallets:
      cmd_util.wallet_id = wallet.split('_')[1]

      with DbManager() as db_manager:
        objs = db_manager.get_unsent(cmd_util.wallet_id)

      if not objs:
        continue

      wallet_password = cryptocode.decrypt(objs[0].wallet_password, objs[0].sr_id)
      cmd_util.cmd_manager.set_wallet(cmd_util.wallet_id, wallet_password)
      txs = []
      outputs = []
      total_amount = 0
      total_fee = 0
      for tx in objs:
        txs.append(tx.sr_id)
        total_amount += tx.amount
        outputs.append([tx.address, tx.amount / 1.0e8])

      total_size = cmd_util.cmd_manager.get_tx_size(outputs = outputs)
      total_fee = cmd_util.cmd_manager.conf.estimate_fee(total_size, allow_fallback_to_static_rates = True) / 1.0e8
      fee_to_amount_proportion = int(total_fee * 1.0e8) / total_amount

      queue[wallet] = {
        'sr_ids': txs,
        'amount': '{:.8f}'.format(total_amount / 1.0e8),
        'fee': '{:.8f}'.format(total_fee),
        'fa_ratio': (int(cmd_util.cmd_manager.config['USER']['fa_ratio_min']) / 100) * cmd_util.threshold_multiplier,
        'fa_ratio_limit': fee_to_amount_proportion,
        'next_send_attempt_in': int(cmd_util.cmd_manager.config['USER']['send_frequency']) * 60 - (int(time.time()) - cmd_util.last_batch)
      }

    return queue