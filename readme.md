# Self hosted bitcoin wallet service
This is a lightweight bitcoin wallet service that is easy to install and can be run on a 5$ VPS. 

## Features
- Self custody of funds
- Automatic batching of transactions to minimize fee
- Easy to use REST API interface 
- Communicates with electrum server for fetching blockchain data 
- Gets up running instantly [no requirement for waiting days to sync with network] 

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
    * cryptocode
4. Init DB `python db_model.py`

### API

Before using the API, start the server with: `python wallet_service_api.py` Default server will run in localhost PORT 8000

Before using the API for the first time, use the CLI commands to create a wallet and get or set the API password:
```
python wallet_service_cli.py createWallet <wallet_password>
python wallet_service_cli.py getAPIConfig
python wallet_service_cli.py setAPIConfig api_password <password>
```

To get CLI help, run `python wallet_service_cli.py -h`

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
sr_id: send request id (unique internal id to track this send)  
error: 500 HTTP Status / “Error msg”
```

#### GET /api/detail/<sr_id>

**Response:**
``` 
tx_id: Bitcoin transaction id of this send if it has been sent 
sr_timestamp: Timestamp of this send request (in unix milliseconds)
tx_timestamp: Timestamp of actual bitcoin tx (in unix milliseconds)
addr: Bitcoin Address to send payment to
amount: Amount of bitcoin to send
tx_fee: Actual weighted network fee taken by this send
```

#### GET /api/history?limit=1

Return the history of completed sends

**Response:**
Array of (tx_timestamp, sr_id, tx_id) dicts sorted in descending order of tx_timestamp.

#### GET /api/queue

Return the current status of send queue

**Response:**
{sr_ids: list of queued send requests, amount: total btc amount scheduled to be sent, fee: current fee required for send, fa_ratio: current fee to amount ratio, fa_ratio_limit: fa_ratio must be below this for send to complete, next_send_attempt_in: Time in seconds when next send will be attempted}


### API Config

Use CLI to get current values of config or change them:
```
python wallet_service_cli.py getAPIConfig
python wallet_service_cli.py setAPIConfig <param> <value>
```
Available configs are:
* **api_password**: Password to be used for HTTP API calls - generated randomly by default
* **fa_ratio_min** : Minimum tolerable fee to send amount ratio - default 5% 
* **fa_ratio_max** : Maximum tolerable fee to send amount ratio - default 50%
* **send_frequency** : Send is attempted regularly with this frequency  - default 5 minutes

