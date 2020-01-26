import socket
import sys, pprint

def http_req_fixer_v2(data):
    data = data.decode('utf-8')
    req_type = data.split(' ')[0]
    url = data.split(' ')[1]
    host  = url.split('/')[1]
    
    files = ''
    location = url.split('/')
    for f in range(2,len(location)): #to grab just the path of the files requested  from the server 
        files = files + '/' + location[f]
    if files == '':
        files = url

    data = data.splitlines()
    fixed_req = ''
    for line_index in range(len(data)):
        if line_index == 0:
            #req_type, url
            fixed_req = fixed_req + req_type + ' ' + files + ' HTTP/1.1'
        elif line_index == 1:
            #host
            fixed_req = fixed_req + 'Host: ' + host
        elif 'Accept-Encoding' in data[line_index]:
            #encoding
            fixed_req = fixed_req + 'Accept-Encoding: utf-8'
        else:
            #if line doesn't need to be changed, add original
            fixed_req = fixed_req + data[line_index]
        if line_index != 15:
            #to not add a third carriage return at the end of the request
            fixed_req = fixed_req + '\r\n'
   
    #print('FIXED REQ:\n', fixed_req)

    return fixed_req, host





def http_req_fixer(data):
    """
    Takes in the output of socket.recv() changes request and host to remove localhost:8080
    E.g. if we browse to localhost:8080/www.example.org/index.html, the request would be 
    /www.example.org/index.html and the host would be localhost:8080. We change this HTTP 
    request to make the request /index.html and the host to www.example.org while keeping all
    other parameters in the HTTP header the same.

    returns a tuple of (new http request, new host)
    """

    # connection.sendall(data)
    # pprint.pprint(data)

    # find the outgoing address
    # make a socket on port 80 
    dest = data.decode().split(" ")[1][1:].split('/', 1)
    dest_addr = dest[0]
    #print("dest is", dest)

    dest_req = '/'+dest[1]

    new_data = data[:]
    data_split = str(new_data).split("\\r\\n", 2)

    req = data_split[0].split(" ")
    req_list = []
    req_list.append(req[0][2:] + " ")
    req_list.append(dest_req + " ")
    req_list.append(req[2] + "\\r\\n")

    new_req = ""
    for x in req_list:
        new_req += x

    data_split[0] = new_req
    data_host = "Host: " + dest_addr + "\\r\\n"
    data_split[1] = data_host

    forward_req = data_split[0] + data_split[1] + data_split[2]
    forward_req = forward_req[:-1] 
    return (forward_req, dest_addr)

def start_proxy(connection, client_address):
    print('connection from', client_address)
    data = connection.recv(1024)
    new_req, webserver = http_req_fixer_v2(data)
    if webserver == "favicon.ico":
        print(f"Server was favicon, skipping")
        return
    print(f"new_req {new_req}, \nwebserver {webserver}")


    forward_sock = socket.socket()
    forward_sock.connect((webserver, 80))
    encoded_req = new_req.encode()
    forward_sock.send(encoded_req)            

    while True:
        reply = forward_sock.recv(16)

        if len(reply) > 0:
            connection.send(reply)
        else:
            break
    
    forward_sock.close()
    connection.close()

if __name__ == "__main__":

    # Create a TCP/IP socket
    client_sock = socket.socket()

    # Bind the socket to the port
    error_count = 0
    port = 8080
    while True:
        try:
            client_sock.bind(('0.0.0.0', port))
            print("Made socket on port", port)
            break;
        except OSError:
            error_count += 1
            if error_count % 1000000 == 0:
                print("OSError")
            continue

    # Listen for incoming connections
    client_sock.listen()

    # in_socks, out_socks = [server_sock], []

    while True:
        # Wait for a connection
        print('waiting for a connection')
        connection, client_address = client_sock.accept()
        start_proxy(connection, client_address)

        # read_socs, write_socks, done_socks = select.select(in_socks, out_socks, in_socks)
        









        #     # Receive the data in small chunks and retransmit it
        #     while True:
        #         print("awaiting data")
        #         data = connection.recv(1024)
        #         # print('received {!r}'.format(data))
        #         if data:
        #             #print("data is: \n", data)
        #             forward_req, forward_addr = http_req_fixer_v2(data)
        #             if forward_addr == "favicon.ico":
        #                 break

        #             #forward_req = 'GET /~arnold HTTP/1.1\r\nHost: www.cs.toronto.edu\r\nConnection: keep-alive\r\nUpgrade-Insecure-Requests: 1\r\nUser-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.117 Safari/537.36\r\nSec-Fetch-User: ?1\r\nAccept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9\r\nSec-Fetch-Site: none\r\nSec-Fetch-Mode: navigate\r\nAccept-Encoding: utf-8\r\nAccept-Language: en-US,en;q=0.9\r\n\r\n'
        #             #forward_addr = 'www.cs.toronto.edu'

        #             print("fixed req: \n", forward_req)
        #             encoded_req = forward_req.encode()
        #             #print("forward req (encoded) is: \n", encoded_req)

        #             forward_sock = socket.socket()
        #             print(f'forward_addr is {forward_addr}')
        #             forward_sock.connect((forward_addr, 80))
        #             print("Forwarding request to", forward_addr)
        #             forward_sock.sendall(encoded_req)
        #             reply = b''
        #             while True:
        #                 response = forward_sock.recv(1024)
        #                 #print("Reply from", forward_addr, "was\n", reply.decode())
        #                 # if not response:
        #                 #     break

        #                 if len(response) > 0:
        #                     connection.send(response)
        #                 else:
        #                     break
                    

        #         else:
        #             print('no data from', client_address)
        #             break


        # finally:
        #     # Clean up the connection
        #     connection.close()