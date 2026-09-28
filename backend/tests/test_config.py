from app.config import Settings


def test_database_url_built_from_parts_when_host_and_password_given():
    settings = Settings(
        db_host="my-db.example.com",
        db_port=3306,
        db_name="mydb",
        db_user="admin",
        db_password="s3cret",
    )
    assert settings.database_url == "mysql+pymysql://admin:s3cret@my-db.example.com:3306/mydb"


def test_database_url_keeps_explicit_value_when_host_or_password_missing():
    # No db_host/db_password given: the explicit database_url must NOT be overridden
    # (this is the local docker-compose / test path, e.g. SQLite in CI).
    settings = Settings(database_url="mysql+pymysql://root:rootpass@db:3306/servicepulse")
    assert settings.database_url == "mysql+pymysql://root:rootpass@db:3306/servicepulse"

