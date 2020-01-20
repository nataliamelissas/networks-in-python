from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
import re

# Important socket connection data
proxySocket = None
clientSocket = None
serverSocket = None

clientRequest = ""
hostUrl = ""
hostUrlParam = "/"
hostPort = 80
clientHeaders = []


def createProxyListenerSocket():
    global proxySocket
    """Creates an initial listener TCP socket for the proxy"""
    # Get port # and server address
    serverPort = ""
    while 1:
        try:
            serverPort = input("Specify a port #: ")
            break
        except Exception:
            continue
    serverAddress = 'localhost'
    proxySocket = socket(AF_INET, SOCK_STREAM)
    print 'Got a socket with fd:', proxySocket.fileno()
    # allow us to quickly reuse the port number...
    proxySocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    try:
        proxySocket.bind((serverAddress, serverPort))
    except Exception:
        print "Invalid port number. Restart the program and try again."
        exit()
    print 'Bound to:', proxySocket.getsockname()
    proxySocket.listen(1)


def listenForClient():
    """Listens for a single client connection"""
    print 'Listening for requests'
    global clientSocket
    clientSocket, addr = proxySocket.accept()
    print 'Accepted connection from:', clientSocket.getpeername(
    ), ' fd: ', clientSocket.fileno()


def sendResponse(responseCode, socket):
    print "Sending response code: ", responseCode
    if (responseCode == 400):
        socket.send("HTTP/1.0 400 Bad Request\r\n")
        socket.close()
    if (responseCode == 501):
        socket.send("HTTP/1.0 501 Not Implemented\r\n")
        socket.close()
    if (responseCode == 200):
        socket.send("HTTP/1.0 200 OK\r\n")

    return


def processClientData():
    """Receives incoming data 1024 bytes at a
    time from the client and processes it.
    Specifically expects a valid HTTP request"""
    global clientRequest
    clientRequest = ""
    while 1:
        incoming = clientSocket.recv(1024)
        if incoming == "\r\n":
            break
        clientRequest += incoming

    print "Provided HTTP Request:\n ", clientRequest

    # Split request by new lines and check request line
    splitClientRequest = clientRequest.splitlines()
    requestPattern = re.compile(
        "^[A-Za-z]+ (?i)(https?|ftp)://[^\s/$.?#].[^\s]* HTTP/1.0$")
    isValidRequestLine = requestPattern.match(splitClientRequest[0])
    if (not isValidRequestLine):
        # Send bad request to connection socket
        sendResponse(400, clientSocket)
        return False
    print("Valid request line provided.")
    providedHttpMethod = splitClientRequest[0].partition(' ')[0]
    if (not "GET" == providedHttpMethod):
        sendResponse(501, clientSocket)
        return False
    print "The provided http method: ", providedHttpMethod
    hostAbsUrl = splitClientRequest[0].split(' ')[1]
    print "The provided absolute host url: ", hostAbsUrl
    global hostUrl
    global hostPort
    global hostUrlParam
    # Extract hostUrl, port, and path from the absolute url
    hostUrl = hostAbsUrl[7:]  # 7 = length of "http://"
    colonPos = hostUrl.find(":")
    if (colonPos != -1):
        hostUrlParam = hostUrl[colonPos:]
        slashPos = hostUrlParam.find("/")
        if (slashPos != -1):
            hostPort = int(hostUrlParam[1:slashPos])
            hostUrlParam = hostUrlParam[slashPos:]
        else:
            hostPort = int(hostUrlParam[1:])
        hostUrl = hostUrl[:colonPos]
    slashPos = hostUrl.find("/")
    if (slashPos != -1):
        hostUrlParam = hostUrl[slashPos:]
        hostUrl = hostUrl[:slashPos]
    print "The provided host url: ", hostUrl
    print "The host port number:", hostPort
    print "The provided url path:", hostUrlParam
    # Check headers (if any)
    headerPattern = re.compile("^[\w-]+: .*$")
    for i in range(len(splitClientRequest)):
        if (i == 0):
            continue
        if (splitClientRequest[i] == "\r\n"):
            continue
        isValidHeader = headerPattern.match(splitClientRequest[i])
        if (not isValidHeader):
            sendResponse(400, clientSocket)
            return False
        clientHeaders.append(splitClientRequest[i])
        print("Valid header provided.")

    # Client request success
    print "Sending success reponse back to client"
    sendResponse(200, clientSocket)
    return True


def connectToHost():
    """Connects to remote host server with data
    provided by the client"""
    print "Connecting to remote host..."
    global serverSocket
    hostAddress = hostUrl
    serverSocket = socket(AF_INET, SOCK_STREAM)
    print 'Bound to: (after socket call)', serverSocket.getsockname()
    serverSocket.connect((hostAddress, hostPort))
    print 'Bound to: (after connect call)', clientSocket.getsockname()


def forwardRequestToHost():
    """Forwards client request to the remote host"""
    # Form http request line
    hostRequest = "GET " + hostUrlParam + " HTTP/1.0\nHost: " + \
        hostUrl + "\nConnection: close"

    # Attach any headers
    for x in range(len(clientHeaders)):
        hostRequest += "\n"
        if (not clientHeaders[x].lower() == "connection: keep-alive"):
            hostRequest += clientHeaders[x]
    hostRequest += "\r\n\r\n"

    print "Request to host:\n", hostRequest
    serverSocket.send(hostRequest)
    hostResponse = ""
    temp = serverSocket.recv(1024)
    while (temp):
        hostResponse += temp
        temp = serverSocket.recv(1024)

    print 'From host:', hostResponse
    print 'Sending host response to client via proxy...'
    clientSocket.send(hostResponse)


# 1 - Wait for connection
createProxyListenerSocket()

while 1:
    # 2 - Wait for client connection
    listenForClient()

    # 3 - Process data from client
    connected = processClientData()

    # 4 - Connect with remote host
    if (connected):
        connectToHost()

        # 5 - Request remote host webpage
        forwardRequestToHost()

    # Close connection with client
    clientSocket.close()
