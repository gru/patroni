#!/bin/bash
echo "\c postgres
DROP DATABASE IF EXISTS source_db;" \
| psql;

echo "\c postgres
CREATE DATABASE source_db;" \
| psql;

echo "\c source_db
CREATE TABLE IF NOT EXISTS public.debezium_table(id int primary key, current_value bigint not null);" \
| psql; 

echo '\c source_db
CREATE EXTENSION IF NOT EXISTS "pgcrypto";' \
| psql; 

echo "\c source_db
CREATE TABLE IF NOT EXISTS public.outbox(id uuid default gen_random_uuid() primary key, aggregatetype character varying(255), aggregateid character varying(255), type character varying(255), payload jsonb);" \
| psql; 

echo "\c source_db
CREATE TABLE IF NOT EXISTS public.debezium_signal(id character varying(42) primary key, type character varying(32) not null, data text null);" \
| psql; 

echo "\c source_db
CREATE TABLE public.debezium_heartbeat (last_heartbeat_ts TIMESTAMPTZ DEFAULT NOW() PRIMARY KEY);" \
| psql; 

echo "\c source_db
INSERT INTO public.debezium_heartbeat (last_heartbeat_ts) VALUES (NOW());" \
| psql; 

echo '\c source_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";' \
| psql; 

# Создать публикацию для Debezium
echo "\c source_db
CREATE PUBLICATION dbz_publication FOR ALL TABLES;" \
| psql;

# Проверить создание публикации
echo "\c source_db
SELECT pubname, puballtables, pubinsert, pubupdate, pubdelete, pubtruncate 
FROM pg_publication 
WHERE pubname = 'dbz_publication';" \
| psql;

echo "✅ Database setup completed with publication 'dbz_publication'"