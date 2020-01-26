from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
import threading
import argparse
import re


# Important socket connection data
proxySocket = None


def createProxyListenerSocket():
    """Creates an initial listener TCP socket for the proxy"""
    global proxySocket
    parser = argparse.ArgumentParser(
        description="""This is a multi-client web proxy server.
        Default port number is 8000 unless supplied in commandline.""")
    parser.add_argument('--port', metavar='port', type=str,
                        nargs='?', default='8000')
    args = parser.parse_args()
    proxyAddress = 'localhost'
    proxySocket = socket(AF_INET, SOCK_STREAM)
    proxySocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    try:
        proxySocket.bind((proxyAddress, int(args.port)))
        print 'Running the proxy on:', proxySocket.getsockname()
        proxySocket.listen(1)
    except Exception as e:
        msg = "Restart the program. Failed to bind proxy on host: %s to port: %s because: %s" % (
            proxyAddress, args.port, e)
        raise SystemExit(msg)
    print 'Listening for clients...'


def sendResponse(responseCode, socket):
    # print "Sending response code: ", responseCode
    if (responseCode == 400):
        socket.send("HTTP/1.0 400 Bad Request\r\n")
        socket.close()
    if (responseCode == 501):
        socket.send("HTTP/1.0 501 Not Implemented\r\n")
        socket.close()
    if (responseCode == 200):
        socket.send("HTTP/1.0 200 OK\r\n")
    return


def processClientData(clientSocket):
    """Receives incoming byte data from the client and processes it.
    Specifically expects a valid HTTP request"""
    clientRequest = ""
    clientHeaders = []
    hostUrl = ""
    hostPort = 80
    hostUrlParam = "/"

    while True:
        incoming = clientSocket.recv(1024)
        if incoming == "\r\n":
            break
        clientRequest += incoming

    # print "Provided HTTP Request:\n ", clientRequest

    # Split request by new lines and check request line
    splitClientRequest = clientRequest.splitlines()
    requestPattern = re.compile(
        "^[A-Za-z]+ (?i)(http|ftp)://[^\s/$.?#].[^\s]* HTTP/1.0$")
    isValidRequestLine = requestPattern.match(splitClientRequest[0])
    if (not isValidRequestLine):
        # Send bad request to connection socket
        sendResponse(400, clientSocket)
        return False
    # print("Valid request line provided.")
    providedHttpMethod = splitClientRequest[0].partition(' ')[0]
    if (not "GET" == providedHttpMethod):
        sendResponse(501, clientSocket)
        return False
    # print "The provided http method: ", providedHttpMethod
    hostAbsUrl = splitClientRequest[0].split(' ')[1]
    # print "The provided absolute host url: ", hostAbsUrl

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
        # print("Valid header provided.")

    # Client request success
    # print "Sending successful reponse back to client"
    sendResponse(200, clientSocket)
    return clientHeaders, hostUrl, hostPort, hostUrlParam


def connectToRemoteServer(clientSocket, hostUrl, hostPort):
    """Connects to remote host server with data
    provided by the client"""
    print "Connecting to remote host..."
    # global serverSocket
    serverSocket = socket(AF_INET, SOCK_STREAM)
    print '\tBound to: (after socket call)', serverSocket.getsockname()
    serverSocket.connect((hostUrl, hostPort))
    print '\tBound to: (after connect call)', clientSocket.getsockname()
    return serverSocket


def forwardRequestToRemoteServer(url, param, headers, serverSocket):
    """Forwards client request to the remote host"""
    hostRequest = "GET " + param + " HTTP/1.0\nHost: " + \
        url + "\nConnection: close"

    # Attach any headers
    for x in range(len(headers)):
        hostRequest += "\n"
        if (not headers[x].lower() == "connection: keep-alive"):
            hostRequest += headers[x]
    hostRequest += "\r\n\r\n"
    # print "Sending client request to remote server..."
    print "Sending client request to remote server...\n", hostRequest
    serverSocket.send(hostRequest)
    hostResponse = ""
    temp = serverSocket.recv(1024)
    while (temp):
        hostResponse += temp
        temp = serverSocket.recv(1024)
    return hostResponse


def sendResponseToClient(clientSocket, hostResponse):
    """Send response from the remote server back to client through the proxy"""
    print 'Sending remote server response back to client...'
    clientSocket.sendall(hostResponse)


def onNewClient(clientSocket, connectionAddr):
    ip = connectionAddr[0]
    port = connectionAddr[1]
    print 'New client connection from IP: %s, and port: %s' % (ip, port)
    headers, hostUrl, hostPort, hostUrlParam = processClientData(
        clientSocket)
    serverSocket = connectToRemoteServer(clientSocket, hostUrl, hostPort)
    hostResponse = forwardRequestToRemoteServer(
        hostUrl, hostUrlParam, headers, serverSocket)
    sendResponseToClient(clientSocket, hostResponse)
    print 'Success. Closing connection to client at IP: %s, and port: %s' % (
        ip, port)
    clientSocket.close()


# 1 - Wait for connection
print "Use '--port [port]' command argument on initial run to set a custom proxy socket port."
createProxyListenerSocket()

# 2 - Accept multiple client connections
while True:
    try:
        client, ip = proxySocket.accept()
        threading._start_new_thread(onNewClient, (client, ip))
    except KeyboardInterrupt as e:
        raise SystemExit('Gracefully shutting down the server.')
    except Exception as e:
        print 'Program threw an exception: ', e
