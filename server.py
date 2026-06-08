import psycopg2
import socket
import threading

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



server = socket.socket(socket.AF_INET , socket.SOCK_STREAM)
server.bind(("localhost",9999))
server.listen()

clients ={}
clients_lock = threading.Lock()

def save_message(conn,username,message):
    with conn.cursor as cur:
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
    with conn.cursor as cur:
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


def handle_client(client_socket):
    username = None
    try:
        username = (client_socket.recv(1024).decode().strip())

        
        
        with clients_lock:
            clients[username]=client_socket
        
        history = get_last_20_messages()
        for msg in history:
            client_socket.send(f"{msg}\n".encode())
        
        broadcast(None,f"[server]{username} has joined the chat")

        while True:
            data = client_socket.recv(1024)

            if not data:
                break

            message = data.decode().strip()

            if message == "/quit":
                break

            save_message(username,message)

            broadcast(username,message)

    except Exception as e:
        print(f"Error for {username}:{e}")

    finally:
        with clients_lock:
            if username in clients:
                del clients[username]

        if username:
            broadcast(None,f"[server]{username} has left the chat")
        
        client_socket.close()
        

while True:
    client_socket,address = server.accept()
    threading.Thread(target= handle_client, args= (client_socket,)).start()






    

