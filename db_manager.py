from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm.exc import NoResultFound
from db_model import Transactions
import time
import uuid

class DbManager:

  def __init__(self, echo_mode=False):
    Base = declarative_base()
    engine = create_engine('sqlite:///wallet_service_db', echo=echo_mode)
    Base.metadata.bind = engine
    self.session = sessionmaker(bind=engine)()
 
  def __del__(self):
    self.session.close()
  
  def __exit__(self, *err):
    pass
  
  def __enter__(self):
    return self

  def close_session(self):
    self.session.close()    

  def insert_transaction(self, address, amount, wallet_id, tx_size):
    unsent = self.get_unsent(wallet_id)
    if unsent:
      internal_txid = unsent[0].internal_txid
    else:
      internal_txid = str(uuid.uuid4().hex)

    # Only sent transactions have txid, fee and timestamp
    obj = Transactions(
        internal_txid = internal_txid,
        txid = None,
        address = address,
        amount = amount,
        wallet_id = wallet_id,
        relative_tx_size = tx_size,
        fee = None,
        timestamp_ms = None
      )
    self.session.add(obj)
    self.session.commit()
    return obj, unsent

  def get_unsent(self, wallet_id):
    return self.session.query(Transactions).filter(Transactions.txid == None, Transactions.wallet_id == wallet_id).all()

  def get_txs(self, internal_txid):
    return self.session.query(Transactions).filter(Transactions.internal_txid == internal_txid).all()

  def update_transactions(self, internal_txid, txid, total_fee):
    objs = self.session.query(Transactions).filter(Transactions.internal_txid == internal_txid).all()
    # Calculate total relative size of all transactions in this batch
    # With the total fee and total relative size, we calculate each individual transactions fee
    # One transaction is proportionally calculated as one tx / total = percent of fee
    total_relative_size = 0
    for tx in objs:
      total_relative_size += tx.relative_tx_size
    for obj in objs:
      obj.txid = txid
      obj.fee = total_fee * (obj.relative_tx_size / total_relative_size)
      obj.timestamp_ms = int(time.time())
    self.session.commit()
