## Payment Forwarding

### Requirements:

- Python >= 3.7
- Electrum 4.1.5

### Installation

Use virtual environment

1. Electrum:
    * `git clone git://github.com/spesmilo/electrum.git`
    * `cd electrum`
    * `python -m pip install .[fast]`
2. Install required PIP packages:
    * sqlalchemy
    * requests
    * sanic
3. Init DB `python db_model.py`

### Usage

To start the REST API server: `python wallet_service_api.py`

To get CLI help text: `python wallet_service_cli.py -h` 