from sanic import Sanic
from sanic.response import text, json
from electrum_cmd_util import APICmdUtil
import utils

app = Sanic("BlockonomicsWalletServiceAPI")

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

    estimated_fee = await APICmdUtil.presend(addr, btc_amount, wallet_id, wallet_password, api_password)
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
  
    estimated_fee, sr_id = await APICmdUtil.send(addr, btc_amount, wallet_id, wallet_password, api_password)
    return json({"estimated_fee": '{:.8f}'.format(estimated_fee), "sr_id": sr_id})
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

@app.get("/api/detail/<sr_id>")
async def send(request, sr_id):
  try:
    if not sr_id:
      raise Exception('Missing param sr_id')
    data = await APICmdUtil.get_tx(sr_id)
    return json(data)
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

@app.get("/api/history")
async def send(request):
  try:
    limit = request.args.get("limit")
    data = await APICmdUtil.get_send_history(limit)
    return json(data)
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8000, debug=True)
