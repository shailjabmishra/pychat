
import threading

from db import pool

from shared import clients,clients_lock




def save_message(username,message):
    conn = pool.getconn()
    try:
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
    finally:
        pool.putconn(conn)

def get_last_20_messages():
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select sender as username, content as message from messages order by sent_at desc limit 20
                """
            )
            rows = cur.fetchall()
            return rows[::-1]
    finally:
        pool.putconn(conn)

def broadcast(sender,message):
    with clients_lock:
        for username,sock in clients.items():

            if username == sender:
                continue
            sock.send(f"{sender}:{message}".encode())
