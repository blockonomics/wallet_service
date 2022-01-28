## Payment Forwarding

### Requirements:

- Python >= 3.8
- Electrum 4.1.5

### Installation example on Ubuntu

Use virtual environment

1. Packages:
    * Libsec package is needed `sudo apt install libsecp256k1-dev`
    * Rust compiler may need to be installed depending on current server config: `sudo apt install rustc`
2. Electrum:
    * `git clone git://github.com/spesmilo/electrum.git`
    * `cd electrum`
    * `python -m pip install .[fast]`
3. Install required PIP packages:
    * sqlalchemy
    * requests
    * sanic
4. Init DB `python db_model.py`

### API

Before using the API, start the server with: `python wallet_service_api.py` Default server will run in localhost PORT 8000

To use the API, use the CLI commands to create a wallet and get or set the API password:
```
python wallet_service_api.py getAPIConfig
python wallet_service_api.py setAPIConfig api_password <password>
python wallet_service_api.py createWallet <wallet_password>
```

To get CLI help, run `python wallet_service_api.py -h`

#### POST /api/presend
Estimate transaction fee, dry run of send. Fee level estimate for one transaction is proportionally calculated as one tx / total = percent of fee

**Parameters:**
`{addr, btc_amount, wallet_id, wallet_password, admin_password}`

**Response:**
```
estimated_fee : Estimated fee that will be taken for this send (Proportionally calculated)
error: 500 HTTP Status / “Error msg” (BTC_amount may be more than wallet etc)
```

#### POST /api/send
Schedules the transaction to be sent when threshold is met. Fee level estimates for one transaction is calculated as one tx / total = percent of fee

**Parameters:**
`{addr, btc_amount, wallet_id, wallet_password, admin_password}`

**Response:**
```
estimated_fee: Estimated fee that will be taken for this send (Proportionally calculated)
internal_txid: internal txid to track this send  
error: 500 HTTP Status / “Error msg”
```

#### GET /api/send/<internal_txid>

**Response:**
```
txid: Bitcoin txid of internal_txid if already sent  
timestamp: Timestamp of bitcoin txid broadcast if already sent 
addr, btc_amount: of this internal_txid
fee: Actual fee of taken by this internal tx
```

#### GET /api/send_history?limit=1

Return the history of sends that happened

**Response:**
Array of (timestamp, bitcoin_txids) sorted in descending order