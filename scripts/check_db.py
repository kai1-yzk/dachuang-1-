import sys
import os
sys.path.append(os.path.abspath('backend'))
from utils import db

print('DB config:', db.DB_HOST, db.DB_PORT, db.DB_USER, db.DB_NAME)
conn = db.get_connection()
print('connection object:', conn)
if conn:
    try:
        with conn.cursor() as c:
            c.execute('SELECT 1 as v')
            print('query result:', c.fetchall())
    except Exception as e:
        print('query error:', e)
    finally:
        conn.close()
else:
    print('No DB connection (pool is None)')
