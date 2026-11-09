"""Vendor-aware DDL checks. Never accepts an unknown vendor or unenforced CHECK."""
import re
from sqlalchemy import text

CHECK_ERRORS = (4025, 3819)  # MariaDB / MySQL; duplicate-key 1062 is handled separately.


def shared_read(db):
    """MySQL read-only policy/provenance rows need shared locks, not write grants.

    MySQL FOR UPDATE requires UPDATE/DELETE/LOCK TABLES; FOR SHARE needs SELECT.
    Existing MariaDB and SQLite lock behavior is left unchanged.
    """
    dialect=db.get_bind().dialect
    return dialect.name=='mysql' and not getattr(dialect,'is_mariadb',False)


def vendor(connection):
    version = connection.scalar(text('SELECT VERSION()'))
    if 'MariaDB' in version:
        return 'mariadb'
    comment = connection.scalar(text('SELECT @@version_comment'))
    if re.match(r'^8\.(0|4)\.', version) and 'mysql' in comment.lower():
        return 'mysql'
    raise RuntimeError('UNSUPPORTED_DATABASE_VENDOR_OR_VERSION')


def verify_check_enforcement(connection):
    if connection.scalar(text('SELECT @@unique_checks')) != 1 or connection.scalar(text('SELECT @@foreign_key_checks')) != 1:
        raise RuntimeError('DATABASE_CONSTRAINT_CHECKS_DISABLED')
    if vendor(connection) == 'mariadb':
        if connection.scalar(text('SELECT @@check_constraint_checks')) != 1:
            raise RuntimeError('CHECK_ENFORCEMENT_DISABLED')
    else:
        # No MySQL equivalent of MariaDB's session switch. Check the actual DDL.
        disabled = connection.scalar(text("SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND CONSTRAINT_TYPE='CHECK' AND ENFORCED<>'YES'"))
        if disabled:
            raise RuntimeError('MYSQL_CHECK_NOT_ENFORCED')


def normalized_expression(value):
    # MySQL reflection introduces charset names before literals; semantics stay
    # identical. Do not strip arbitrary SQL tokens or change literal contents.
    value = re.sub(r'_[a-zA-Z0-9]+(?=[\'\"])', '', str(value))
    return re.sub(r'[\s`()]+', '', value).lower()
