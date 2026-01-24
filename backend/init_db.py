"""
Atlas 2.0 - Database Initialization Script

Run this script to initialize or reset the database schema.
"""

from database import init_db, reset_db
import sys

def main():
    print("=" * 60)
    print("Atlas 2.0 - Database Initialization")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        print("\n⚠️  WARNING: This will DELETE all data!")
        response = input("Are you sure you want to reset the database? (yes/no): ")
        
        if response.lower() == "yes":
            print("\n🗑️  Resetting database...")
            try:
                reset_db()
                print("✅ Database reset successfully!")
            except Exception as e:
                print(f"❌ Error resetting database: {e}")
                return 1
        else:
            print("Cancelled.")
            return 0
    else:
        print("\n🔧 Initializing database...")
        try:
            init_db()
            print("✅ Database initialized successfully!")
            print("\nDatabase is ready for use.")
            print("You can now start the server with: python server.py")
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
