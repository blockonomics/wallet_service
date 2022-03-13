from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm.exc import NoResultFound
from db_model import Transactions
import time
import uuid
import cryptocode

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

  def insert_transaction(self, address, amount, wallet_id, wallet_password):
    # Only sent transactions have txid and fee
    sr_id = str(uuid.uuid4().hex)
    obj = Transactions(
        sr_id = sr_id,
        txid = None,
        address = address,
        amount = amount,
        wallet_id = wallet_id,
        fee = None,
        timestamp_ms = int(time.time()),
        wallet_password = cryptocode.encrypt(wallet_password, sr_id)
      )
    self.session.add(obj)
    self.session.commit()
    return obj

  def get_unsent(self, wallet_id):
    return self.session.query(Transactions).filter(Transactions.txid == None, Transactions.wallet_id == wallet_id).all()

  def get_tx(self, sr_id):
    return self.session.query(Transactions).filter(Transactions.sr_id == sr_id).one()

  def get_all_txs(self, limit):
    return self.session.query(Transactions.txid, Transactions.timestamp_ms, Transactions.sr_id)\
      .order_by(Transactions.timestamp_ms).limit(limit).all()

  def update_transactions(self, wallet_id, txid, total_fee, total_amount):
    objs = self.get_unsent(wallet_id)
    total_fee_sat = int(total_fee * 1.0e8)
    for obj in objs:
      obj.txid = txid
      obj.fee = int(total_fee_sat * (obj.amount / total_amount))
    self.session.commit()
