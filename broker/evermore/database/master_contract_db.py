# database/master_contract_db.py
# Evermore (AutoTradeTech) Master Contract Database
# Seeds symbol-token mappings from NSE official instrument files.

import io
import os

import pandas as pd
from sqlalchemy import Column, Float, Index, Integer, Sequence, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

from extensions import socketio
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)


DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


class SymToken(Base):
    __tablename__ = "symtoken"
    id = Column(Integer, Sequence("symtoken_id_seq"), primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    brsymbol = Column(String, nullable=False, index=True)
    name = Column(String)
    exchange = Column(String, index=True)
    brexchange = Column(String, index=True)
    token = Column(String, index=True)
    expiry = Column(String)
    strike = Column(Float)
    lotsize = Column(Integer)
    instrumenttype = Column(String)
    tick_size = Column(Float)

    __table_args__ = (Index("idx_symbol_exchange", "symbol", "exchange"),)


def init_db():
    logger.info("Initializing Evermore Master Contract DB")
    Base.metadata.create_all(bind=engine)


def delete_symtoken_table():
    logger.info("Deleting Symtoken Table for Evermore")
    SymToken.query.delete()
    db_session.commit()


def copy_from_dataframe(df):
    logger.info("Performing Bulk Insert for Evermore")
    data_dict = df.to_dict(orient="records")

    existing_tokens = {result.token for result in db_session.query(SymToken.token).all()}
    filtered_data_dict = [row for row in data_dict if row["token"] not in existing_tokens]

    try:
        if filtered_data_dict:
            db_session.bulk_insert_mappings(SymToken, filtered_data_dict)
            db_session.commit()
            logger.info(f"Bulk insert completed with {len(filtered_data_dict)} new records.")
        else:
            logger.info("No new records to insert.")
    except Exception as e:
        logger.error(f"Error during bulk insert: {e}")
        db_session.rollback()


def download_nse_instruments():
    """
    Download NSE instrument files for equity and derivatives.
    Uses NSE's official CSV instrument files.

    Returns:
        pd.DataFrame: Combined DataFrame of all instruments
    """
    client = get_httpx_client()
    frames = []

    # NSE Equity instruments (NSECM)
    nse_equity_urls = [
        "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
    ]

    # Try to download NSE equity list
    for url in nse_equity_urls:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/csv,application/csv,text/plain",
            }
            response = client.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                logger.info(f"Downloaded NSE equity data: {len(df)} records from {url}")
                frames.append(("NSECM", df))
                break
        except Exception as e:
            logger.warning(f"Failed to download from {url}: {e}")

    if frames:
        return frames
    else:
        logger.warning("Could not download NSE instrument files. Using empty dataset.")
        return []


def process_nse_equity(df):
    """
    Process NSE equity CSV into SymToken format.

    NSE EQUITY_L.csv typically has columns:
    SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE
    """
    if df.empty:
        return pd.DataFrame()

    # NSE equity files may have different column names
    # Try to normalize
    cols = df.columns.tolist()
    logger.info(f"NSE equity columns: {cols}")

    # Create the output DataFrame
    records = []
    for _, row in df.iterrows():
        symbol = str(row.get("SYMBOL", row.get("symbol", ""))).strip()
        name = str(row.get("NAME OF COMPANY", row.get("name", ""))).strip()

        if not symbol:
            continue

        records.append({
            "symbol": symbol,
            "brsymbol": symbol,
            "name": name,
            "exchange": "NSE",
            "brexchange": "NSECM",
            "token": "",  # Token will need to be mapped separately
            "expiry": "",
            "strike": 0.0,
            "lotsize": 1,
            "instrumenttype": "EQ",
            "tick_size": 0.05,
        })

    return pd.DataFrame(records)


def master_contract_download():
    """
    Download and process master contract data for Evermore.

    Since Evermore uses NSE exchange tokens, we download NSE instrument files
    and create the symbol-token mapping database.

    Note: Token numbers need to be mapped separately as NSE equity CSVs
    don't always include exchange tokens. For a production setup, consider:
    1. Using the NSE bhavcopy with token numbers
    2. Getting tokens from Evermore's support team
    3. Using another broker's instrument file that includes NSE tokens
    """
    logger.info("Downloading Master Contract for Evermore (from NSE)")

    try:
        nse_data = download_nse_instruments()

        all_records = []
        for exchange_code, df in nse_data:
            if exchange_code == "NSECM":
                processed = process_nse_equity(df)
                if not processed.empty:
                    all_records.append(processed)

        if all_records:
            combined_df = pd.concat(all_records, ignore_index=True)
            logger.info(f"Total instruments processed: {len(combined_df)}")

            delete_symtoken_table()
            copy_from_dataframe(combined_df)

            return socketio.emit(
                "master_contract_download",
                {"status": "success", "message": f"Successfully loaded {len(combined_df)} instruments"},
            )
        else:
            logger.warning("No instrument data available. SymToken table will be empty.")
            return socketio.emit(
                "master_contract_download",
                {"status": "warning", "message": "No NSE instrument data available. Manual token mapping required."},
            )

    except Exception as e:
        logger.error(f"Error downloading master contract: {e}")
        return socketio.emit(
            "master_contract_download",
            {"status": "error", "message": str(e)},
        )


def search_symbols(symbol, exchange):
    """Search for symbols matching the given pattern."""
    return SymToken.query.filter(
        SymToken.symbol.like(f"%{symbol}%"),
        SymToken.exchange == exchange,
    ).all()
