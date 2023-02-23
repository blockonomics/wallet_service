from sanic import Sanic
from sanic.response import text, json
from electrum_cmd_util import APICmdUtil, ElectrumCmdUtil
import asyncio
import utils
import logging
import time

app = Sanic("BlockonomicsWalletServiceAPI")
cmd_manager = ElectrumCmdUtil()
cmd_util = APICmdUtil(cmd_manager)

@app.post("/api/presend")
async def presend(request):
  try:
    args = request.json
    utils.check_params(args, ['addr', 'btc_amount', 'wallet_id', 'wallet_password', 'api_password'])

    addr = args.get('addr')
    btc_amount = args.get('btc_amount')
    wallet_id = args.get('wallet_id')
    wallet_password = args.get('wallet_password')
    api_password = args.get('api_password')

    if api_password != cmd_manager.config['USER']['api_password']:
      raise Exception('Incorrect API password')

    post_cmd_util = APICmdUtil(cmd_manager, wallet_id, wallet_password)

    estimated_fee = await post_cmd_util.presend(addr, btc_amount)
    return json({"estimated_fee": '{:.8f}'.format(estimated_fee)})
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

@app.post("/api/send")
async def send(request):
  try:
    args = request.json
    utils.check_params(args, ['addr', 'btc_amount', 'wallet_id', 'wallet_password', 'api_password'])

    addr = args.get('addr')
    btc_amount = args.get('btc_amount')
    wallet_id = args.get('wallet_id')
    wallet_password = args.get('wallet_password')
    api_password = args.get('api_password')

    if api_password != cmd_manager.config['USER']['api_password']:
      raise Exception('Incorrect API password')

    post_cmd_util = APICmdUtil(cmd_manager, wallet_id, wallet_password)
  
    estimated_fee, sr_id = await post_cmd_util.send(addr, btc_amount)
    return json({"estimated_fee": '{:.8f}'.format(estimated_fee), "sr_id": sr_id})
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

@app.post("/api/get_balance")
async def get_balance(request):
  try:
    args = request.json
    utils.check_params(args, ['wallet_id', 'wallet_password', 'api_password'])

    wallet_id = args.get('wallet_id')
    wallet_password = args.get('wallet_password')
    api_password = args.get('api_password')

    if api_password != cmd_manager.config['USER']['api_password']:
      raise Exception('Incorrect API password')

    balance_cmd_util = APICmdUtil(cmd_manager, wallet_id, wallet_password)
  
    confirmed, unconfirmed = await balance_cmd_util.get_balance()
    return json({"confirmed": confirmed, "unconfirmed": unconfirmed})
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

@app.get("/api/detail/<sr_id>")
async def detail(request, sr_id):
  try:
    if not sr_id:
      raise Exception('Missing param sr_id')
    data = await APICmdUtil.get_tx(sr_id)
    return json(data)
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

@app.get("/api/history")
async def history(request):
  try:
    limit = request.args.get("limit")
    data = await APICmdUtil.get_send_history(limit)
    return json(data)
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

@app.get("/api/queue")
async def queue(request):
  try:
    data = await APICmdUtil.get_queue(cmd_util)
    return json(data)
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

@app.listener("after_server_start")
async def server_start_listener(app, loop):
  # Once server is running, grab the loop of the server and start
  # Bitcoin network
  asyncio.ensure_future(main_loop())
  cmd_manager.get_event_loop()
  cmd_manager.connect_to_network()

async def main_loop():
  last_batch_send_try = int(time.time())
  while True:
    try:
      cmd_util.last_batch = last_batch_send_try
      # Re-read config in case of any updates
      cmd_manager.config.read(cmd_manager.config_file)
      await cmd_manager.log_network_status()
      await cmd_util.send_batch()
    except Exception as e:
      logging.error("%s", e)
    await asyncio.sleep(10)

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8000, debug=True)
