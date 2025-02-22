import logging
import os
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


class MultipurposeLogger(logging.Logger):
    # TODO: this code is open for improvement
    #   - add properties
    #   - add the logger customization from a logging file

    # Pre-compile the regex pattern
    _valid_name_pattern = re.compile("^[A-Za-z0-9_.-]+$")

    def __init__(self, name: str, path: str = 'logs', level: int = None, create=False):
        self.__name = self.__set_name(name)

        self.__level = level if level else logging.NOTSET
        super().__init__(self.__name, self.__level)

        self.__path = self.__set_path(path, create=create)

        self.__log_file = None
        self.__extra_info = None

        self.initialize_logger_handler()

    def get_name(self):
        return self.__name

    def get_log_file(self):
        return self.__log_file

    def __set_name(self, name):
        """
        Set the logger's name with validation.

        Parameters:
        name (str): The name to be assigned to the logger.

        Raises:
        ValueError: If the name does not matches the required pattern.
        """
        if not MultipurposeLogger._valid_name_pattern.match(name):
            raise ValueError("Name must contain only alphanumeric characters, underscores, hyphens, and periods.")
        return name

    def get_path(self):
        return self.__path

    def __set_path(self, path, create=False):
        """
        Set the path for the logger and optionally create it if it doesn't exist.

        Parameters:
        path (str): The path to be set for logging.
        create (bool): Whether to create the path if it doesn't exist.

        Raises:
        FileNotFoundError: If the path doesn't exist and 'create' is False.
        OSError: For issues related to creating the directory.
        """
        try:
            if not os.path.exists(path) and create:
                os.makedirs(path, exist_ok=True)
            elif not os.path.exists(path):
                raise FileNotFoundError(f"The given path '{path}' does not exist.")
            return path
        except OSError as e:
            raise OSError(f"Error creating directory '{path}': {e}")
        except Exception as e:
            print(f"An unexpected error occurred while setting the path '{path}': {e}")
            raise

    def check_and_reinitialize_log_file(self):
        """
        Check if the log file exists, and reinitialize if it does not.
        Mainly, This methods aim to solve the problem where the log file is removed during the runtime.
        """
        log_file_exists = os.path.exists(self.__log_file)
        if not log_file_exists:
            print("Log file was missing... Reinitializing log file and file handler.")
            self.warning("Log file was missing... Reinitializing log file and file handler.")
            self.initialize_logger_handler()

    def initialize_logger_handler(self, log_level: int = logging.NOTSET, max_bytes: int = 10485760,
                                  backup_count: int = 1000, rotate_time: str = None):
        """
        Initialize the logger with specific settings.

        Parameters:
            log_level (int): the logging level for the file handler
            max_bytes (int): Maximum size in bytes for RotatingFileHandler. 10 MB by default.
            backup_count (int): Number of retention files to keep. 1000 file by default.
            rotate_time (str): Rotation interval for TimedRotatingFileHandler (e.g., 'midnight', 'W0', 'D').

        Raises:
            IOError: For issues related to file handling during logger setup.
        """
        try:
            formatter = logging.Formatter(
                '[%(asctime)s] || %(levelname)s :- %(message)s'
            )
            self.__log_file = os.path.join(self.__path, f'{self.__name}_{datetime.now():%Y%m%d_%H%M%S%f}.log')
            if rotate_time:
                file_handler = TimedRotatingFileHandler(
                    filename=self.__log_file,
                    when=rotate_time,
                    backupCount=backup_count,
                    encoding='utf-8',  # Optional: Specify encoding if needed
                )
                file_handler.suffix = "%Y%m%d_%H%M%S%f.log"
            else:
                file_handler = RotatingFileHandler(
                    filename=self.__log_file,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding='utf-8',
                )

            print(f"Log File: {self.__log_file}")
            if self.__level == logging.NOTSET and log_level is not None:
                file_handler.setLevel(log_level)
                self.setLevel(log_level)
            else:
                file_handler.setLevel(self.__level)
                self.setLevel(self.__level)

            file_handler.setFormatter(formatter)
            self.addHandler(file_handler)
        except IOError as e:
            raise IOError(f"Error initializing file handler for logger: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while initializing file handler for logger: {e}")
            raise

    def info(self, msg, xtra=None, *args, **kwargs):
        extra_info = xtra if xtra is not None else self.__extra_info
        super().info(msg, *args, extra=extra_info, **kwargs)
        print(msg)

    def debug(self, msg, xtra=None, *args, **kwargs):
        extra_info = xtra if xtra is not None else self.__extra_info
        super().debug(msg, *args, extra=extra_info, **kwargs)
        print(msg)

    def warning(self, msg, xtra=None, *args, **kwargs):
        extra_info = xtra if xtra is not None else self.__extra_info
        super().warning(msg, *args, extra=extra_info, **kwargs)
        print(msg)

    def error(self, msg, xtra=None, *args, **kwargs):
        extra_info = xtra if xtra is not None else self.__extra_info
        super().error(msg, *args, extra=extra_info, **kwargs)
        print(msg)

    @staticmethod
    def setup_logger(name: str, level=logging.INFO, file_path: str = None):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File Handler
        if file_path:
            file_handler = logging.FileHandler(file_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger


if __name__ == "__main__":
    pass
