import glob
import json, os
import logging
import shutil
import socket
import subprocess

from datetime import datetime, timedelta
from enum import Enum


def sort_dict_keys_with_symbols(data: dict):
    # Extract and group keys based on the same grouping logic
    keys = list(data.keys())
    groups = []
    i = 0
    while i < len(keys):
        if keys[i].startswith('#') or keys[i].startswith('@'):
            if i + 1 < len(keys) and not keys[i + 1].startswith(('#', '@')):
                groups.append([keys[i], keys[i + 1]])
                i += 2
            else:
                groups.append([keys[i]])
                i += 1
        else:
            groups.append([keys[i]])
            i += 1

    # Sort groups with keys starting with `#` or `@`
    sorted_groups = sorted(
        [g for g in groups if g[0].startswith(('#', '@'))],
        key=lambda x: x[0]
    ) + [g for g in groups if not g[0].startswith(('#', '@'))]

    # Flatten the sorted groups back into a list
    sorted_keys = [item for group in sorted_groups for item in group]

    # Recreate the dictionary with sorted keys
    sorted_dict = {key: data[key] for key in sorted_keys}
    return sorted_dict


def sort_symbols_maintain_location(lst: list[str]):
    # Extract items starting with # or @
    symbol_items = [item for item in lst if item.startswith('#') or item.startswith('@')]
    # Sort the extracted items
    sorted_symbols = sorted(symbol_items)

    # Replace the original positions with the sorted items
    result = []
    symbol_index = 0
    for item in lst:
        if item.startswith('#') or item.startswith('@'):
            result.append(sorted_symbols[symbol_index])
            symbol_index += 1
        else:
            result.append(item)
    return result


def add_one_day_to_date(yyyymmdd: str) -> str:
    # Convert integer YYYYMMDD to a datetime object
    date = datetime.strptime(str(yyyymmdd), "%Y%m%d")

    # Add one day to the date
    new_date = date + timedelta(days=1)

    # Convert the new date back to integer YYYYMMDD
    return new_date.strftime("%Y%m%d")


def error_handler(func, logger=None):
    """Decorator to handle exceptions and log errors."""
    logger = logger if logger else logging.getLogger(__name__)

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Error in {func.__name__}: {e}")
            raise e

    return wrapper


def is_empty(name, value):
    if isinstance(value, str) and value.strip() == '':
        raise ValueError(f"{name} cannot be None or empty.")

    if not value:
        raise ValueError(f"{name} cannot be None or empty.")

    return True


def is_type(value, dtype):
    if not isinstance(value, dtype) and isinstance(dtype, Enum):
        return False
    elif not isinstance(value, dtype):
        return False
    else:
        return True


def is_valid_path(path, create=False):
    # Check if the file exists
    if not os.path.exists(path):
        if create:
            os.mkdir(path)
            return True
        return False

    # Check if the file is not empty
    # if os.path.getsize(path) == 0:
    #     return False

    # if file:
    #     # Check if it is a regular file
    #     if not os.path.isfile(path):
    #         return False

    # If all checks pass, the file is valid
    return True


def is_valid_ip_format(ip):
    """
    Check if the provided string is a valid IPv4 address.
    """
    try:
        socket.inet_pton(socket.AF_INET, ip)
        return True
    except socket.error:
        return False


def is_dict_field_missing(value, field_name):
    """Check if a specific field in a value is None or empty."""
    return value.get(field_name) in [None, "", {}, [], ()]


def get_days_between_dates(date1, date2):
    # Convert the date strings to datetime objects
    datetime1 = datetime.strptime(date1, "%Y%m%d").date()
    datetime2 = datetime.strptime(date2, "%Y%m%d").date()

    # Calculate the number of days between the two dates
    num_days = abs((datetime2 - datetime1).days)
    return num_days


def find_base_directory():
    current_file = os.path.abspath(__file__)
    base_directory = os.path.dirname(current_file)
    return base_directory


def load_json_file(path):
    """Return a dictionary structured exactly [dumped] as the JSON file."""
    try:
        with open(path, encoding='utf-8') as file:
            loaded_dict = json.load(file)
        return loaded_dict
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Error: {e}. File not found at path: {path}")
    except json.JSONDecodeError as e:
        raise Exception(f"Error: {e}. Unable to decode JSON file at path: {path}")
    except Exception as e:
        raise Exception(f"Error: {e}. An unexpected error occurred while loading JSON file at path: {path}")


def load_sql_file_queries(path):
    """
    Return a list of queries loaded from the given SQL file and separated by ';'.

    Args:
    - path (str): The path to the SQL file.

    Returns:
    - list: List of SQL queries.
    """
    try:
        with open(path, 'r', encoding='utf-8') as file:
            # Read the file and split queries using ';' while filtering out empty strings
            queries = [query.strip() for query in file.read().split(';') if query.strip()]

        return queries

    except FileNotFoundError as file_not_found_error:
        raise FileNotFoundError(f"Error: {file_not_found_error}. File not found at path: {path}")

    except Exception as e:
        raise Exception(f"Error: {e}. An unexpected error occurred while loading SQL file at path: {path}")

def convert_to_json(items):
    x = json.dumps(items)
    print(x)
