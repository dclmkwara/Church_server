"""
Verify partitions
"""
import psycopg2
from app.core.config import settings

def check_partitions():
    conn = psycopg2.connect(settings.DATABASE_URL.replace('+asyncpg', ''))
    cur = conn.cursor()

    tables = ['counts', 'offerings', 'fellowship_attendance']
    
    for table in tables:
        print(f"\\n=== Partitions for table '{table}' ===")
        cur.execute("""
            SELECT child.relname
            FROM pg_inherits
            JOIN pg_class parent        ON pg_inherits.inhparent = parent.oid
            JOIN pg_class child         ON pg_inherits.inhrelid   = child.oid
            WHERE parent.relname = %s
            ORDER BY child.relname;
        """, (table,))
        partitions = cur.fetchall()
        for p in partitions:
            print(f"  - {p[0]}")
            
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_partitions()
