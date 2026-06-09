
import threading

from db import ThreadedConnectionPool as pool

clients ={}
clients_lock = threading.Lock()



def save_message(conn,username,message):
    conn = pool.getconn
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into messages
            (sender,content)
            VALUES (%s,%s)
            """,
            (username,message)
        )
        conn.commit()

def get_last_20_messages(conn):
    conn = pool.getconn
    with conn.cursor() as cur:
        cur.execute(
            """
            select sender as username, content as message from messages order by sent_at desc limit 20
            """
        )
        rows = cur.fetchall()
        return rows[::-1]

def broadcast(sender,message):
    with clients_lock:
        for username,sock in clients.items():

            if username == sender:
                continue
            sock.send(f"{sender}:{message}".encode())
