class DBConfigError(Exception):
    """Custom exception for DBConfig errors."""
    pass


# Custom Exceptions
class DBConnectionError(Exception):
    """Raised when there is an error with the database connection."""
    pass


class DBQueryError(Exception):
    """Raised when there is an error executing a query."""
    pass


class DBInsertError(Exception):
    """Raised when there is an error inserting data."""
    pass
