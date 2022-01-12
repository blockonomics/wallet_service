MIN_BTC_AMOUNT = 0.00000001

def check_params(data, params):
  sanitize_params(data)
  for param in params:
    if data.get(param) == None:
      raise Exception('Missing param {}'.format(param))
    if param.startswith('email') and '@' not in data.get(param):
      raise Exception('Invalid param {}'.format(param))
    if param == 'btc_amount':
      try:
        if float(data.get(param)) < MIN_BTC_AMOUNT:
          raise Exception
      except Exception:
        raise Exception('btc_amount must be a float more than {:.8f}'.format(MIN_BTC_AMOUNT))
    if param == 'wallet_id':
      try:
        if int(data.get(param)) < 0:
          raise Exception
      except Exception:
        raise Exception('wallet id must be a positive int')

def sanitize_params(input_dict):
  '''Sanitize params of a dict for DB safety
  Not primitive types are converted to string'''
  for key,value in input_dict.items():
    if type(value) not in [int, float, bool, str, bytes]:
      input_dict[key]=json.dumps(value)