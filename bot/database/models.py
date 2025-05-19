from sqlalchemy import Column, Integer, BigInteger, Text, ForeignKey
from sqlalchemy.orm import relationship
from .db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)

    wallets = relationship("Wallet", back_populates="user")


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    address = Column(Text, nullable=False)
    encrypted_seed = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="wallets")