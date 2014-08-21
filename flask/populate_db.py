import struct
from struct import *
import json
import pymongo
import numpy as np
import os
from os import path
from os import makedirs
from pprint import pprint
from json import JSONEncoder
from pymongo import MongoClient
from pymongo import ASCENDING
from bson.objectid import ObjectId
from bson.json_util import dumps
import gridfs
from datetime import datetime
from dateutil import tz
import calendar
from bson.objectid import ObjectId
import httplib
import argparse
import time
import timezone


mongodb_host = os.environ.get('DB_PORT_27017_TCP_ADDR', 'localhost')
client = MongoClient(mongodb_host)
db = client.spectrumdb
bulk = db.spectrumdb.initialize_ordered_bulk_op()
bulk.find({}).remove()

SENSOR_ID = "SensorID"
TIME_ZONE_KEY = "timeZone"
timeStampBug  = False

def roundTo2DecimalPlaces(value):
    newVal = int(value*100)
    return float(newVal)/float(100)

# generate the freq range key.
def getFreqRange(msg):
    fmin = msg['mPar']['fStart']
    fmax = msg['mPar']['fStop']
    return freqRange(fmin,fmax)

def freqRange(fmin,fmax):
    return str(int(fmin))+":"+str(int(fmax))
    

def getDataTypeLength(dataType):
    if dataType == "Binary - float32":
        return 4
    elif dataType == "Binary - int8":
        return 1
    else:
        return 1

# Read ascii from a file descriptor.
def readAsciiFromFile(fileDesc):
    csvValues = ""
    while True:
        char = fileDesc.read(1)
        if char == "[":
            csvValues += "["
            break
    while True:
        char = fileDesc.read(1)
        csvValues += char
        if char == "]":
            break
    return csvValues


def readDataFromFileDesc(fileDesc,dataType, count):
    if dataType != "ASCII" :
        dataTypeLength = getDataTypeLength(dataType)
        if fileDesc != None:
            dataBytes = fileDesc.read(dataTypeLength*count)
    else:
        dataBytes = readAsciiFromFile(fileDesc)
    return dataBytes


