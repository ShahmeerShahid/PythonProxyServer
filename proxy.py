import socket
import sys, pprint, select, os, time


def http_req_fixer_v2(data):
	data = data.decode('utf-8')
	space_split_data = data.split(' ')
	req_type = space_split_data[0]
	# print(f"data.split: {space_split_data}")
	url = space_split_data[1]
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

	return fixed_req, host, url

def write_to_cache(reply, url):
	url = url.replace("/", ",")
	with open(f"{url}.txt", "ab") as o:
		o.write(reply)
	print(f"Wrote {url} to cache")
	return len(reply)

def read_from_cache(url):
	url = url.replace("/", ",")
	try:
		with open(f"{url}.txt", "rb") as o:
			if cache_valid(cache_timer, url):
				reply = o.read()
			else:
				print(f"Found {url} in cache but was expired, deleting")
				return b""
	except IOError as e:
		print(f"{url} not found in cache")
		return b"" # file doesn't exist
	print(f"Found {url} in cache")
	return reply


def cache_valid(cache_timer, url):
	url = url.replace("/", ",")
	try:
		modification_time = os.path.getmtime(url)
	except OSError:
		return False # file DNE
	
	if cache_timer <= (time.time() - modification_time):
		os.remove(url)
		return False
	return True



def start_proxy(connection, client_address):
	print('\nConnection from', client_address)
	data = connection.recv(8192)
	if len(data) == 0:
		return
	new_req, webserver = http_req_fixer_v2(data)
	if webserver.split("/")[-1] == "favicon.ico":
		print(f"Server was favicon, skipping")
		return
	print(f"new_req: \n{new_req}")


	forward_sock = socket.socket()
	forward_sock.connect((webserver, 80))
	encoded_req = new_req.encode()
	forward_sock.send(encoded_req)            
	
	response = b''
	while True:
		reply = forward_sock.recv(64000) # 64k buffer size

		if len(reply) > 0:
			# with open('out.txt' 'w') as f:
			print("Received reply of length " + str(len(reply)))
			print(str(reply))
			# response += reply
			connection.sendall(reply)
		else:
			break
	# connection.sendall(response)
	forward_sock.close()
	connection.close()


if __name__ == "__main__":
	# parse cache expiry timer
	cache_timer = sys.argv[1]

	# Create a TCP/IP socket
	server_sock = socket.socket()

	# Bind the socket to the port
	error_count = 0
	port = 8080
	while True:
		try:
			server_sock.bind(('127.0.0.1', port))
			print("Made socket on port", port)
			break
		except OSError:
			error_count += 1
			if error_count % 1000000 == 0:
				print("OSError")
			continue

	# Listen for incoming connections
	server_sock.listen()

	# in_socks, out_socks = [server_sock], []

	dest_client_dict = {} # dest_socket: (client_socket, URL e.g. 'www.example.com/index.html')
	cache = [] # urls
	input_socks = [server_sock]
	client_socks = []
	num_clients, num_inputs = 0, 0

	while True:
		# Wait for a connection
		# connection, client_address = server_sock.accept()
		# start_proxy(connection, client_address)

		read_socks, _, error_socks = select.select(input_socks, [], input_socks)

		for s in read_socks:
			if s is server_sock:
				new_client, _ = s.accept()
				new_client.settimeout(20)
				input_socks.append(new_client)
				client_socks.append(new_client)
				num_clients += 1
				num_inputs += 1
				# print("Established connection with new client")

			elif s in client_socks:
				# HTTP request came in from client
				try:
					data = s.recv(8192)
				except ConnectionResetError:
					client_socks.remove(s)
					input_socks.remove(s)
					num_inputs -= 1
					num_clients -= 1
					continue
				if len(data) == 0:
					s.close()
					client_socks.remove(s)
					input_socks.remove(s)
					num_inputs -= 1
					num_clients -= 1
					continue
				
				new_req, webserver, url = http_req_fixer_v2(data)
				# check if url is in cache
				reply = read_from_cache(url)
				if reply != b"":
					# in cache, send back cached web page
					s.sendall(reply)
					input_socks.remove(s)
					client_socks.remove(s)
					s.close()
				else:
					# not in cache/entry expired
					if webserver.split("/")[-1] == "favicon.ico":
						continue # Skip favicon requests
					forward_sock = socket.socket()
					try:
						forward_sock.connect((webserver, 80))
					except TimeoutError:
						continue
					dest_client_dict[forward_sock] = (s, url)
					input_socks.append(forward_sock)
					num_inputs += 1
					encoded_req = new_req.encode()
					forward_sock.sendall(encoded_req)

			else: # must be a response from a server
				try:
					reply = s.recv(8192)
				except ConnectionResetError:
					input_socks.remove(s)
					num_inputs -= 1
					dest_client_dict.pop(s)
					continue
				if len(reply) == 0:
					input_socks.remove(s)
					s.close()
					num_inputs -= 1
					dest_client_dict.pop(s)
					continue

				client_sock, url = dest_client_dict[s]
				cache.append(url)
				write_to_cache(reply, url) 
				client_sock.sendall(reply)
	
		for e in error_socks:
			try:
				e.shutdown()
			except ConnectionResetError:
				continue
	
	print(str(num_clients)+" unique clients, "+str(num_inputs)+" total sockets.", end='\r')