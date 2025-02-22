from typing import Optional, Tuple, Union, Dict, Any
from cryptography.x509 import Certificate
from OpenSSL import crypto

import os
import subprocess

import logging

from models.utils import Model

try:
    import jks
    from OpenSSL import crypto

    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509 import Certificate
except:
    pass


class JKSConverter:
    def __init__(self, path: str, password: str, logger: Optional[logging.Logger] = None):
        self._logger = logger if logger else logging.getLogger(__name__)
        if path is None or not path:
            raise ValueError('"JKS Keystore path" can not be empty')
        if password is None or not password:
            raise ValueError('"SSL Keystore password" can not be empty')
        self._path = path
        self._password = password
        self._keystore = self._load_keystore()

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, new_path: str):
        if new_path is None or not new_path:
            raise ValueError('"SSL Keystore path" can not be empty')
        self._path = new_path
        self._keystore = self._load_keystore()

    @property
    def password(self) -> str:
        return self._password

    @password.setter
    def password(self, new_password: str):
        if new_password is None or not new_password:
            raise ValueError('"SSL password" can not be empty')
        self._password = new_password
        self._keystore = self._load_keystore()

    def _load_keystore(self):
        try:
            if not os.path.exists(self._path):
                raise IOError(f"Keystore file not found at {self._path}")

            with open(self._path, 'rb') as f:
                keystore_data = f.read()
        except IOError as e:
            self._logger.error(f"Error reading keystore file: {e}")
            raise

        try:
            p12 = pkcs12.load_key_and_certificates(
                keystore_data, self._password.encode(), backend=default_backend())
            self._logger.info("Keystore loaded successfully as PKCS12.")
            return p12
        except ValueError:
            self._logger.info("Failed to load as PKCS12, trying JKS/JCEKS.")

        try:
            keystore = jks.KeyStore.loads(keystore_data, self._password)
            self._logger.info("Keystore loaded successfully as JKS/JCEKS.")
            return keystore
        except jks.util.BadKeystoreFormatException as e:
            self._logger.error("Keystore file format is not supported.")
            raise ValueError("Keystore file format is not supported.") from e

    def extract_key_and_cert(self, alias: str) -> Tuple[crypto.PKey, crypto.X509]:
        if isinstance(self._keystore, tuple):
            private_key, cert, _ = self._keystore
            if private_key and cert:
                return private_key, cert
            else:
                raise ValueError("No private key or certificate found.")
        elif alias in self._keystore.private_keys:
            pk_entry = self._keystore.private_keys[alias]
            private_key = serialization.load_der_private_key(
                pk_entry.pkey, password=None, backend=default_backend())
            cert = crypto.load_certificate(crypto.FILETYPE_ASN1, pk_entry.cert_chain[0][1])
            return private_key, cert
        else:
            raise ValueError(f"No private key found for alias {alias}")

    def convert_to_pem(self, private_key: Union[crypto.PKey, rsa.RSAPrivateKey, bytes],
                       cert: Union[crypto.X509, Certificate]) -> Tuple[str, str]:
        private_key = self._load_private_key(private_key)
        cert = self._load_certificate(cert)
        private_key_pem = crypto.dump_privatekey(crypto.FILETYPE_PEM, private_key).decode('utf-8')
        cert_pem = crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode('utf-8')
        return private_key_pem, cert_pem

    def _load_private_key(self, private_key: Union[rsa.RSAPrivateKey, bytes]) -> crypto.PKey:
        if isinstance(private_key, rsa.RSAPrivateKey):
            key_der = private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption())
            return crypto.load_privatekey(crypto.FILETYPE_ASN1, key_der)
        elif isinstance(private_key, bytes):
            if b'-----BEGIN' in private_key:
                return crypto.load_privatekey(crypto.FILETYPE_PEM, private_key)
            else:
                return crypto.load_privatekey(crypto.FILETYPE_ASN1, private_key)
        else:
            raise TypeError("Unsupported private key type.")

    def _load_certificate(self, cert: Union[Certificate, bytes]) -> crypto.X509:
        if isinstance(cert, Certificate):
            cert_der = cert.public_bytes(serialization.Encoding.DER)
            return crypto.load_certificate(crypto.FILETYPE_ASN1, cert_der)
        elif isinstance(cert, bytes):
            return crypto.load_certificate(
                crypto.FILETYPE_PEM, cert) if b'-----BEGIN' in cert else crypto.load_certificate(
                crypto.FILETYPE_ASN1, cert)
        else:
            raise TypeError("Unsupported certificate type.")

    def convert_jks_to_pem(self, alias: str) -> Tuple[str, str]:
        try:
            private_key, cert = self.extract_key_and_cert(alias)
            return self.convert_to_pem(private_key, cert)
        except Exception as e:
            self._logger.error(f"Error converting JKS to PEM: {e}")
            raise


class CryptoHandler:
    def __init__(self, key: bytes, logger: Optional[logging.Logger] = None):
        self._logger = logger if logger else logging.getLogger(__name__)
        self._cipher = Fernet(key)

    def encrypt(self, data: str) -> str:
        """Encrypts the provided string data."""
        try:
            return self._cipher.encrypt(data.encode()).decode()
        except Exception as e:
            self._logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, data: str) -> str:
        """Decrypts the provided string data."""
        try:
            return self._cipher.decrypt(data.encode()).decode()
        except Exception as e:
            self._logger.error(f"Decryption failed: {e}")
            raise


