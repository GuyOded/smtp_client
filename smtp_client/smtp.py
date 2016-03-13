"""
This file provides a low level interface for connecting
and
"""
import logging
import socket
import status
import ssl

LOG_NAME = "log.txt"
SMTP_PORT = 25
KILO = 1024
CRLF = "\r\n"
NULL = "\0"
DEBUG = True


class Smtp(object):
    def __init__(self, server_ip, port=SMTP_PORT):
        """
        initializes necessary members like the port the ip
        the socket that will be used and the log file, namely log.txt

        :type server_ip: str
        :param server_ip: The ip of the smtp server you wish to work
                          with
        :type port: int
        :param port: The port that will be used to connect to the server.
                     The default is the standard smtp port 25, but you
                     can choose a different one as 587 for example or 465.
        :return: None
        """
        logging.basicConfig(filename=LOG_NAME, level=logging.DEBUG)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.server_ip = server_ip
        self.port = port

    def connect(self):
        """
        establishes connection with the server

        :rtype: str
        :return: the response of the server

        :raises socket.timeout: if the socket has reached timeout on
                                the recv method
        :raises RuntimeError: if an unexpected status code was received
        """
        logging.info("Connecting to socket: {}:{}".format(self.server_ip, SMTP_PORT))
        self.sock.connect((self.server_ip, SMTP_PORT))

        logging.info("Connection successful. Waiting for service_ready response...")
        try:
            response = self.sock.recv(KILO)
        except socket.timeout as err:
            logging.error(err.message)
            raise

        logging.info("Received response, starting conversation\n\nS:{}".format(response))

        code = response[0:3]

        if code != str(status.READY):
            runtime_err = build_unexpected_status_error(code, status.READY)
            logging.error(runtime_err.message)
            raise runtime_err

        return response

    def ehlo(self):
        """
        Sends ehlo to the server and waits for its response.

        :rtype: str
        :return: the response of the server to the ehlo

        :raises socket.timeout: if the socket has reached timeout on
                                the recv method
        :raises RuntimeError: if an unexpected status code was received, expects 250
        """
        if DEBUG:
            logging.debug(repr("EHLO" + CRLF))
        logging.info("C:EHLO" + CRLF)

        self.sock.send("EHLO" + CRLF)

        try:
            response = self.sock.recv(KILO)
        except socket.timeout as err:
            logging.error(err.message)
            raise

        logging.info("S:{}".format(response))

        if not compare_status(status.OK, response):
            runtime_err = build_unexpected_status_error(status.OK, response[0:3])
            logging.error(runtime_err.message)
            raise runtime_err

        return response

    def starttls(self):
        """
        Requests a tls session from the server.
        :rtype: str
        :return: the response of the server

        :raises socket.timeout: if the socket has reached timeout on
                                the recv method
        :raises RuntimeError: If an unexpected status code was received, expects 220
        """
        starttls_command = "STARTTLS"

        if DEBUG:
            logging.debug(repr("{}{}".format(starttls_command, CRLF)))
        logging.info("C:{}{}".format(starttls_command, CRLF))

        self.sock.send(starttls_command + CRLF)

        try:
            response = self.sock.recv(KILO)
        except socket.timeout as err:
            logging.error(err.message)
            raise

        logging.info("S:" + response)

        if not compare_status(status.READY, response):
            runtime_err = build_unexpected_status_error(response[0:3], status.READY)
            logging.error(runtime_err.message)
            raise runtime_err

        self.sock = ssl.SSLSocket(self.sock)
        logging.info("CURRENTLY IN TLS MODE")
        return response

    def authenticate_plain(self, user, pass_phrase):
        """
        Authenticates given a username (or email address) and a password
        using the plain method.

        :param user: username or an email address
        :param pass_phrase: the password of the given user
        :return: a tuple of the following structure: success_rate(boolean), response(str)

        :raises socket.timeout: if the server didn't respond after 10 seconds

        """
        from base64 import b64encode
        plain = "PLAIN"

        packed_credentials = NULL + user + NULL + pass_phrase
        encoded_credentials = b64encode(packed_credentials)

        logging.debug("user: {}, password: {}".format(user, pass_phrase))

        command_line = build_auth_line(plain, encoded_credentials)

        if DEBUG:
            logging.debug(repr(command_line))
        logging.info("C:" + command_line)

        self.sock.send(command_line)

        try:
            response = self.sock.recv(KILO)
        except socket.timeout as timeout_err:
            logging.error(timeout_err.message)
            raise

        logging.info("S:" + response)

        if not compare_status(status.ACCEPTED, response):
            runtime_err = build_unexpected_status_error(response[0:3], status.READY)
            logging.error(runtime_err.message)
            return False, response

        return True, response

    def mail(self, sender_address, body=""):
        """
        sends a mail smtp command to the server

        :param sender_address: The value for the FROM parameter
        :param body: The value of the BODY param, for example 8BITMIME
        :return: the server's response
        :raises socket.timeout: if the socket has reached timeout on
                                the recv method
        :raises RuntimeError: If an unexpected status code was received, expects 250
        """
        mail_command = "MAIL"
        from_param = "FROM:"
        body_param = ""
        if body:
            body_param = "BODY=" + body

        sender_address = wrap_in_brackets(sender_address)
        from_param += sender_address
        command_line = "{} {} {}{}".format(mail_command, from_param, body_param, CRLF)

        if DEBUG:
            logging.debug(repr(command_line))
        logging.info("C:" + command_line)

        self.sock.send(command_line)

        try:
            response = self.sock.recv(KILO)
        except socket.timeout as timeout_err:
            logging.error(timeout_err.message)
            raise

        logging.info("S:" + response)

        if not compare_status(status.OK, response):
            runtime_err = build_unexpected_status_error(status.OK, response[0:3])
            logging.error(runtime_err.message)
            raise runtime_err

        return response

    def send_recipients(self, recipient):
        """
        Sends rcpt command to the server
        :param recipient: the recipient address (will be wrapped in <> if necessary)
        :return: response

        :raises socket.timeout: if the socket has reached timeout on
                                the recv method
        :raises RuntimeError: If an unexpected status code was received, expects 250
        """
        rcpt_command = "RCPT"
        to_param = "TO:"
        recipient = wrap_in_brackets(recipient)

        command_line = "{} {}{}{}".format(rcpt_command, to_param, recipient, CRLF)

        if DEBUG:
            logging.debug(repr(command_line))
        logging.info("C:" + command_line)

        self.sock.send(command_line)

        try:
            response = self.sock.recv(KILO)
        except socket.timeout as timeout_err:
            logging.error(timeout_err.message)
            raise

        logging.info("S:" + response)

        if not compare_status(status.OK, response):
            runtime_err = build_unexpected_status_error(status.OK, response[0:3])
            logging.error(runtime_err.message)
            raise runtime_err

        return response

    def send_body(self, body):
        """
        Sends raw data to the server, that is the body of the email itself
        """
        logging.info("SENDING DATA")
        self.sock.sendall(body)

    def initiate_data(self):
        """
        Asks the server to start sending data using the DATA commands
        :return: response
        :raises socket.timeout: if the socket has reached timeout on
                                the recv method
        :raises RuntimeError: If an unexpected status code was received, expects 250
        """
        data_command = "DATA\r\n"

        logging.info("C:" + data_command)
        self.sock.send(data_command)

        try:
            response = self.sock.recv(KILO)
        except socket.timeout as timeout_err:
            logging.error(timeout_err.message)
            raise

        logging.info("S:" + response)

        if not compare_status(status.START_DATA, response):
            runtime_err = build_unexpected_status_error(status.OK, response[0:3])
            logging.error(runtime_err.message)
            raise runtime_err

        return response

    def end_data(self):
        """
        Notifying the server that the email's body was fully sent.
        :return: response
        :raises socket.timeout: if the socket has reached timeout on
                                the recv method
        :raises RuntimeError: If an unexpected status code was received, expects 250
        """
        termination = CRLF + "." + CRLF

        if DEBUG:
            logging.debug(repr(termination))
        logging.info("C:" + termination)
        self.sock.send(termination)

        try:
            response = self.sock.recv(KILO)
        except socket.timeout as timeout_err:
            logging.error(timeout_err.message)
            raise

        logging.info("S:" + response)

        if not compare_status(status.OK, response):
            runtime_err = build_unexpected_status_error(status.OK, response[0:3])
            logging.error(runtime_err.message)
            raise runtime_err

        return response

    def quit_terminate(self):
        """
        Asks to quit the service and terminate the connection
        :return: response
        :raises socket.timeout: if the socket has reached timeout on
                                the recv method
        :raises RuntimeError: If an unexpected status code was received, expects 221
        """
        quit_command = "QUIT" + CRLF

        if DEBUG:
            logging.debug(repr(quit_command))
        logging.info("C:" + quit_command)
        self.sock.send(quit_command)

        try:
            response = self.sock.recv(KILO)
        except socket.timeout as timeout_err:
            logging.error(timeout_err.message)
            raise

        logging.info("S:" + response)

        if not compare_status(status.CLOSE_OK, response):
            runtime_err = build_unexpected_status_error(status.CLOSE_OK, response[0:3])
            logging.error(runtime_err.message)
            raise runtime_err

        self.sock.close()
        return response


def wrap_in_brackets(email_address):
    if email_address[0] != "<":
        email_address = "<" + email_address
    if email_address[-1] != ">":
        email_address += ">"

    return email_address


def build_auth_line(method, additional_param=""):
    auth_command = "AUTH"

    command_line = "{com} {method} {param}{crlf}".format(com=auth_command, method=method,
                                                         param=additional_param, crlf=CRLF)

    return command_line


def compare_status(code, response):
    return str(code) == response[0:3]


def build_unexpected_status_error(status_code, expected):
    return RuntimeError("Unexpected status code: {} instead of {}".format(status_code,
                                                                          expected))
