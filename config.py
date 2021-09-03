# .envをロードして、環境変数へ反映
from dotenv import load_dotenv
load_dotenv()

# 環境変数を参照
import os
CHANNEL_ACCESS_TOKEN = os.getenv('CHANNEL_ACCESS_TOKEN')
NEO4JID=os.getenv('NEO4JID')
NEO4JPW=os.getenv('NEO4JPW')
NEO4JURL=os.getenv('NEO4JURL')
