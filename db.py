import psycopg2

def get_connection(db_config:dict):
    try:
        connection = psycopg2.connect(
            host =db_config['host'] ,
            port = db_config['port'],
            dbname = db_config['dbname'],
            user = db_config['user'],
            password = db_config['password']
        )
        return connection
    except Exception as e:
        print("Connection failed",e.__traceback__)

def create_table(conn):
    with conn.cursor as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
        id          SERIAL PRIMARY KEY,
        sender      VARCHAR(64)  NOT NULL,
        content     TEXT         NOT NULL,
        sent_at     TIMESTAMPTZ  DEFAULT NOW(),
        is_direct   BOOLEAN      DEFAULT FALSE,
        recipient   VARCHAR(64)  -- NULL for broadcast, username for DMs)
            """
        )
        cur.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at DESC)
            """
        )
        conn.commit()

