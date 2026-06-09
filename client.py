import socket
import threading
from datetime import datetime

HOST= "localhost"
PORT= 9999

running = True

def recieve_messages(client_socket):
    global running

    try:
        while running:
            data = client_socket.recv(1024)

            if not data:
                print("\n[Error] Server disconnected ")
                running = False
                break

            print(data.decode())
    
    except:
        print("\n[Error]Lost connection to server.")
        running = False

def send_messages(client_socket,username):
    global running

    try:

        while running:
            message = input()

            if message == "/quit":
                client_socket.send(message.encode())
                running = False
                break

            timestamp = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            formattedmessage = (f"[{timestamp}] {username}:{message}")
            print(formattedmessage)

            client_socket.send(formattedmessage.encode())
    
    except Exception:
        running = False

def main():
    global running

    try:
        client_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        client_socket.connect((HOST,PORT))

        username = input("Enter name of the user:")
        client_socket.send(username.encode())

        recieve_thread = threading.Thread(target= recieve_messages,args=(client_socket,))
        send_thread = threading.Thread(target=send_messages,args=(client_socket,username))

        recieve_thread.start()
        send_thread.start()

        recieve_thread.join()
        send_thread.join()
    
    except ConnectionRefusedError:
        print("[Error]Could not connect to server")

    finally:
        running = False
        try:
            client_socket.close()
        except:
            pass