def put_data(jsonString, headerLength, filedesc):
    """
    put data in the database. jsonString starts with {. If filedesc is None
    then the data part of the message is appended to the message (immediately follows it).
    Otherwise, the data is read from filedesc.
    """
    messageBytes = None
    start_time = time.time()

    if filedesc == None:
       # We are not reading from a file:
       # Assume we are given the message in the string with the data
       # tacked at the end of it.
       jsonStringBytes = jsonString[0:headerLength]
    else:
        jsonStringBytes = jsonString

    print jsonStringBytes
    jsonData = json.loads(jsonStringBytes)
        
    locationPosts = db.locationMessages
    systemPosts = db.systemMessages
    dataPosts = db.dataMessages
    if jsonData['Type'] == "Sys":
       if "Cal" in jsonData:
            calStr = jsonData["Cal"]
            # Ugly!! Need to fix this.
            if calStr != "N/A" :
                n = jsonData["Cal"]['mPar']['n']
                nM = jsonData["Cal"]["nM"]
                sensorId = jsonData[SENSOR_ID]
                if n*nM != 0 :
                   dataType = jsonData["Cal"]["DataType"]
                   lengthToRead = n*nM
                   if filedesc != None:
                        messageBytes = readDataFromFileDesc(filedesc,dataType,lengthToRead)
                   else:
                        messageBytes = jsonString[headerLength:]
                fs = gridfs.GridFS(db,jsonData[SENSOR_ID] + "/data")
                key = fs.put(messageBytes)
                jsonData["Cal"]["dataKey"] = str(key)
       systemPosts.ensure_index([('t',pymongo.DESCENDING)])
       systemPosts.insert(jsonData)
       end_time = time.time()
       print "Insertion time " + str(end_time-start_time)
    elif jsonData['Type'] == "Loc" :
       print(json.dumps(jsonData,sort_keys=True, indent=4))
       sensorId = jsonData[SENSOR_ID]
       t = jsonData['t']
       lat = jsonData["Lat"]
       lon = jsonData["Lon"]
       alt = jsonData["Alt"]
       query = {SENSOR_ID:sensorId, "Lat" : lat , "Lon":lon,"Alt": alt}
       locMsg = locationPosts.find_one(query)
       if locMsg != None:
            print "Location Post already exists - not updating "
            return
       (to_zone,timeZoneName) = timezone.getLocalTimeZoneFromGoogle(t,lat,lon)
       # If google returned null, then override with local information
       if to_zone == None :
            if TIME_ZONE_KEY in jsonData:
                to_zone = jsonData[TIME_ZONE_KEY]
            else:
                print "ERROR: Unable to determine timeZone"
                return
       else :
          jsonData[TIME_ZONE_KEY] = to_zone
       objectId = locationPosts.insert(jsonData)
       db.locationMessages.ensure_index([('t',pymongo.DESCENDING)])
       #post = {SENSOR_ID:sensorId, "id":str(objectId)}
       end_time = time.time()
       print "Insertion time " + str(end_time-start_time)
    elif jsonData['Type'] == "Data" :
       sensorId = jsonData[SENSOR_ID]
       freqRange = getFreqRange(jsonData)
       jsonData['freqRange'] = freqRange
       lastSystemPost = systemPosts.find_one({SENSOR_ID:sensorId,"t":{"$lte":jsonData['t']}})
       lastLocationPost = locationPosts.find_one({SENSOR_ID:sensorId,"t":{"$lte":jsonData['t']}})
       if lastLocationPost == None or lastSystemPost == None :
           raise Exception("Location post or system post not found for " + sensorId)
       timeZone = lastLocationPost[TIME_ZONE_KEY]
       #record the location message associated with the data.
       jsonData["locationMessageId"] =  str(lastLocationPost['_id'])
       jsonData["systemMessageId"] = str(lastSystemPost['_id'])
       # prev data message.
       lastSeenDataMessageSeqno = db.lastSeenDataMessageSeqno.find_one({SENSOR_ID:sensorId})
       #update the seqno
       if lastSeenDataMessageSeqno == None:
            seqNo = 1
            db.lastSeenDataMessageSeqno.insert({SENSOR_ID:sensorId,"seqNo":seqNo})
       else :
            seqNo = lastSeenDataMessageSeqno["seqNo"] + 1 
            lastSeenDataMessageSeqno["seqNo"] = seqNo
            db.lastSeenDataMessageSeqno.update({"_id": lastSeenDataMessageSeqno["_id"]},{"$set":lastSeenDataMessageSeqno}, upsert=False)

       jsonData["seqNo"] = seqNo
       nM = int(jsonData["nM"])
       n = int(jsonData["mPar"]["n"])
       lengthToRead = n*nM
       dataType = jsonData["DataType"]
       if filedesc != None:
            messageBytes = readDataFromFileDesc(filedesc,dataType,lengthToRead)
       else:
            messageBytes = jsonString[headerLength:]
       fs = gridfs.GridFS(db,jsonData[SENSOR_ID] + "/data")
       key = fs.put(messageBytes)
       jsonData['dataKey'] =  str(key)
       cutoff = jsonData["wnI"] + 2
       jsonData["cutoff"] = cutoff
       db.dataMessages.ensure_index([('t',pymongo.ASCENDING),('seqNo',pymongo.ASCENDING)])
       powerVal = np.array(np.zeros(n*nM))
       maxPower = -1000
       minPower = 1000
       if jsonData["mType"] == "FFT-Power" :
          occupancyCount=[0 for i in range(0,nM)]
          #unpack the power array.
          if dataType == "Binary - int8":
              for i in range(0,lengthToRead):
                    powerVal[i] = struct.unpack('b',messageBytes[i:i+1])[0]
                    maxPower = np.maximum(maxPower,powerVal[i])
                    minPower = np.minimum(minPower,powerVal[i])
          powerArray = powerVal.reshape(nM,n)
          for i in range(0,nM):
              occupancyCount[i] = float(len(filter(lambda x: x>=cutoff, powerArray[i,:])))/float(n)
          jsonData['maxOccupancy'] = roundTo2DecimalPlaces(float(np.max(occupancyCount)))
          jsonData['meanOccupancy'] = roundTo2DecimalPlaces(float(np.mean(occupancyCount)))
          jsonData['minOccupancy'] = roundTo2DecimalPlaces(float(np.min(occupancyCount)))
          jsonData['medianOccupancy'] = float(np.median(occupancyCount))
       else:
          if dataType == "ASCII":
              powerVal = eval(messageBytes)
          else :
              for i in range(0,lengthToRead):
                 powerVal[i] = struct.unpack('f',messageBytes[i:i+4])[0]
          maxPower = np.max(powerVal)
          minPower = np.min(powerVal)
          occupancyCount = float(len(filter(lambda x: x>=cutoff, powerVal)))
          jsonData['occupancy'] = occupancyCount / float(len(powerVal))
       jsonData['maxPower'] = maxPower
       jsonData['minPower'] = minPower
       print json.dumps(jsonData,sort_keys=True, indent=4)
       oid = dataPosts.insert(jsonData)
       fStart = jsonData['mPar']['fStart']
       fStop = jsonData['mPar']['fStop']
       if not "sensorFreq" in lastLocationPost:
            lastLocationPost['sensorFreq'] = [freqRange]
       else:
            freqRanges = lastLocationPost['sensorFreq']
            if not freqRange in freqRanges:
                freqRanges.append(freqRange)
            lastLocationPost['sensorFreq'] = freqRanges
       #if we have not registered the first data message in the location post, update it.
       if not 'firstDataMessageId' in lastLocationPost :
          lastLocationPost['firstDataMessageId'] = str(oid)
          lastLocationPost['lastDataMessageId'] = str(oid)
          locationPosts.update({"_id": lastLocationPost["_id"]}, {"$set":lastLocationPost}, upsert=False)
       else :
          lastLocationPost['lastDataMessageId'] = str(oid)
          locationPosts.update({"_id": lastLocationPost["_id"]}, {"$set":lastLocationPost}, upsert=False)
       #post = {SENSOR_ID:sensorId, "id":str(oid), "t":jsonData["t"]}
       end_time = time.time()
       print "Insertion time " + str(end_time-start_time)



