#!/usr/bin/env python3
"""
Script to run the database refactoring migration
This will create separate tables for each document type
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.database import engine
from app.core.config import settings

def run_refactor():
    """Run the refactoring migration"""
    migration_file = os.path.join(os.path.dirname(__file__), 'complete_refactor.sql')
    
    print(f"Reading migration file: {migration_file}")
    
    try:
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        print("Connecting to database...")
        print(f"Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'N/A'}")
        
        with engine.connect() as conn:
            print("\n" + "="*70)
            print("Executing refactoring migration...")
            print("="*70)
            print("\nThis will:")
            print("  1. Create new table structure (documents + 4 type-specific tables)")
            print("  2. Migrate existing data from old table to new tables")
            print("  3. Keep old table (commented out DROP statement)")
            print("\n" + "="*70)
            
            conn.execute(text(migration_sql))
            conn.commit()
            print("\n✅ Refactoring migration completed successfully!")
            print("\n⚠️  NOTE: Old 'document_verifications' table still exists.")
            print("   Review the data in new tables, then uncomment DROP statement in SQL file.")
        
        # Verify new tables
        print("\n" + "="*70)
        print("Verifying new tables...")
        print("="*70)
        
        check_tables = [
            'documents',
            'companies_house_documents',
            'company_registration_documents',
            'vat_registration_documents',
            'director_verification_documents'
        ]
        
        with engine.connect() as conn:
            for table in check_tables:
                result = conn.execute(text(f"""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_name = '{table}'
                """))
                exists = result.scalar() > 0
                if exists:
                    # Get row count
                    count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = count_result.scalar()
                    print(f"  ✅ {table:40} ({count} rows)")
                else:
                    print(f"  ❌ {table:40} NOT FOUND")
        
        print("\n" + "="*70)
        print("Migration verification complete!")
        print("="*70)
        
    except FileNotFoundError:
        print(f"❌ Error: Migration file not found: {migration_file}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 70)
    print("Database Refactoring: Separate Tables per Document Type")
    print("=" * 70)
    print()
    print("⚠️  WARNING: This will refactor your database structure!")
    print("   - Creates new tables: documents + 4 type-specific tables")
    print("   - Migrates existing data")
    print("   - Old table will remain (you can drop it later)")
    print()
    
    response = input("Continue with refactoring? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Refactoring cancelled.")
        sys.exit(0)
    
    print()
    run_refactor()
    print("\n" + "=" * 70)
    print("Refactoring process completed!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Review the data in new tables")
    print("2. Update application code to use new models")
    print("3. Test the application")
    print("4. When ready, uncomment DROP statement in complete_refactor.sql")
    print("=" * 70)

