import socket
import sys, select, os, time


def http_req_fixer(data):
	data = data.decode('utf-8')
	space_split_data = data.split(' ')
	req_type = space_split_data[0]
	url = space_split_data[1]
	host  = url.split('/')[1]
	
	files = ''
	location = url.split('/')
	for f in range(2,len(location)): #to grab just the path of the files requested from the server 
		files = files + '/' + location[f]
	if files == '':
		files = url
	# if files == "/":
	# 	files = " "
	
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
		elif 'Connection' in data[line_index]:
			fixed_req = fixed_req + 'Connection: close'
		else:
			#if line doesn't need to be changed, add original
			fixed_req = fixed_req + data[line_index]
		if line_index != 15:
			#to not add a third carriage return at the end of the request
			fixed_req = fixed_req + '\r\n'

	return fixed_req, host, url

def inject_html(injection, html):
	# injects injection into <body> in HTML
	# HTML is encoded
	text = [b'<p style="z-index:9999; position:fixed; top:20px; left:20px; width:200px;height:100px; background-color:yellow; padding:10px; font-weight:bold;">', b'</p>']
	
	if b"<html" not in html:
		return html

	injection_length = len(text[0]) + len(injection.encode()) + len(text[1])
	injected_html = b""
	html = html.split(b"\r\n")
	for i in html: #adjust content-length header to resolve truncation 
		if b"Content-Length: " in i:
			x = i.split(b"Content-Length: ")
			content_length = int(x[1])
			new_length = content_length + injection_length
			injected_html += b"Content-Length: " + str(new_length).encode() + b"\r\n"
		else:
			injected_html += i + b"\r\n"

	l = injected_html.split(b"<body", 1)
	x = l[1].split(b">", 1)
	return l[0] + b"<body" + x[0] + b">" + text[0] + injection.encode() + text[1] + x[1]


def write_to_cache(reply, url):
	url = url.replace("/", " ")
	with open(f"{url}", "wb") as o:
		o.write(reply)
	# Wrote URL to cache
	return len(reply)

def read_from_cache(url):
	url = url.replace("/", " ")
	try:
		with open(f"{url}", "rb") as o:
			if cache_valid(cache_timer, url):
				reply = o.read()
			else:
				# Found URL in cache, but was expired, deleting
				return b""
	except IOError:
		# URL not found in cache
		return b"" # file doesn't exist

	# Found URL in cache
	return reply


def cache_valid(cache_timer, url):
	url = url.replace("/", " ")
	modification_time = os.path.getmtime(url)
	if cache_timer <= (time.time() - modification_time):
		os.remove(url)
		return False
	return True

def start_proxy(cache_timer):
	# Create a TCP/IP socket
	server_sock = socket.socket()

	# Bind the socket to the port
	port = 8888
	server_sock.bind(('127.0.0.1', port))
	print("Made socket on port", port)

	# Listen for incoming connections
	server_sock.listen()

	dest_client_dict = {} # dest_socket: (client_socket, URL e.g. 'www.example.com/index.html')
	dest_response_dict = {} # allows us to collect the response from the server to inject HTML
	input_socks = [server_sock]
	client_socks = []

	while True:
		# Wait for a connection

		read_socks, _, error_socks = select.select(input_socks, [], input_socks)

		for s in read_socks:
			if s is server_sock:
				new_client, _ = s.accept()
				new_client.settimeout(60)
				input_socks.append(new_client)
				client_socks.append(new_client)

			elif s in client_socks:
				# HTTP request came in from client
				try:
					data = s.recv(8192)
				except ConnectionResetError:
					# socket has been closed
					client_socks.remove(s)
					input_socks.remove(s)
					continue
				if len(data) == 0:
					# no more data from client
					s.close()
					client_socks.remove(s)
					input_socks.remove(s)
					continue
				
				new_req, webserver, url = http_req_fixer(data)

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
					dest_response_dict[forward_sock] = b""
					input_socks.append(forward_sock)
					encoded_req = new_req.encode()
					forward_sock.sendall(encoded_req)

			else: # must be a response from a server
				try:
					reply = s.recv(8192)
				except ConnectionResetError:
					input_socks.remove(s)
					dest_client_dict.pop(s)
					continue
				if len(reply) == 0:
					# no more data coming in from server, we can send back collected response to client
					client_sock, url = dest_client_dict[s]
					# inject HTML to add the yellow box
					try: 
						time_stamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
						fresh_msg = f"FRESH VERSION AT: {time_stamp}"
						cache_msg = f"CACHED VERSION AS OF: {time_stamp}"
						client_sock.sendall(inject_html(fresh_msg, dest_response_dict[s]))
						write_to_cache(inject_html(cache_msg, dest_response_dict[s]), url)

					except OSError as e:
						print("Tried writing to a client that already disconnected")

					finally:
						input_socks.remove(s)
						s.close()
						dest_response_dict.pop(s)
						dest_client_dict.pop(s)
					continue
				
				dest_response_dict[s] += reply
	
		for e in error_socks:
			try:
				e.shutdown()
			except ConnectionResetError:
				continue


if __name__ == "__main__":
	# parse cache expiry timer
	cache_timer = int(sys.argv[1])
	start_proxy(cache_timer)