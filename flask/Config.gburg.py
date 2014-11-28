from pymongo import MongoClient
import os
import netifaces

# This is a placeholder. After first system install, we need a page that
# Expects these things to be entered before the system becomes operational.

API_KEY= "AIzaSyDgnBNVM2l0MS0fWMXh3SCzBz6FJyiSodU"
SMTP_SERVER="smtp.nist.gov"
SMTP_PORT = 25
SMTP_SENDER = "mranga@nist.gov"
ADMIN_EMAIL_ADDRESS = "mranga@nist.gov"
ADMIN_PASSWORD = "12345"
# Time between captures.
STREAMING_SAMPLING_INTERVAL_SECONDS = 15*60
# number of spectrums per sample
STREAMING_CAPTURE_SAMPLE_SIZE = 10000
STREAMING_FILTER = "PEAK"
STREAMING_SERVER_PORT = 9000
STREAMING_SECONDS_PER_FRAME = 0.05
IS_AUTHENTICATION_REQUIRED = False

# A list of base URLS where this server will REGISTER
# the sensors that it manages. This contains pairs of server 
# base URL and server key. 

PEERS=[{"protocol":"http", "host":"129.6.140.82" ,"port":8000, "key":"efgh"} ,
       {"protocol":"http", "host":"129.6.140.77" ,"port":8000, "key":"abcd"} ]

mongodb_host = os.environ.get('DB_PORT_27017_TCP_ADDR', 'localhost')
client = MongoClient(mongodb_host)
db = client.sysconfig
oldConfig = db.configuration.find_one({})

if oldConfig != None:
    db.configuration.remove(oldConfig)

# Determine my host address by looking at the interfaces
# and the default route (not always foolproof but works
# most of the time). If you use specific routes,
# this will not work.
gws = netifaces.gateways()
gw = gws['default'][netifaces.AF_INET]
addrs = netifaces.ifaddresses(gw[1])
MY_HOST_NAME = addrs[netifaces.AF_INET][0]['addr']


configuration = {"API_KEY":API_KEY,\
"SMTP_SERVER":SMTP_SERVER, \
"SMTP_PORT" : SMTP_PORT,\
"SMTP_SENDER": SMTP_SENDER,\
"ADMIN_EMAIL_ADDRESS":ADMIN_EMAIL_ADDRESS,\
"ADMIN_PASSWORD":ADMIN_PASSWORD, \
"STREAMING_SAMPLING_INTERVAL_SECONDS":STREAMING_SAMPLING_INTERVAL_SECONDS,\
"STREAMING_CAPTURE_SAMPLE_SIZE":STREAMING_CAPTURE_SAMPLE_SIZE,\
"STREAMING_SECONDS_PER_FRAME":STREAMING_SECONDS_PER_FRAME,\
"STREAMING_FILTER": STREAMING_FILTER,\
"STREAMING_SERVER_PORT": STREAMING_SERVER_PORT,\
"IS_AUTHENTICATION_REQUIRED": IS_AUTHENTICATION_REQUIRED,\
"PEERS":PEERS,\
"HOST_NAME":MY_HOST_NAME
}

db.configuration.insert(configuration)

