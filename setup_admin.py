from database.db import init_db, create_user

# Initialize the new tables
init_db()

print("\n--- System Setup: Create Super Admin ---")
name = input("Enter Admin's Full Name (e.g., John Doe): ")
username = input("Enter Admin Username (e.g., admin1): ")
password = input("Enter Admin Password: ")

# Save to the new database with secure hashing
success, message = create_user(username, password, "admin", name)

if success:
    print("\nSuccess! You can now use these credentials to log into the dashboard.")
else:
    print(f"\nSetup Failed: {message}")