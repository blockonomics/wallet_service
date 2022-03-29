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
        sr_timestamp = int(time.time()),
        tx_timestamp = None,
        wallet_password = cryptocode.encrypt(wallet_password, sr_id)
      )
    self.session.add(obj)
    self.session.commit()
    return obj

  def get_unsent(self, wallet_id):
    return self.session.query(Transactions).filter(Transactions.txid == None, Transactions.wallet_id == wallet_id).all()

  def get_tx(self, sr_id):
    try:
      return self.session.query(Transactions).filter(Transactions.sr_id == sr_id).one()
    except Exception as e:
      return {}

  def get_all_txs(self, limit):
    return self.session.query(Transactions.txid, Transactions.sr_timestamp, Transactions.sr_id)\
      .order_by(Transactions.sr_timestamp).limit(limit).all()

  def get_sent_txs(self, limit):
    return self.session.query(Transactions.txid, Transactions.tx_timestamp, Transactions.sr_id)\
      .filter(Transactions.txid != None).order_by(Transactions.tx_timestamp.desc()).limit(limit).all()

  def update_transactions(self, wallet_id, txid, total_fee, total_amount):
    objs = self.get_unsent(wallet_id)
    total_fee_sat = int(total_fee * 1.0e8)
    for obj in objs:
      obj.txid = txid
      obj.fee = int(total_fee_sat * (obj.amount / total_amount))
      obj.tx_timestamp = int(time.time())
    self.session.commit()
