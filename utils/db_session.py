import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

db_engine = create_engine(os.environ["PGSQL_CONNECTION"])
session_maker = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
db_session = session_maker()