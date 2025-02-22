import logging

import paramiko
from sshtunnel import SSHTunnelForwarder, BaseSSHTunnelForwarderError
from paramiko.ssh_exception import SSHException, AuthenticationException, NoValidConnectionsError
import os

from models.utils import Model


class SSHConfig(Model):
    def __init__(self, host=None, port=22, username=None, password=None, auth_key=None):
        """
        Parameters:
            auth_key (optional): is the path to your PEM [PEM is a file format that may consist of a certificate
             (aka. public key), a private key or indeed both concatenated together.] if needed.
        """
        self.__host = host
        self.__port = port
        self.__username = username
        self.__auth_key = auth_key
        self.__password = password

    @property
    def host(self):
        return self.__host

    @host.setter
    def host(self, host):
        if host is None or not isinstance(host, str):
            raise ValueError("SSH Host must be a non-empty string.")
        self.__host = host

    @property
    def port(self):
        return self.__port

    @port.setter
    def port(self, port):
        if port is None or not isinstance(port, int):
            raise ValueError("SSH Port must be an integer.")
        self.__host = port

    @property
    def username(self):
        return self.__username

    @username.setter
    def username(self, username):
        if username is None or not isinstance(username, str):
            raise ValueError("SSH User must be a non-empty string.")
        self.__username = username

    @property
    def auth_key(self):
        return self.__auth_key

    @auth_key.setter
    def auth_key(self, auth_key):

        if auth_key is not None and not isinstance(auth_key, str):
            raise ValueError("SSH Private Key must be a string or None.")

        if not os.path.exists(auth_key):
            FileNotFoundError(f"Authentication file '{auth_key}' not found.")
        self.__auth_key = auth_key

    @property
    def password(self):
        return self.__password

    @password.setter
    def password(self, password):
        if password is not None and not isinstance(password, str):
            raise ValueError("SSH Password must be a string or None.")
        self.__password = password

    # Optional: Add a method to update configs using a dictionary
    def update_config(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise KeyError(f"Invalid SSH configuration key: {key}")


class SSHTunnelCommandExecutor:
    def __init__(self, config: SSHConfig, logger=None):
        self.__config = config
        self.tunnel = None
        self.client = None
        self._logger = logger if logger else logging.getLogger(__name__)

        self.auth_key = None
        self.load_rsa_key(self.__config.auth_key)

    @classmethod
    def build_connection_from_config(cls, config: SSHConfig, logger):
        # Create an SSHTunnelCommandExecutor object using an SSHConfig instance
        executor = cls(config, logger)
        return executor

    @classmethod
    def build_connection_from_dict(cls, config_dict: dict, logger):
        # Create an SSHConfig instance from the provided dictionary
        config = SSHConfig(**config_dict)

        # Create an SSHTunnelCommandExecutor object using the SSHConfig instance
        executor = cls(config, logger)
        return executor

    def load_rsa_key(self, key):
        try:
            if self.__config.auth_key:
                self.auth_key = paramiko.RSAKey.from_private_key_file(key)
                self._logger.info(f"RSA Key created successfully.")
        except Exception as e:
            self._logger.error(f"Error loading authentication file: {e}")
            raise Exception(f"Error loading authentication file: {e}")

    @property
    def config(self):
        return self.__config

    @config.setter
    def config(self, config: SSHConfig):
        if config is not None and not isinstance(config, SSHConfig):
            self._logger.error("Config must be an SSHConfig instance.")
            raise ValueError("Config must be an SSHConfig instance.")
        self.__config = config

    def open_tunnel(self, ):
        try:
            self.tunnel = SSHTunnelForwarder(
                (self.config.host, self.config.port),
                ssh_username=self.config.username,
                ssh_password=self.config.password,
                ssh_pkey=self.auth_key,
                remote_bind_address=('127.0.0.1', 22)
            )

            self.tunnel.start()
            self._logger.info(f"SSH Tunnel is open...")
        except BaseSSHTunnelForwarderError as e:
            self._logger.error(f"Error opening SSH tunnel: {e}")
            raise Exception(f"Error opening SSH tunnel: {e}")

    def connect_client(self):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._logger.info(f"SSH Client is created")

            if not self.tunnel or self.tunnel.closed:
                self.open_tunnel()

            self.client.connect(
                '127.0.0.1',
                port=self.tunnel.local_bind_port,
                username=self.config.username,
                password=self.config.password,
                pkey=self.auth_key
            )
            self._logger.info(f"SSH Client Connected...")
        except (AuthenticationException, SSHException, NoValidConnectionsError) as e:
            self._logger.error(f"Error connecting SSH client: {e}")
            raise Exception(f"Error connecting SSH client: {e}")

    def execute(self, command):
        if not self.client:
            self._logger.error("SSH Client not connected before execution.")
            raise Exception("SSH Client not connected before execution.")
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            return stdout.read().decode(), stderr.read().decode()

        except SSHException as e:
            self._logger.error(f"Error executing command: {e}")
            raise Exception(f"Error executing command: {e}")

    def close(self):
        if self.client:
            self.client.close()
            self._logger.info(f"Client closed successfully")
        if self.tunnel:
            self.tunnel.close()
            self._logger.info(f"Tunnel closed successfully")


def get_ssh_hook(config, logger=None):
    if isinstance(config, dict):
        conn = SSHTunnelCommandExecutor.build_connection_from_dict(config, logger=logger)
    elif isinstance(config, SSHConfig):
        conn = SSHTunnelCommandExecutor.build_connection_from_config(config, logger=logger)
    else:
        raise TypeError(f"The provided parameter '{type(config)}' is not supported to create a database connection.")

    return conn


def ssh_connect(config, logger=None):
    logger = logger if logger else logging.getLogger(__name__)
    try:
        logger.info(f"Creating SSH Hook.")
        ssh = get_ssh_hook(
            config=config.get('ssh', None),
            logger=logger
        )
        logger.info(f"Establishing SSH Tunnel.")
        ssh.open_tunnel()
    except Exception as e:
        logger.warning(f"Unable to open ssh tunnel. SSH is not supported or unwanted: {e}")


if __name__ == "__main__":
    pass
