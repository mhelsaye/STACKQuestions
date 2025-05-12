import os

creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS")
if creds_json:
    print("Environment variable IS set!")
    print("Full content of creds_json:")
    print(creds_json)  # Print the entire string for inspection (TEMPORARILY!)
else:
    print("Environment variable is NOT set!")
    raise ValueError("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS environment variable is not set!")
    
