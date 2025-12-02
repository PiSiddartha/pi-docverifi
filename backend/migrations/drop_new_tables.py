#!/usr/bin/env python3
"""
Script to drop the new refactored tables
This will NOT drop merchant_document or psc_document
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.database import engine
from app.core.config import settings

def drop_tables():
    """Drop the new refactored tables"""
    
    tables_to_drop = [
        'director_verification_documents',
        'vat_registration_documents',
        'company_registration_documents',
        'companies_house_documents',
        'documents'
    ]
    
    print("=" * 70)
    print("Dropping New Refactored Tables")
    print("=" * 70)
    print("\nTables to drop:")
    for table in tables_to_drop:
        print(f"  - {table}")
    
    print("\nTables that will be KEPT:")
    print("  ✓ merchant_document")
    print("  ✓ psc_document")
    print("  ✓ document_verifications (old table - will be kept)")
    
    print("\n" + "=" * 70)
    
    try:
        with engine.connect() as conn:
            for table in tables_to_drop:
                print(f"\nDropping {table}...")
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                    conn.commit()
                    print(f"  ✅ {table} dropped successfully")
                except Exception as e:
                    print(f"  ⚠️  Error dropping {table}: {e}")
                    conn.rollback()
        
        # Verify tables were dropped
        print("\n" + "=" * 70)
        print("Verifying tables...")
        print("=" * 70)
        
        with engine.connect() as conn:
            for table in tables_to_drop:
                result = conn.execute(text(f"""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_name = '{table}'
                """))
                exists = result.scalar() > 0
                if exists:
                    print(f"  ⚠️  {table:40} STILL EXISTS")
                else:
                    print(f"  ✅ {table:40} DROPPED")
            
            # Verify kept tables still exist
            kept_tables = ['merchant_document', 'psc_document', 'document_verifications']
            print("\nVerifying kept tables:")
            for table in kept_tables:
                result = conn.execute(text(f"""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_name = '{table}'
                """))
                exists = result.scalar() > 0
                if exists:
                    print(f"  ✅ {table:40} EXISTS (kept)")
                else:
                    print(f"  ⚠️  {table:40} NOT FOUND")
        
        print("\n" + "=" * 70)
        print("✅ Table cleanup completed!")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    response = input("This will drop the new refactored tables. Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Operation cancelled.")
        sys.exit(0)
    
    print()
    drop_tables()

