import psycopg2
import socket
import threading
from message import save_message,get_last_20_messages,broadcast

from db import create_table

server = socket.socket(socket.AF_INET , socket.SOCK_STREAM)
server.bind(("localhost",9999))
server.listen()

clients ={}
clients_lock = threading.Lock()



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






    

