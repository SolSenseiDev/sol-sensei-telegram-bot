from sqlalchemy import Column, Integer, BigInteger, Text, ForeignKey, DateTime, Numeric, Enum, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base
from sqlalchemy import Numeric
import enum


class TradeType(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)

    pnl = Column(Integer, default=0)
    points = Column(Integer, default=0)
    referral_code = Column(Text, unique=True)
    referred_by = Column(Text)
    referrals_total = Column(Integer, default=0)
    referrals_active = Column(Integer, default=0)

    wallets = relationship("Wallet", back_populates="user")
    trades = relationship("Trade", back_populates="user")
    slippage_tolerance = Column(Integer, default=1)
    tx_fee = Column(Numeric(asdecimal=True), default=0.001)


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    address = Column(Text, nullable=False)
    encrypted_seed = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="wallets")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(Text, nullable=False)
    wallet_address = Column(Text, nullable=False)

    type = Column(Enum(TradeType), nullable=False)  # BUY or SELL
    token_amount = Column(Numeric(asdecimal=True), nullable=False)
    amount_usdc = Column(Numeric(asdecimal=True), nullable=False)
    price_per_token = Column(Numeric(asdecimal=True), nullable=True)

    realized_pnl = Column(Numeric(asdecimal=True), nullable=True)

    txid = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="trades")



class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("user_id", "wallet_address", "token", name="uix_position_user_wallet_token"),
    )

    id = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    wallet_address  = Column(Text, nullable=False)
    token           = Column(Text, nullable=False)
    entry_amount_usdc = Column(Numeric(asdecimal=True), nullable=False, default=0)
    token_amount      = Column(Numeric(asdecimal=True), nullable=False, default=0)
    created_at      = Column(DateTime, server_default=func.now())

    user = relationship("User")


class ReferralReward(Base):
    __tablename__ = "referral_rewards"

    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    points_given = Column(Integer, default=0)

    referrer = relationship("User", foreign_keys=[referrer_id])
    referee = relationship("User", foreign_keys=[referee_id])