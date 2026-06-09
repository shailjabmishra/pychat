import psycopg2
from psycopg2.pool import ThreadedConnectionPool

try: 
    pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host="localhost",
            port=5432,
            dbname="pychatdb",
            user="admin",
            password="admin"
            )
    
        

except Exception as e:
    print("Connection failed",e.__traceback__)

def create_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
        id          SERIAL PRIMARY KEY,
        sender      VARCHAR(64)  NOT NULL,
        content     TEXT         NOT NULL,
        sent_at     TIMESTAMPTZ  DEFAULT NOW(),
        is_direct   BOOLEAN      DEFAULT FALSE,
        recipient   VARCHAR(64)  )
            """
        )
        cur.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at DESC)
            """
        )
        conn.commit()

