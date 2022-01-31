# Self hosted bitcoin wallet service

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
Estimate transaction fee, dry run of send.

**Parameters:**
`{addr, btc_amount, wallet_id, wallet_password, admin_password}`

**Response:**
```
estimated_fee : Estimated fee for this send 
error: 500 HTTP Status / “Error msg”
```

#### POST /api/send
Schedules the transaction to be sent when threshold is met.

**Parameters:**
`{addr, btc_amount, wallet_id, wallet_password, admin_password}`

**Response:**
```
estimated_fee: Estimated weighted fee for this send 
srid: send request id (unique internal id to track this send)  
error: 500 HTTP Status / “Error msg”
```

#### GET /api/detail/<sr_id>

**Response:**
```
estimated_fee: Estimated weighted fee for this send 
tx_id: Bitcoin transaction id of this send if it has been sent 
timestamp: Timestamp of this send request (in unix milliseconds)
addr: Bitcoin Address to send payment to
amount: Amount of bitcoin to send
tx_fee: Actual weighted network fee of taken by send
```

#### GET /api/history?limit=1

Return the history of sends that happened

**Response:**
Array of (timestamp, sr_id, status) dicts sorted in descending order of timestamp. Status can be *queued* or *sent*

### API Config

Use CLI to get current values of config or change them:
```
python wallet_service_api.py getAPIConfig
python wallet_service_api.py setAPIConfig <param> <value>
```
Available configs are:
* **api_password**: Password to be used for HTTP API calls - generated randomly by default
* **batching_threshold** : Continue to batch incoming sends until this percent threshold is met, default 5%. Threshold is calculated as (tx_fee)/(total amount being sent)

