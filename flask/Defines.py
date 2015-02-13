'''
Created on Feb 2, 2015

@author: local
'''

SENSOR_ID = "SensorID"
SENSOR_KEY="SensorKey"
SENSOR_ADMIN_EMAIL = "sensorAdminEmail"
SENSOR_STATUS = "sensorStatus"
LOCAL_DB_INSERTION_TIME = "_localDbInsertionTime"
DATA_RETENTION_DURATION_MONTHS = "dataRetentionDurationMonths"
SENSOR_THRESHOLDS = "thresholds"
SENSOR_STREAMING_PARAMS = "streaming"
STREAMING_SAMPLING_INTERVAL_SECONDS = "streamingSamplingIntervalSeconds"
STREAMING_SECONDS_PER_FRAME = "streamingSecondsPerFrame"
STREAMING_CAPTURE_SAMPLE_SIZE_SECONDS = "streamingCaptureSampleSizeSeconds"
STREAMING_FILTER = "streamingFilter"
LAST_MESSAGE_TYPE = "lastMessageType"
LAST_MESSAGE_DATE = "lastMessageDate"
ENABLED = "ENABLED"
DISABLED = "DISABLED"
LAT = "Lat"
LON = "Lon"
ALT = "Alt"
FFT_POWER = "FFT-Power"
SWEPT_FREQUENCY = "Swept-frequency"



ADMIN_EMAIL_ADDRESS = "ADMIN_EMAIL_ADDRESS"
UNKNOWN = "UNKNOWN"
ADMIN_PASSWORD = "ADMIN_PASSWORD"
API_KEY= "API_KEY"
HOST_NAME = "HOST_NAME"
PUBLIC_PORT= "PUBLIC_PORT"
PROTOCOL= "PROTOCOL"
IS_AUTHENTICATION_REQUIRED = "IS_AUTHENTICATION_REQUIRED"
MY_SERVER_ID = "MY_SERVER_ID" 
MY_SERVER_KEY = "MY_SERVER_KEY" 
SMTP_PORT = "SMTP_PORT"
SMTP_SERVER = "SMTP_SERVER"
ADMIN_USER_FIRST_NAME = "ADMIN_USER_FIRST_NAME"
ADMIN_USER_LAST_NAME =  "ADMIN_USER_LAST_NAME"
STREAMING_SERVER_PORT = "STREAMING_SERVER_PORT"
SOFT_STATE_REFRESH_INTERVAL = "SOFT_STATE_REFRESH_INTERVAL"



#Message Types

SYS = "Sys"
LOC = "Loc"
DATA = "Data"
CAL = "Cal"
DATA_TYPE = "DataType"
DATA_KEY="dataKey"
TYPE = "Type"
NOISE_FLOOR = "wnI"
SYS_TO_DETECT="Sys2Detect"
THRESHOLD_DBM_PER_HZ = "thresholdDbmPerHz"
THRESHOLD_MIN_FREQ_HZ = "minFreqHz"
THRESHOLD_MAX_FREQ_HZ = "maxFreqHz"
THRESHOLD_SYS_TO_DETECT = "systemToDetect"


# Streaming filter types
MAX_HOLD = "MAX_HOLD"

TIME_ZONE_KEY = "TimeZone"

TWO_HOURS = 2 * 60 * 60
SIXTY_DAYS = 60*60*60*60
HOURS_PER_DAY = 24
MINUTES_PER_DAY = HOURS_PER_DAY * 60
SECONDS_PER_DAY = MINUTES_PER_DAY * 60
MILISECONDS_PER_DAY = SECONDS_PER_DAY * 1000
UNDER_CUTOFF_COLOR = '#D6D6DB'
OVER_CUTOFF_COLOR = '#000000'
