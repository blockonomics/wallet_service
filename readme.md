# Self hosted bitcoin wallet service
This is a lightweight bitcoin wallet service that is easy to install and can be run on a 5$ VPS. 

![Wallet logo_v2](https://user-images.githubusercontent.com/22165583/161113280-7e43bd9a-fa21-4cdf-94ed-3f13db32dbdc.png)

## Features
- Complete self custody of funds
- Automatic batching of send transactions to minimize fee
- Easy to use REST API interface 
- Communicates with electrum nodes internally for fetching blockchain data 
- Gets up running instantly [no requirement for waiting days to sync with network] 

## Installation 
Use virtual environment (python >=3.8)
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
5. Do basic config
    * `python wallet_service_cli.py createWallet <wallet_password>`
    * `python wallet_service_cli.py setAPIConfig api_password <password>`
6. Start the service (default port is localhost:8080)
    * `python wallet_service_api.py`




## API Documentation

#### POST /api/presend
Estimate transaction fee, dry run of send.

**Parameters:**
`{addr, btc_amount, wallet_id, wallet_password, api_password}`

**Response:**
```
estimated_fee : Estimated fee for this send 
error: 500 HTTP Status / “Error msg”
```

#### POST /api/send
Schedules the transaction to be sent when threshold is met.

**Parameters:**
`{addr, btc_amount, wallet_id, wallet_password, api_password}`

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

## Command Line
Various admin functions like creating wallet, getting balance can performed to CLI which can be acessed via
```
python wallet_service_cli.py -h
Available commands:
getAPIConfig
setAPIConfig <param> <value>
listWallets
createWallet <wallet_password>
getInfo <wallet_id> <wallet_password>
getBalance <wallet_id> <wallet_password>
getHistory <wallet_id> <wallet_password>
sendToAddress <wallet_id> <wallet_password> <btc_address> <btc_amount>
```

## API Config

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

