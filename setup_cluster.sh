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

echo "\c source_db
CREATE TABLE IF NOT EXISTS public.outbox(id uuid default gen_random_uuid() primary key, aggregatetype character varying(255), aggregateid character varying(255), type character varying(255), payload jsonb);" \
| psql; 
