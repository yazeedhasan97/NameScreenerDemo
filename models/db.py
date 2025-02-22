import os
import logging
import time

import pandas as pd
import pickle as pkl
from typing import Optional, Dict, Any, Literal
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.engine.url import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from models.erorrs import DBConfigError, DBConnectionError, DBQueryError, DBInsertError

from models.protcs import QueryConfig, KerberosConfig
from models.utils import Model

import urllib3

# Suppress urllib3 warnings
# urllib3.disable_warnings(urllib3.exceptions.SubjectAltNameWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class DBConfig(Model):
    def __init__(self, delicate: str = 'postgresql', host: str = 'localhost', port: int = 5432,
                 database: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None,
                 query: Optional[Dict] = None, stream: bool = False, echo: bool = False,
                 kerberos: Optional[Dict] = None, logger: Optional[logging.Logger] = None,
                 pool_size: Optional[int] = 15, max_overflow: Optional[int] = 5,
                 pool_timeout: Optional[int] = 15, pool_recycle: Optional[int] = 1200, ):
        self._logger = logger or logging.getLogger(__name__)

        self._delicate = delicate
        self._host = host
        self._port = port
        self._database = database
        self._username = username
        self._password = password
        self._stream = stream
        self._echo = echo
        self._query = QueryConfig(**query) if query else None

        # Connection pooling configuration
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._pool_timeout = pool_timeout
        self._pool_recycle = pool_recycle

        if self._query:
            self._query.convert_jks_cert(self._username)

        self._kerberos = KerberosConfig(**kerberos) if kerberos else None
        if self._kerberos:
            self._log_kerberos_config()

    @property
    def pool_size(self) -> int:
        return self._pool_size

    @property
    def max_overflow(self) -> int:
        return self._max_overflow

    @property
    def pool_timeout(self) -> int:
        return self._pool_timeout

    @property
    def pool_recycle(self) -> int:
        return self._pool_recycle

    def _log_kerberos_config(self):
        self._logger.info(
            f"Kerberos Config: krb5_config={self._kerberos.krb5_config}, "
            f"principal={self._kerberos.principal}, keytab_path={self._kerberos.keytab_path}, "
            f"kerberos_service_name={self._kerberos.kerberos_service_name}"
        )

    def _validate_input(self, value: Any, attr_name: str, data_type: type, nullable: bool = False) -> None:
        if value is None and not nullable:
            self._logger.error(f"{attr_name} cannot be empty or None.")
            raise DBConfigError(f"{attr_name} cannot be empty or None.")
        if not isinstance(value, data_type):
            self._logger.error(f"{attr_name} must be of type {data_type.__name__}.")
            raise DBConfigError(f"{attr_name} must be of type {data_type.__name__}.")

    @property
    def kerberos(self) -> Optional[KerberosConfig]:
        return self._kerberos

    @kerberos.setter
    def kerberos(self, kerberos: dict) -> None:
        try:
            self._kerberos = KerberosConfig(**kerberos)
        except TypeError as e:
            self._logger.error(f"Incorrect Kerberos configuration: {str(e)}")
            raise ValueError(f"Incorrect Kerberos configuration: {str(e)}")

    @property
    def query(self) -> Optional[QueryConfig]:
        return self._query

    @query.setter
    def query(self, query: dict) -> None:
        try:
            self._query = QueryConfig(**query) if query else None
            if self._query:
                self._query.convert_jks_cert(self._username)
        except TypeError as e:
            self._logger.error(f"Incorrect Query configuration: {str(e)}")
            raise ValueError(f"Incorrect Query configuration: {str(e)}")

    @property
    def delicate(self) -> str:
        return self._delicate

    @delicate.setter
    def delicate(self, delicate: str) -> None:
        self._validate_input(delicate, 'delicate', str)
        self._delicate = delicate

    @property
    def host(self) -> str:
        return self._host

    @host.setter
    def host(self, host: str) -> None:
        self._validate_input(host, 'host', str)
        self._host = host

    @property
    def port(self) -> int:
        return self._port

    @port.setter
    def port(self, port: int) -> None:
        self._validate_input(port, 'port', int, nullable=True)
        if not (0 < port < 65536):
            self._logger.error("Port must be an integer between 1 and 65535.")
            raise ValueError("Port must be an integer between 1 and 65535.")
        self._port = port

    @property
    def database(self) -> Optional[str]:
        return self._database

    @database.setter
    def database(self, database: Optional[str]) -> None:
        self._validate_input(database, 'database', str, nullable=True)
        self._database = database

    @property
    def username(self) -> Optional[str]:
        return self._username

    @username.setter
    def username(self, username: Optional[str]) -> None:
        self._validate_input(username, 'username', str, nullable=True)
        self._username = username

    @property
    def password(self) -> Optional[str]:
        return self._password

    @password.setter
    def password(self, password: Optional[str]) -> None:
        self._validate_input(password, 'password', str, nullable=True)
        self._password = password

    @property
    def stream(self) -> bool:
        return self._stream

    @stream.setter
    def stream(self, stream: bool) -> None:
        self._validate_input(stream, 'stream', bool)
        self._stream = stream

    @property
    def echo(self) -> bool:
        return self._echo

    @echo.setter
    def echo(self, echo: bool) -> None:
        self._validate_input(echo, 'echo', bool)
        self._echo = echo


