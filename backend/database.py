from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

def make_engine(settings, url=None):
    target = url or URL.create('mysql+mysqlconnector', username=settings.db_user,
        password=settings.db_password, host=settings.db_host, port=settings.db_port,
        database=settings.db_name, query={'charset': 'utf8mb4'})
    engine = create_engine(target, pool_pre_ping=True)
    if engine.dialect.name == 'mysql':
        # Each API statement observes committed changes from parallel requests.
        engine = engine.execution_options(isolation_level='READ COMMITTED')
    return engine

def make_sessions(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
