"""
Test database connection and verify tables exist
"""
import sys
from sqlalchemy import create_engine, text
from app.core.config import settings

def test_connection():
    """Test database connection"""
    try:
        print("Testing database connection...")
        print(f"Database URL: {settings.DATABASE_URL.split('@')[0]}@***")
        
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        
        with engine.connect() as conn:
            # Test basic connection
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✓ Connected to PostgreSQL: {version.split(',')[0]}")
            
            # Check if tables exist
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('document_verifications', 'audit_logs')
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result.fetchall()]
            
            if 'document_verifications' in tables:
                print("✓ Table 'document_verifications' exists")
                
                # Check column count
                result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.columns 
                    WHERE table_name = 'document_verifications';
                """))
                col_count = result.fetchone()[0]
                print(f"  - Has {col_count} columns")
            else:
                print("✗ Table 'document_verifications' NOT found")
            
            if 'audit_logs' in tables:
                print("✓ Table 'audit_logs' exists")
                
                # Check column count
                result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.columns 
                    WHERE table_name = 'audit_logs';
                """))
                col_count = result.fetchone()[0]
                print(f"  - Has {col_count} columns")
            else:
                print("✗ Table 'audit_logs' NOT found")
            
            # Check indexes
            result = conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename IN ('document_verifications', 'audit_logs')
                ORDER BY tablename, indexname;
            """))
            indexes = [row[0] for row in result.fetchall()]
            print(f"\n✓ Found {len(indexes)} indexes on document_verifications and audit_logs tables")
            
            # Test a simple query
            result = conn.execute(text("SELECT COUNT(*) FROM document_verifications;"))
            count = result.fetchone()[0]
            print(f"✓ document_verifications table has {count} records")
            
            print("\n✅ Database connection test successful!")
            return True
            
    except Exception as e:
        print(f"\n❌ Database connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

