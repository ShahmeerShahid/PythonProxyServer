# PythonProxyServer
An HTTP proxy server that caches webpages and injects HTML into packets to display information about caching. The server is built only using Python sockets (ie without the use of ```requests``` or any other library).

# Usage
To start the server, supply an expiration time in seconds for cached webpages:
```python
> python3 proxy.py 120
```
This will start a proxy server on ```localhost:8888``` with a cache expiration time of 2 minutes. Now we can navigate to ```HTTP``` websites through our proxy e.g. ```localhost:8888/www.example.org/```

# Caching example
Navigating to www.example.org regularly will give us:

![example.org normal](https://i.imgur.com/p54L6Yb.png)

The first time we navigate to www.example.org through our proxy we get:
![example.org fresh](https://i.imgur.com/LyiHjXe.png)

If we refresh the page, we instead get:
![example.org cached](https://i.imgur.com/Ie7DxF4.png)

This is because the webpage is cached for however much time we set. This speeds up navigation but sacrifices the currentness of the webpage.

# Why can't we use HTTPS?
This proxy server injects HTML into responses from the destination server. In order to do this, we require the response to be in plaintext. In the HTTPS protocol, communication between clients and servers are encrypted after the initial handshake where a public/private key pair is established.