class DBConnection:
    def __init__(self, config: DBConfig, logger: Optional[logging.Logger] = None, ) -> None:
        self.__engine = None
        self.__inspector = None
        self.__metadata = MetaData()

        self._logger = logger or logging.getLogger(__name__)
        self._config = config

        self._create_engine()

    @classmethod
    def build_connection_from_config(cls, dbconfig: DBConfig,
                                     logger: Optional[logging.Logger] = None) -> 'DBConnection':
        return cls(config=dbconfig, logger=logger)

    @classmethod
    def build_connection_from_uri(cls, uri: str, logger: Optional[logging.Logger] = None,
                                  stream: bool = False, echo: bool = False) -> 'DBConnection':
        parsed_uri = URL.make_url(uri)
        dbconfig = DBConfig(
            delicate=parsed_uri.drivername,
            username=parsed_uri.username,
            password=parsed_uri.password,
            host=parsed_uri.host,
            database=parsed_uri.database,
            port=parsed_uri.port,
            query=parsed_uri.query,
            stream=stream,
            echo=echo
        )
        return cls(config=dbconfig, logger=logger)

    @classmethod
    def build_connection_from_dict(cls, config: dict, logger: Optional[logging.Logger] = None) -> 'DBConnection':
        dbconfig = DBConfig(
            delicate=config.get('delicate'),
            username=config.get('username'),
            password=config.get('password'),
            host=config.get('host'),
            database=config.get('database'),
            port=config.get('port'),
            query=config.get('query'),
            stream=config.get('stream'),
            echo=config.get('echo'),
            kerberos=config.get('kerberos'),
            logger=logger
        )
        return cls(config=dbconfig, logger=logger)

    @property
    def inspector(self) -> inspect:
        if self.__inspector is None:
            self._logger.info('Database engine inspector created successfully.')
            self.__inspector = inspect(self.engine)
        return self.__inspector

    @property
    def metadata(self) -> MetaData:
        return self.__metadata

    @property
    def config(self) -> DBConfig:
        return self._config

    @config.setter
    def config(self, config: DBConfig) -> None:
        if not isinstance(config, DBConfig):
            self._logger.error("Config must be an DBConfig instance.")
            raise TypeError("Config must be an DBConfig instance.")
        self._config = config

    @property
    def engine(self) -> create_engine:
        if self.__engine is None:
            self._create_engine()
        return self.__engine

    def _create_engine(self) -> None:
        self._logger.info(f"Creating connection to {self.config.host} on {self.config.database}...")

        query = self.config.query.build_db_connect_args() if self.config.query else {}
        connect_args = self.config.kerberos.build_db_connect_args() if self.config.kerberos else {}

        query.update(connect_args)
        conn_url = self._build_connection_url(query)
        self._initialize_engine(conn_url)

    def _build_connection_url(self, query: dict) -> URL:
        try:
            return URL(
                drivername=self.config.delicate,
                username=self.config.username,
                password=self.config.password,
                host=self.config.host,
                database=self.config.database,
                port=self.config.port,
                query=query,
            )
        except Exception as e:
            try:
                return URL.make_url(
                    drivername=self.config.delicate,
                    username=self.config.username,
                    password=self.config.password,
                    host=self.config.host,
                    database=self.config.database,
                    port=self.config.port,
                    query=query,
                )
            except Exception as e:
                self._logger.error(f"Failed to build a URI for the Database: {e}")
                raise e

    def _initialize_engine(self, conn_url: URL) -> None:
        try:
            self.__engine = create_engine(
                conn_url,
                echo=self.config.echo,
                pool_size=self.config.pool_size,  # Dynamic pool size
                max_overflow=self.config.max_overflow,  # Dynamic max overflow
                pool_timeout=self.config.pool_timeout,  # Dynamic pool timeout
                pool_recycle=self.config.pool_recycle,  # Dynamic pool recycle time
                poolclass=QueuePool  # Use a QueuePool for pooling
            )
            if self.config.stream:
                self.engine.connect().execution_options(stream_results=self.config.stream)
            self._logger.info(f'Database [{self.engine.url.database}] session created...')
        except SQLAlchemyError as e:
            self._logger.error(f"Database connection error: {e}")
            raise DBConnectionError(f"Database connection error: {e}")
        except Exception as e:
            self._logger.error(f"Unknown error creating database engine: {e}")
            raise DBConnectionError(f"Unknown error: {e}")

    def schemas(self) -> pd.DataFrame:
        """
        Retrieves a list of schemas in the database.

        :return: DataFrame containing the schema names.
        """
        self._logger.info('Retrieving database schemas...')
        start_time = time.time()
        try:
            schemas = self.inspector.get_schema_names()
            df = pd.DataFrame(schemas, columns=['schemas'])
            self._logger.info(f"Retrieved {df.shape[0]} schemas in {time.time() - start_time:.2f} seconds.")
            return df
        except SQLAlchemyError as e:
            self._logger.error(f"Error retrieving schemas: {e}")
            raise DBQueryError(f"Error retrieving schemas: {e}")
        except Exception as e:
            self._logger.error(f"Unknown error during schema retrieval: {e}")
            raise DBQueryError(f"Unknown error: {e}")

    def tables(self, schema: str) -> pd.DataFrame:
        """
        Retrieves a list of tables in the specified schema.

        :param schema: The name of the schema.
        :return: DataFrame containing the table names.
        """
        self._logger.info(f'Retrieving tables for schema: {schema}...')
        start_time = time.time()
        try:
            tables = self.inspector.get_table_names(schema=schema)
            df = pd.DataFrame(tables, columns=['tables'])
            self._logger.info(
                f"Retrieved {df.shape[0]} tables from schema '{schema}' in {time.time() - start_time:.2f} seconds.")
            return df
        except SQLAlchemyError as e:
            self._logger.error(f"Error retrieving tables from schema {schema}: {e}")
            raise DBQueryError(f"Error retrieving tables from schema {schema}: {e}")
        except Exception as e:
            self._logger.error(f"Unknown error during table retrieval from schema {schema}: {e}")
            raise DBQueryError(f"Unknown error: {e}")

    def select(self, query: str, params: Optional[dict] = None, chunk_size: Optional[int] = None) -> pd.DataFrame:
        """
        Executes a SQL select query with optional parameterization.

        :param query: SQL query string.
        :param params: Optional dictionary of parameters to be used in the query.
        :param chunk_size: Number of rows per chunk to return for large queries.
        :return: DataFrame containing the result set.
        """
        self._logger.info(f'Executing query: \n{query}\n')
        start_time = time.time()
        try:
            query_df = pd.read_sql(
                text(query), self.engine, params=params, chunksize=chunk_size
            ).convert_dtypes(convert_string=False)
            self._logger.info(f'Query executed successfully in {time.time() - start_time:.2f} seconds.')
            return query_df
        except SQLAlchemyError as e:
            self._logger.error(f'Error executing SQL query: {e}')
            raise DBQueryError(f'Error executing SQL query: {e}')
        except Exception as e:
            self._logger.error(f'Unknown error during query execution: {e}')
            raise DBQueryError(f'Unknown error: {e}')

    def insert(self, df: pd.DataFrame, table: str, schema: str,
               if_exists: Literal['fail', 'replace', 'append'] = 'fail', chunk_size: Optional[int] = 5000,
               index: bool = False, method: Literal['multi'] = 'multi') -> bool:
        start_time = time.time()
        try:
            df.to_sql(
                table, self.engine, schema=schema, if_exists=if_exists, chunksize=chunk_size, index=index,
                method=method
            )
            self._logger.info(
                f'Data inserted into [{table}] in schema {schema} successfully in {time.time() - start_time:.2f} seconds.')
            return True
        except SQLAlchemyError as e:
            self._logger.error(f"Error inserting data into table {table}: {e}")
            raise DBInsertError(f"Error inserting data into table {table}: {e}")
        except Exception as e:
            self._logger.error(f"Unknown error during data insertion: {e}")
            raise DBInsertError(f"Unknown error: {e}")

    def execute(self, sql: str, commit: bool = False) -> bool:
        self._logger.info(f'Executing SQL: {sql}')
        start_time = time.time()
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text(sql))
                if commit:
                    conn.commit()
            self._logger.info(f'SQL executed successfully in {time.time() - start_time:.2f} seconds.')
            return res
        except SQLAlchemyError as e:
            self._logger.error(f"Error executing SQL: {e}")
            raise DBQueryError(f"Error executing SQL: {e}")
        except Exception as e:
            self._logger.error(f"Unknown error during SQL execution: {e}")
            raise DBQueryError(f"Unknown error: {e}")

    def close(self) -> None:
        if self.__engine:
            self.engine.dispose()
            self._logger.info('Database connection closed successfully.')


