from sqlalchemy import create_engine
from sqlalchemy import String, Column, BigInteger, Integer
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:///wallet_service_db')

Base = declarative_base()

class Transactions(Base):
    __tablename__ = 'transactions'
    internal_txid = Column(String(250), primary_key = True)
    txid = Column(String(250))
    address = Column(String(250), primary_key = True)
    amount = Column(Integer)
    wallet_id = Column(Integer)
    relative_tx_size = Column(Integer)
    fee = Column(Integer)
    timestamp_ms = Column(BigInteger)

Base.metadata.create_all(engine)