def put_data_from_file(filename):
    """
    Read data from a file and put it into the database.
    """
    f = open(filename)
    while True:
        start_time = time.time()
        headerLengthStr = ""
        while True:
            c = f.read(1)
            if c == "" :
                print "Done reading file"
                return
            if c == '\r':
                if headerLengthStr != "":
                    break
            elif c == '\n':
                if headerLengthStr != "":
                    break
            else:
                headerLengthStr = headerLengthStr + c
        print "headerLengthStr = " , headerLengthStr
        jsonHeaderLength = int(headerLengthStr.rstrip())
        jsonStringBytes = f.read(jsonHeaderLength)
        put_data(jsonStringBytes,jsonHeaderLength,f)

def putDataFromFile(filename):
    f = open(filename)
    while True:
        jsonHeaderLengthStr = f.read(4)
        if jsonHeaderLengthStr == "":
            print "End of stream"
            break
        jsonHeaderLength = struct.unpack('i',jsonHeaderLengthStr[0:4])[0]
        jsonStringBytes = f.read(jsonHeaderLength)
        put_data(jsonStringBytes,jsonHeaderLength,f)


def put_message(message):
    """
    Read data from a message string
    """
    index = message.index("{")
    lengthString = message[0:index - 1].rstrip()
    messageLength = int(lengthString)
    print messageLength
    put_data(message[index:],messageLength,None)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process command line args')
    parser.add_argument('-data',help='Filename with readings')
    args = parser.parse_args()
    filename = args.data
    put_data_from_file(filename)
    # Michael's buggy data.
    #putDataFromFile(filename)


