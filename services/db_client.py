import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date
from decimal import Decimal
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")

def get_connection():
    if not DB_CONNECTION_STRING:
        raise ValueError("DB_CONNECTION_STRING not found in environment variables")
    return psycopg2.connect(DB_CONNECTION_STRING)

def get_obligation_by_id(obligation_id: str) -> dict | None:
    """
    Fetches obligation details by ID.
    Returns a dict with principal_balance, total_due_date, net_due_date, remunerative_rate
    or None if not found.
    """
    query = """
    SELECT 
        principal_balance, 
        total_due_date, 
        net_due_date, 
        remunerative_rate 
    FROM schsaf.tbl_obligations 
    WHERE id = %s
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (obligation_id,))
                result = cur.fetchone()
                return result
    except Exception as e:
        print(f"Error fetching obligation: {e}")
        return None

def get_usury_rates(start_date: date, end_date: date) -> list[dict]:
    """
    Fetches daily usury rates (rate_type_id = 1) between start_date and end_date.
    Actually the table has 'start_date' for the rate validity. 
    We want all rate records that 'start' within or cover the range?
    The user logic says: "If the rate starts on 2025-11-01... apply...".
    So we fetch all rates with start_date >= requested_start OR just before.
    
    Simplification: Fetch all rates with start_date <= end_date AND (end_date >= start_date)
    We'll filter strictly by range needed.
    """
    query = """
    SELECT 
        start_date,
        value
    FROM schsaf.tbl_rate
    WHERE rate_type_id = 1
      AND start_date <= %s
      AND start_date >= %s
    ORDER BY start_date ASC
    """
    # We might need to go back a bit further than current start_date to find the rate *active* at start_date
    # But for now let's query the specific range
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # We want rates that start BEFORE or ON end_date. 
                # And usually we want to know the rate active valid for start_date.
                # So maybe we just fetch everything relevant around these dates.
                
                # Broaden the query slightly or logic? 
                # User query example: "start_date = '2025-11-01'".
                
                cur.execute(query, (end_date, start_date)) 
                results = cur.fetchall()
                return results
    except Exception as e:
        print(f"Error fetching usury rates: {e}")
        return []

def get_active_usury_rate_for_date(target_date: date) -> dict | None:
    """
    Finds the specific rate entry valid for a given date.
    (The one with max start_date that is <= target_date)
    """
    query = """
    SELECT start_date, value
    FROM schsaf.tbl_rate
    WHERE rate_type_id = 1
      AND start_date <= %s
    ORDER BY start_date DESC
    LIMIT 1
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (target_date,))
                result = cur.fetchone()
                return result
    except Exception as e:
        print(f"Error fetching specific usury rate: {e}")
        return None
