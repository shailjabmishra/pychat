import psycopg2
import socket
import threading
from message import save_message,get_last_20_messages,broadcast

from db import pool

from shared import clients ,clients_lock

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
        print(f"entering finally block for {username}")
        with clients_lock:
            if username in clients:
                del clients[username]

        if username:
            broadcast(None,f"[server]{username} has left the chat")
        
        client_socket.close()
        

def server_conn():
    while True:
        client_socket,address = server.accept()
        threading.Thread(target= handle_client, args= (client_socket,)).start()
        print("function is running")


try:
    server = socket.socket(socket.AF_INET , socket.SOCK_STREAM)
    server.bind(("0.0.0.0",2877))
    server.listen()
    server_conn()

finally:
    server.close()












    

