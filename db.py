#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import logging
import pymysql

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.config = {
            'host':            os.getenv('DB_HOST', 'localhost'),
            'user':            os.getenv('DB_USER', 'root'),
            'password':        os.getenv('DB_PASS', ''),
            'charset':         'utf8mb4',
            'cursorclass':     pymysql.cursors.DictCursor,
            'connect_timeout': 5,
            'read_timeout':    10,
            'write_timeout':   10,
        }
        self.config_gps = {
            'host':            os.getenv('GPS_DB_HOST', 'localhost'),
            'user':            os.getenv('GPS_DB_USER', 'systemph'),
            'password':        os.getenv('GPS_DB_PASS', '22zbV7I5zm'),
            'database':        'systemph_gpstracker',
            'charset':         'utf8mb4',
            'cursorclass':     pymysql.cursors.DictCursor,
            'connect_timeout': 5,
            'read_timeout':    10,
            'write_timeout':   10,
        }

    def _connect(self, db_name):
        return pymysql.connect(**{**self.config, 'database': db_name})

    def _connect_gps(self):
        return pymysql.connect(**self.config_gps)