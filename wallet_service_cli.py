import argparse
import configparser
import os
import random, string
from electrum_cmd_util import ElectrumCmdUtil
from electrum import util

CONFIG_FILE = 'config.ini'
config = configparser.ConfigParser()
config.read(CONFIG_FILE)

def _check_api_password():
  # If no api password exists, create and set a random alphanumeric
  if config['USER']['api_password'] == '':
    set_config('api_password', 
      ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(16)))

def get_config():
  for key in config['SYSTEM']:
    print('{} = {}'.format(key, config['SYSTEM'][key]))
  for key in config['USER']:
    print('{} = {}'.format(key, config['USER'][key]))

def set_config(param, value):
  if param in config['USER']:
    config.set('USER', param, value)
  elif param in config['SYSTEM']:
    config.set('SYSTEM', param, value)
  else:
    raise Exception('Config param: {} does not exits'.format(param))
  with open(CONFIG_FILE, 'w') as configfile:
    config.write(configfile)

def list_wallets():
  # Sort by timestamp
  os.chdir(config['SYSTEM']['wallet_dir'])
  wallets = sorted(filter(os.path.isfile, os.listdir('.')), key=os.path.getmtime)
  for wallet in wallets:
    print(wallet.split('_')[1])

def create_wallet(wallet_password):
  cmd_manager = ElectrumCmdUtil()
  path, dirs, files = next(os.walk(config['SYSTEM']['wallet_dir']))
  last_id = len(files)
  seed, xpub = cmd_manager.create_wallet(last_id, wallet_password)
  print('Wallet created\nID: {}\nPassword: {}\nSeed: {}\nxPub: {}'.format(last_id, wallet_password, xpub, seed))

def get_wallet_info(wallet_id, wallet_password):
  cmd_manager = ElectrumCmdUtil()
  wallet = cmd_manager.load_wallet(wallet_id, wallet_password)
  xpub = wallet.get_master_public_key()
  seed = wallet.get_seed(wallet_password)
  print('xPub: {}\nSeed: {}'.format(xpub, seed))

def get_wallet_balance(wallet_id, wallet_password):
  cmd_manager = ElectrumCmdUtil()
  wallet = cmd_manager.load_wallet(wallet_id, wallet_password)
  print('Connecting to network and syncing wallet...')
  cmd_manager.wait_for_wallet_sync(wallet, True)
  balance = cmd_manager.get_balance(wallet)
  print('Confirmed: {}\nUnconfirmed: {}'.format(balance[0], balance[1]))

def get_wallet_history(wallet_id, wallet_password):
  cmd_manager = ElectrumCmdUtil()
  wallet = cmd_manager.load_wallet(wallet_id, wallet_password)
  print('Connecting to network and syncing wallet...')
  cmd_manager.wait_for_wallet_sync(wallet, True)
  history = cmd_manager.get_history(wallet)
  for tx in list(history.items()):
    if not tx[1]['date']:
      tx[1]['date'] = 'Waiting for confirmation'
    print('txid: {}, date: {}, amount: {}'\
      .format(tx[1]['txid'], tx[1]['date'], tx[1]['bc_value']))

def send_to_address(wallet_id, wallet_password, btc_address, btc_amount):
  cmd_manager = ElectrumCmdUtil()
  wallet = cmd_manager.load_wallet(wallet_id, wallet_password)
  print('Connecting to network and syncing wallet...')
  cmd_manager.wallet = wallet
  cmd_manager.wallet_password = wallet_password
  cmd_manager.send_to(btc_address, btc_amount)

def get_unused(wallet_id, wallet_password):
  ''' This command is used to fetch next unused address of a wallet.
      Designed to help testing by providing easy access of addresses for
      sending test transactions
  '''
  cmd_manager = ElectrumCmdUtil()
  wallet = cmd_manager.load_wallet(wallet_id, wallet_password)
  addr = wallet.get_unused_address()
  print(addr)

if __name__ == '__main__':
  _check_api_password()
  # Setup argument parser
  ap = argparse.ArgumentParser(
      description='Available commands:\n\n'
                  'getAPIConfig\n'
                  'setAPIConfig <param> <value>\n'
                  'listWallets\n'
                  'createWallet <wallet_password>\n'
                  'getInfo <wallet_id> <wallet_password>\n'
                  'getBalance <wallet_id> <wallet_password>\n'
                  'getHistory <wallet_id> <wallet_password>\n'
                  'sendToAddress <wallet_id> <wallet_password> <btc_address> <btc_amount>\n',
      formatter_class=argparse.RawTextHelpFormatter
    )
  ap.add_argument('command', help='command to run')
  ap.add_argument('options', nargs='*', help='options for command')
  args = vars(ap.parse_args())

  #Loop through commands to see which was called
  if args['command'].lower() == 'getAPIConfig'.lower():
    if len(args['options']) != 0:
      ap.error('getAPIConfig takes no options')
    get_config()

  elif args['command'].lower() == 'setAPIConfig'.lower():
    if len(args['options']) != 2:
      ap.error('setAPIConfig takes exactly 2 options: <param> <value>')
    param = args['options'][0]
    value = args['options'][1]
    set_config(param, value)

  elif args['command'].lower() == 'listWallets'.lower():
    if len(args['options']) != 0:
      ap.error('listWallets takes no options')
    list_wallets()

  elif args['command'].lower() == 'createWallet'.lower():
    if len(args['options']) != 1:
      ap.error('createWallet takes exactly 1 option: <wallet_password>')
    wallet_password = args['options'][0]
    create_wallet(wallet_password)

  elif args['command'].lower() == 'getInfo'.lower():
    if len(args['options']) != 2:
      ap.error('getInfo takes exactly 2 options: <wallet_id> <wallet_password>')
    wallet_id = args['options'][0]
    wallet_password = args['options'][1]
    get_wallet_info(wallet_id, wallet_password)

  elif args['command'].lower() == 'getBalance'.lower():
    if len(args['options']) != 2:
      ap.error('getBalance takes exactly 2 options: <wallet_id> <wallet_password>')
    wallet_id = args['options'][0]
    wallet_password = args['options'][1]
    get_wallet_balance(wallet_id, wallet_password)

  elif args['command'].lower() == 'getHistory'.lower():
    if len(args['options']) != 2:
      ap.error('getHistory takes exactly 2 options: <wallet_id> <wallet_password>')
    wallet_id = args['options'][0]
    wallet_password = args['options'][1]
    get_wallet_history(wallet_id, wallet_password)

  elif args['command'].lower() == 'sendToAddress'.lower():
    if len(args['options']) != 4:
      ap.error('sendToAddress takes exactly 4 options: <wallet_id> <wallet_password> <btc_address> <btc_amount>')
    wallet_id = args['options'][0]
    wallet_password = args['options'][1]
    btc_address = args['options'][2]
    btc_amount = args['options'][3]
    send_to_address(wallet_id, wallet_password, btc_address, btc_amount)

  elif args['command'] == 'getunused':
    if len(args['options']) != 2:
      ap.error('getrecord takes exactly 2 option: <wallet_id> <wallet_password>')
    wallet_id = args['options'][0]
    wallet_password = args['options'][1]
    get_unused(wallet_id, wallet_password)

  else:
    ap.error('No command found')