class QueryConfig(Model):
    def __init__(self, sslrootcert: Optional[str] = None, storepassword: Optional[str] = None,
                 sslmode: str = "require", logger: Optional[logging.Logger] = None):

        self._sslrootcert = sslrootcert
        self._storepassword = storepassword
        self._sslmode = sslmode
        self._finalsslrootcert = None
        self._logger = logger if logger else logging.getLogger(__name__)

        if self._sslrootcert and self._sslrootcert.endswith('.jks'):
            self._converter = JKSConverter(path=self._sslrootcert, password=self._storepassword, logger=self._logger)
        else:
            self._converter = None

    @property
    def sslrootcert(self) -> Optional[str]:
        return self._sslrootcert

    @sslrootcert.setter
    def sslrootcert(self, sslrootcert: str):
        if sslrootcert is None or not sslrootcert:
            raise ValueError('"SSL root certificate" can not be empty')
        self._sslrootcert = sslrootcert

    @property
    def storepassword(self) -> Optional[str]:
        return self._storepassword

    @storepassword.setter
    def storepassword(self, storepassword: str):
        if storepassword is None or not storepassword:
            raise ValueError('"SSL Store password" can not be empty')
        self._storepassword = storepassword

    @property
    def sslmode(self) -> str:
        return self._sslmode

    @sslmode.setter
    def sslmode(self, sslmode: str):
        if sslmode is None or not sslmode:
            raise ValueError('"SSL mode" can not be empty')
        self._sslmode = sslmode

    def convert_jks_cert(self, alias: str):
        """Converts the JKS SSL certificate to PEM format and writes it to a file."""
        try:
            if self._converter:
                private_key, cert = self._converter.convert_jks_to_pem(alias)
                path = self._write_pem_file(cert)
                self._finalsslrootcert = path
        except Exception as e:
            self._logger.error(f"Error converting SSL certificate: {e}")
            raise

    def _write_pem_file(self, cert_pem: str) -> str:
        if not os.path.exists(self._sslrootcert):
            raise IOError(f"Could not find the cert at {self._sslrootcert}")

        if self._sslrootcert.endswith('.jks'):
            path = self._sslrootcert.replace('.jks', '.cert')
            try:
                with open(path, 'w') as file:
                    file.write(cert_pem)
                return path
            except IOError as e:
                self._logger.error(f"Error writing PEM file: {e}")
                raise
        else:
            return self._sslrootcert

    def build_db_connect_args(self) -> Dict[str, Any]:
        """Builds a dictionary of database connection arguments."""
        return {
            'protocol': 'https',
            # "requests_kwargs": {'verify': self._finalsslrootcert if self._finalsslrootcert else False},
            "requests_kwargs": {'verify': False},
        }


class KerberosConfig(Model):
    def __init__(self, krb5_config: str, principal: str, keytab_path: str,
                 kerberos_service_name: str = 'hive', logger: Optional[logging.Logger] = None):
        self._krb5_config = krb5_config
        self._principal = principal
        self._keytab_path = keytab_path
        self._kerberos_service_name = kerberos_service_name
        self._logger = logger if logger else logging.getLogger(__name__)
        self.acquire()

    @property
    def krb5_config(self) -> str:
        return self._krb5_config

    @krb5_config.setter
    def krb5_config(self, value: str):

        if value is None or not value:
            raise ValueError('"Kerberos krb5 config" can not be empty')
        self._krb5_config = value

    @property
    def principal(self) -> str:
        return self._principal

    @principal.setter
    def principal(self, value: str):
        if value is None or not value:
            raise ValueError('"Kerberos Principal" can not be empty')
        self._principal = value

    @property
    def keytab_path(self) -> str:
        return self._keytab_path

    @keytab_path.setter
    def keytab_path(self, value: str):
        if value is None or not value:
            raise ValueError('"Kerberos Keytab path" can not be empty')
        self._keytab_path = value

    @property
    def kerberos_service_name(self) -> str:
        return self._kerberos_service_name

    @kerberos_service_name.setter
    def kerberos_service_name(self, value: str):
        if value is None or not value:
            raise ValueError('"Kerberos service name" can not be empty')
        self._kerberos_service_name = value

    def acquire(self) -> bool:
        command = ['kinit', '-kt', self._keytab_path, self._principal]
        self._logger.info(f"Kerberos command: {' '.join(command)}")

        try:
            result = subprocess.run(
                command,
                universal_newlines=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )

            self._logger.info(f"Kerberos session acquire: Error Code - {result.returncode}")
            if result.returncode == 0:
                return True

            return False
        except subprocess.CalledProcessError as e:
            self._logger.error(f"Failed to acquire Kerberos session due to terminal error: {e}")
            raise
        except Exception as e:
            self._logger.error(f"Failed to acquire Kerberos session due to unknown error: {e}")
            raise

    def build_db_connect_args(self) -> Dict[str, str]:
        """Builds a dictionary of database connection arguments for Kerberos authentication."""
        return {
            'auth': 'KERBEROS',
            'kerberos_service_name': self._kerberos_service_name,
        }
