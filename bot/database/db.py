from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
)

print("🔍 POSTGRES_USER:", os.getenv('POSTGRES_USER'))
print("🔍 POSTGRES_PASSWORD:", os.getenv('POSTGRES_PASSWORD'))
print("🔍 POSTGRES_HOST:", os.getenv('POSTGRES_HOST'))
print("🔍 POSTGRES_PORT:", os.getenv('POSTGRES_PORT'))
print("🔍 POSTGRES_DB:", os.getenv('POSTGRES_DB'))
print("🔍 DATABASE_URL:", DATABASE_URL)

engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()