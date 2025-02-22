from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy import BigInteger, Column, Integer, String, DateTime, Enum, Boolean, ARRAY, PrimaryKeyConstraint, \
    Index, event, DDL
from sqlalchemy.engine import Engine

from models.utils import Model

try:
    from sqlalchemy.orm import declarative_base
except:
    from sqlalchemy.ext.declarative import declarative_base

BASE = declarative_base(cls=Model)
SCHEMA = 'screening'


# STATUS_ENUM = Enum(HDFSRetentionStatus, name='HDFSRetentionStatus', schema=SCHEMA, create_type=True)
# PATH_TYPE_ENUM = Enum(PathType, name='PathType', schema=SCHEMA, create_type=True)


class Customers(BASE):
    __tablename__ = 'customers'
    __table_args__ = (
        PrimaryKeyConstraint('id', 'hash'),
        Index('idx_customers_hash', 'hash'),
        {'extend_existing': True, 'schema': SCHEMA, 'postgresql_partition_by': 'HASH (hash)'},
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String, nullable=False)
    name_1 = Column(String, nullable=False)
    name_2 = Column(String, nullable=False)
    name_3 = Column(String)
    name_4 = Column(String)
    name_5 = Column(String)
    name_6 = Column(String)
    name_7 = Column(String)
    name_8 = Column(String)
    name_9 = Column(String)
    name_10 = Column(String)
    count = Column(Integer)
    hash = Column(String, nullable=False)


# Sanctions Table with Partitioning
class Sanctions(BASE):
    __tablename__ = 'sanctions'
    __table_args__ = (
        PrimaryKeyConstraint('id', 'hash'),
        Index('idx_sanctions_hash', 'hash'),
        {'extend_existing': True, 'schema': SCHEMA, 'postgresql_partition_by': 'HASH (hash)'},
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String, nullable=False)
    name_1 = Column(String, nullable=False)
    name_2 = Column(String, nullable=False)
    name_3 = Column(String)
    name_4 = Column(String)
    name_5 = Column(String)
    name_6 = Column(String)
    name_7 = Column(String)
    name_8 = Column(String)
    name_9 = Column(String)
    name_10 = Column(String)
    count = Column(Integer)
    hash = Column(String, nullable=False)
    reason = Column(String, nullable=False)


# Event listener to create partitions manually
# DDL for Partition Creation
for i in range(4):
    customers_partition_ddl = DDL(f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.customers_part{i + 1}
        PARTITION OF {SCHEMA}.customers
        FOR VALUES WITH (MODULUS 4, REMAINDER {i});
    """)
    sanctions_partition_ddl = DDL(f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.sanctions_part{i + 1}
        PARTITION OF {SCHEMA}.sanctions
        FOR VALUES WITH (MODULUS 4, REMAINDER {i});
    """)

    event.listen(Customers.__table__, 'after_create', customers_partition_ddl)
    event.listen(Sanctions.__table__, 'after_create', sanctions_partition_ddl)