class DBTablesFactory:
    def __init__(self, connection: DBConnection, base: Optional[declarative_base] = None,
                 logger: Optional[logging.Logger] = None) -> None:
        """
        Initialize the dynamic table generator with a database connection string.

        :param connection: DBConnection connection instance.
        :param base: Optional SQLAlchemy declarative base.
        :param logger: logger instance.
        """
        self._connection = connection
        self._base = base or declarative_base(cls=Model)
        self._session = sessionmaker(bind=self._connection.engine)()
        self._logger = logger or logging.getLogger(__name__)

    @property
    def base(self) -> declarative_base:
        return self._base

    @base.setter
    def base(self, base: declarative_base) -> None:
        self._base = base

    @property
    def session(self) -> Session:
        """Context manager for a synchronous SQLAlchemy session."""
        if self._session is None:
            self._session = sessionmaker(bind=self._connection.engine)()
        return self._session

    def schema_exists(self, schema: str) -> bool:
        """Check if a schema exists in the database."""
        with self._connection.engine.connect() as conn:
            return conn.dialect.has_schema(conn, schema)

    def create_schema(self, schema: str) -> bool:
        """
        Create a database schema if it does not exist.

        :param schema: Name of the schema
        """
        if not self.schema_exists(schema):
            try:
                self._logger.info(f"Creating schema '{schema}'.")
                with self._connection.engine.connect() as conn:
                    conn.execute(CreateSchema(schema))
                    conn.commit()
                self._logger.info(f"Schema '{schema}' created successfully.")
                return True
            except Exception as e:
                self._logger.error(f"Error creating schema {schema}: {e}")
                raise e
        else:
            self._logger.info(f"Schema '{schema}' already exists.")
            return True

    def drop_schema(self, schema: str) -> bool:
        """Drop a database schema."""
        if self.schema_exists(schema):
            try:
                self._logger.info(f"Dropping schema '{schema}'.")
                with self._connection.engine.connect() as conn:
                    conn.execute(DropSchema(schema))
                    conn.commit()
                self._logger.info(f"Schema '{schema}' dropped successfully.")
                return True
            except Exception as e:
                self._logger.error(f"Error dropping schema {schema}: {e}")
                raise
        else:
            self._logger.info(f"Schema '{schema}' does not exist.")
            return True

    def merge(self, item, commit: bool = False):
        self.session.merge(item)
        if commit:
            self.session.commit()

    def add(self, item, commit: bool = False):
        self.session.add(item)
        if commit:
            self.session.commit()

    def batch_commit(self, threshold=600):

        count = len(self.session.new) + len(self.session.dirty) + len(self.session.deleted)
        if count >= threshold:
            self.session.flush()
            self.session.commit()
            self.session.flush()

    def commit(self, ):
        self.session.flush()
        self.session.commit()
        self.session.flush()

    def create_table_class(self, name: str, columns: dict, schema: str) -> type:
        """
        Create a SQLAlchemy table class dynamically.

        :param name: Name of the table
        :param columns: Dictionary of column names and their types
        :param schema: Schema name where the table will be created
        :return: Table class
        """
        self._logger.info(f"Creating table class '{name}'.")
        attrs = {
            '__tablename__': name.lower(),
            '__table_args__': {
                'extend_existing': True,
                'schema': schema
            },
        }
        attrs.update(columns)

        try:
            self.create_schema(schema)
            return type(name, (self._base,), attrs)
        except Exception as e:
            self._logger.error(f"Error creating table class {name}: {e}")
            raise

    def _ensure_schemas_exist(self) -> None:
        schemas = {table.schema for table in self._base.metadata.tables.values() if table.schema}
        for schema in schemas:
            self.create_schema(schema)

    def create_tables(self) -> None:
        """
        Create all tables in the database.
        """
        try:
            self._logger.info("Creating schemas and tables.")
            self._ensure_schemas_exist()
            self._base.metadata.create_all(self._connection.engine)
            self._logger.info("All tables created successfully.")
        except Exception as e:
            self._logger.error(f"Error creating tables: {e}")
            raise e

    def get_table_metadata(self, table: str, schema: Optional[str] = None) -> dict:
        """Retrieve metadata for a specified table."""
        try:
            with self._connection.engine.connect() as conn:
                inspector = inspect(conn)
                return inspector.get_columns(table, schema=schema)
        except Exception as e:
            self._logger.error(f"Error retrieving metadata for table {table}: {e}")
            raise e

    def create_table_from_dict(self, schema: str, table: str, columns: dict) -> tuple[bool, Optional[str]]:
        if not all([table, columns, schema]):
            self._logger.error("Invalid configuration. Ensure 'table_name', 'columns', and 'schema' are provided.")
            return False, None

        try:
            table_class = self.create_table_class(table, columns, schema)
            self.create_tables()
            path = self.dump_class_by_table_and_schema(
                cls=table_class,
                table_name=table,
                schema_name=schema,
            )
            return True, path
        except Exception as e:
            self._logger.error(f"Error creating table from config: {e}")
            raise e

    def load_class_by_table_and_schema(self, table_name: str, schema_name: Optional[str] = None,
                                       path: str = 'classes') -> type:
        source = f"{schema_name}." if schema_name else '' + table_name
        self._logger.info(f"Loading class for table: {source}")
        if not os.path.exists(path):
            os.mkdir(path)

        file_path = os.path.join(path, f"{source}.{table_name}.ddl")

        try:
            with open(file_path, 'rb') as file:
                cls = pkl.load(file)
            return cls
        except FileNotFoundError as e:
            self._logger.error(f"Class file not found: {e}")
            raise e
        except Exception as e:
            self._logger.error(f"Error loading class: {e}")
            raise e

    def dump_class_by_table_and_schema(self, cls: type, table_name: str, schema_name: Optional[str] = None,
                                       path: str = 'classes') -> str:
        source = f"{schema_name}." if schema_name else '' + table_name
        self._logger.info(f"Dumping class for table: {source}")
        if not os.path.exists(path):
            os.mkdir(path)

        file_path = os.path.join(path, f"{source}.{table_name}.ddl")

        with open(file_path, 'wb') as file:
            pkl.dump(cls, file)
            file.flush()

        return file_path

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._logger.info('Session closed successfully.')


def get_db_hook(config: Any, create: bool = False, logger: Optional[logging.Logger] = None) -> tuple[
    DBConnection, DBTablesFactory]:
    if isinstance(config, dict):
        conn = DBConnection.build_connection_from_dict(config, logger=logger)
    elif isinstance(config, DBConfig):
        conn = DBConnection.build_connection_from_config(config, logger=logger)
    else:
        raise TypeError(f"Unsupported parameter type '{type(config)}' for creating a database connection.")

    from models.models import BASE
    fac = DBTablesFactory(conn, base=BASE, logger=logger)

    if create:
        fac.create_tables()

    return conn, fac
