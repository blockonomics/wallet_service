from sanic import Sanic
from sanic.response import text, json
from electrum_cmd_util import APICmdUtil
import utils

app = Sanic("BlockonomicsWalletServiceAPI")

@app.post("/api/presend")
async def presend(request):
  args = request.json
  utils.check_params(args, ['addr', 'btc_amount', 'wallet_id', 'wallet_password', 'api_password'])

  addr = args.get('addr')
  btc_amount = args.get('btc_amount')
  wallet_id = args.get('wallet_id')
  wallet_password = args.get('wallet_password')
  api_password = args.get('api_password')

  try:
    estimated_fee = await APICmdUtil.presend(addr, btc_amount, wallet_id, wallet_password, api_password)
    return json({"estimated_fee": '{:.8f}'.format(estimated_fee)})
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

@app.post("/api/send")
async def send(request):
  args = request.json
  utils.check_params(args, ['addr', 'btc_amount', 'wallet_id', 'wallet_password', 'api_password'])

  addr = args.get('addr')
  btc_amount = args.get('btc_amount')
  wallet_id = args.get('wallet_id')
  wallet_password = args.get('wallet_password')
  api_password = args.get('api_password')
  
  try:
    estimated_fee, internal_txid = await APICmdUtil.send(addr, btc_amount, wallet_id, wallet_password, api_password)
    return json({"estimated_fee": '{:.8f}'.format(estimated_fee), "internal_txid": internal_txid})
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

@app.get("/api/send/<internal_txid>")
async def send(request, internal_txid):
  try:
    if not internal_txid:
      raise Exception('Missing param internal_txid')
    data = await APICmdUtil.get_tx(internal_txid)
    return json(data)
  except Exception as e:
    return json({"error": '{}'.format(e)}, status = 500)

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8000, debug=True)
