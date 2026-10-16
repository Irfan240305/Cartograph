import sys

from dotenv import load_dotenv

from cartograph.onboard import add_repo

load_dotenv(override=True)

print(add_repo(sys.argv[1]))