"""Shared PostgreSQL metadata inspection helpers for NRI applications."""

import re
from typing import List

import pandas as pd
from sqlalchemy import text


def list_postgres_databases(engine) -> List[str]:
    sql = """
    SELECT datname
    FROM pg_database
    WHERE datistemplate = false
      AND datallowconn = true
    ORDER BY datname
    """
    df = pd.read_sql(text(sql), engine)
    return df["datname"].tolist()


def replace_dbname_in_dsn(dsn: str, new_db_name: str) -> str:
    return re.sub(r"/[^/?]+(\?.*)?$", f"/{new_db_name}", dsn)


def get_database_objects(engine) -> pd.DataFrame:
    sql = """
    SELECT
        ns.nspname AS table_schema,
        cls.relname AS table_name,
        CASE cls.relkind
            WHEN 'r' THEN 'BASE TABLE'
            WHEN 'p' THEN 'PARTITIONED TABLE'
            WHEN 'v' THEN 'VIEW'
            WHEN 'm' THEN 'MATERIALIZED VIEW'
            WHEN 'f' THEN 'FOREIGN TABLE'
            ELSE cls.relkind::text
        END AS object_type,
        pg_get_userbyid(cls.relowner) AS owner_name,
        COALESCE(cls.reltuples, 0)::bigint AS estimated_rows,
        pg_size_pretty(
            pg_total_relation_size(cls.oid)
        ) AS total_size,
        obj_description(
            cls.oid,
            'pg_class'
        ) AS table_comment
    FROM pg_class cls
    JOIN pg_namespace ns
      ON ns.oid = cls.relnamespace
    WHERE cls.relkind IN ('r', 'p', 'v', 'm', 'f')
      AND ns.nspname NOT IN (
          'information_schema',
          'pg_catalog',
          'pg_toast'
      )
    ORDER BY
        ns.nspname,
        cls.relname
    """
    return pd.read_sql(text(sql), engine)


def get_all_columns(engine) -> pd.DataFrame:
    sql = """
    SELECT
        c.table_schema,
        c.table_name,
        c.ordinal_position,
        c.column_name,
        c.data_type,
        c.udt_name,
        c.character_maximum_length,
        c.numeric_precision,
        c.numeric_scale,
        c.is_nullable,
        c.column_default,
        pgd.description AS column_comment
    FROM information_schema.columns c
    JOIN pg_class cls
      ON cls.relname = c.table_name
    JOIN pg_namespace ns
      ON ns.oid = cls.relnamespace
     AND ns.nspname = c.table_schema
    LEFT JOIN pg_description pgd
      ON pgd.objoid = cls.oid
     AND pgd.objsubid = c.ordinal_position
    WHERE c.table_schema NOT IN (
        'information_schema',
        'pg_catalog',
        'pg_toast'
    )
    ORDER BY
        c.table_schema,
        c.table_name,
        c.ordinal_position
    """
    return pd.read_sql(text(sql), engine)


def get_primary_keys(engine) -> pd.DataFrame:
    sql = """
    SELECT
        tc.table_schema,
        tc.table_name,
        tc.constraint_name,
        kcu.column_name,
        kcu.ordinal_position
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.table_schema = kcu.table_schema
     AND tc.table_name = kcu.table_name
    WHERE tc.constraint_type = 'PRIMARY KEY'
      AND tc.table_schema NOT IN (
          'information_schema',
          'pg_catalog',
          'pg_toast'
      )
    ORDER BY
        tc.table_schema,
        tc.table_name,
        kcu.ordinal_position
    """
    return pd.read_sql(text(sql), engine)


def get_foreign_keys(engine) -> pd.DataFrame:
    sql = """
    SELECT
        source_ns.nspname AS source_schema,
        source_table.relname AS source_table,
        source_att.attname AS source_column,
        target_ns.nspname AS target_schema,
        target_table.relname AS target_table,
        target_att.attname AS target_column,
        con.conname AS constraint_name,
        CASE con.confupdtype
            WHEN 'a' THEN 'NO ACTION'
            WHEN 'r' THEN 'RESTRICT'
            WHEN 'c' THEN 'CASCADE'
            WHEN 'n' THEN 'SET NULL'
            WHEN 'd' THEN 'SET DEFAULT'
            ELSE con.confupdtype::text
        END AS update_rule,
        CASE con.confdeltype
            WHEN 'a' THEN 'NO ACTION'
            WHEN 'r' THEN 'RESTRICT'
            WHEN 'c' THEN 'CASCADE'
            WHEN 'n' THEN 'SET NULL'
            WHEN 'd' THEN 'SET DEFAULT'
            ELSE con.confdeltype::text
        END AS delete_rule,
        source_key.ordinality AS column_position
    FROM pg_constraint con
    JOIN pg_class source_table
      ON source_table.oid = con.conrelid
    JOIN pg_namespace source_ns
      ON source_ns.oid = source_table.relnamespace
    JOIN pg_class target_table
      ON target_table.oid = con.confrelid
    JOIN pg_namespace target_ns
      ON target_ns.oid = target_table.relnamespace
    JOIN LATERAL unnest(
        con.conkey
    ) WITH ORDINALITY AS source_key(
        attnum,
        ordinality
    )
      ON TRUE
    JOIN LATERAL unnest(
        con.confkey
    ) WITH ORDINALITY AS target_key(
        attnum,
        ordinality
    )
      ON target_key.ordinality = source_key.ordinality
    JOIN pg_attribute source_att
      ON source_att.attrelid = con.conrelid
     AND source_att.attnum = source_key.attnum
    JOIN pg_attribute target_att
      ON target_att.attrelid = con.confrelid
     AND target_att.attnum = target_key.attnum
    WHERE con.contype = 'f'
      AND source_ns.nspname NOT IN (
          'information_schema',
          'pg_catalog',
          'pg_toast'
      )
    ORDER BY
        source_schema,
        source_table,
        constraint_name,
        column_position
    """
    return pd.read_sql(text(sql), engine)


def get_indexes(engine) -> pd.DataFrame:
    sql = """
    SELECT
        schemaname AS table_schema,
        tablename AS table_name,
        indexname AS index_name,
        indexdef AS index_definition
    FROM pg_indexes
    WHERE schemaname NOT IN (
        'information_schema',
        'pg_catalog',
        'pg_toast'
    )
    ORDER BY
        schemaname,
        tablename,
        indexname
    """
    return pd.read_sql(text(sql), engine)


def get_unique_constraints(engine) -> pd.DataFrame:
    sql = """
    SELECT
        tc.table_schema,
        tc.table_name,
        tc.constraint_name,
        STRING_AGG(
            kcu.column_name,
            ', ' ORDER BY kcu.ordinal_position
        ) AS columns
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.table_schema = kcu.table_schema
     AND tc.table_name = kcu.table_name
    WHERE tc.constraint_type = 'UNIQUE'
      AND tc.table_schema NOT IN (
          'information_schema',
          'pg_catalog',
          'pg_toast'
      )
    GROUP BY
        tc.table_schema,
        tc.table_name,
        tc.constraint_name
    ORDER BY
        tc.table_schema,
        tc.table_name,
        tc.constraint_name
    """
    return pd.read_sql(text(sql), engine)
