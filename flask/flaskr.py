import flask
from flask import Flask, request, abort, make_response
from flask import jsonify
import random
from random import randint
import struct
import json
import pymongo
import numpy as np
import os
from json import JSONEncoder
from pymongo import MongoClient
from bson.json_util import dumps
from bson.objectid import ObjectId
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import time
import urlparse
import gridfs
import ast
import pytz
import timezone
import png
import populate_db
import sys
from flask_sockets import Sockets
import gevent
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
from io import BytesIO
import binascii
from Queue import Queue
import sets
import traceback
import GenerateZipFileForDownload
import util
import msgutils




sessions = {}
secureSessions = {}
gwtSymbolMap = {}

# move these to another module
sensordata = {}
lastDataMessage = {}
lastdataseen = {}

peakDetection = True
launchedFromMain = False
app = Flask(__name__, static_url_path="")
sockets = Sockets(app)
random.seed(10)
mongodb_host = os.environ.get('DB_PORT_27017_TCP_ADDR', 'localhost')
client = MongoClient(mongodb_host)
db = client.spectrumdb
debug = True
HOURS_PER_DAY = 24
MINUTES_PER_DAY = HOURS_PER_DAY * 60
SECONDS_PER_DAY = MINUTES_PER_DAY * 60
MILISECONDS_PER_DAY = SECONDS_PER_DAY * 1000
UNDER_CUTOFF_COLOR = '#D6D6DB'
OVER_CUTOFF_COLOR = '#000000'
SENSOR_ID = "SensorID"
TIME_ZONE_KEY = "timeZone"
SECONDS_PER_FRAME = 0.1


flaskRoot = os.environ['SPECTRUM_BROWSER_HOME'] + "/flask/"



######################################################################################
# Internal functions (not exported as web services).
######################################################################################



class MyByteBuffer:

    def __init__(self, ws):
        self.ws = ws
        self.queue = Queue()
        self.buf = BytesIO()


    def readFromWebSocket(self):
        dataAscii = self.ws.receive()
        if dataAscii != None:
            data = binascii.a2b_base64(dataAscii)
            # print data
            if data != None:
                bio = BytesIO(data)
                bio.seek(0)
                self.queue.put(bio)
        return

    def read(self, size):
        val = self.buf.read(size)
        if val == "" :
            if self.queue.empty():
                self.readFromWebSocket()
                self.buf = self.queue.get()
                val = self.buf.read(size)
            else:
                self.buf = self.queue.get()
                val = self.buf.read(size)
        return val

    def readByte(self):
        val = self.read(1)
        retval = struct.unpack(">b", val)[0]
        return retval

    def readChar(self):
        val = self.read(1)
        return val

    def size(self):
        return self.size


def checkSessionId(sessionId):
    if debug :
        return True
    elif sessions[request.remote_addr] == None :
        return False
    elif sessions[request.remote_addr] != sessionId :
        return False
    return True


def getMaxMinFreq(msg):
    return (msg["mPar"]["fStop"], msg["mPar"]["fStart"])



def getNextAcquisition(msg):
    query = {SENSOR_ID: msg[SENSOR_ID], "t":{"$gt": msg["t"]}, "freqRange":msg['freqRange']}
    return db.dataMessages.find_one(query)

def getPrevAcquisition(msg):
    query = {SENSOR_ID: msg[SENSOR_ID], "t":{"$lt": msg["t"]}, "freqRange":msg["freqRange"]}
    cur = db.dataMessages.find(query)
    if cur == None or cur.count() == 0:
        return None
    sortedCur = cur.sort('t', pymongo.DESCENDING).limit(10)
    return sortedCur.next()

def getPrevDayBoundary(msg):
    prevMsg = getPrevAcquisition(msg)
    if prevMsg == None:
        locationMessage = msgutils.getLocationMessage(msg)
        return  timezone.getDayBoundaryTimeStampFromUtcTimeStamp(msg['t'], locationMessage[TIME_ZONE_KEY])
    locationMessage = msgutils.getLocationMessage(prevMsg)
    timeZone = locationMessage[TIME_ZONE_KEY]
    return timezone.getDayBoundaryTimeStampFromUtcTimeStamp(prevMsg['t'], timeZone)

def getNextDayBoundary(msg):
    nextMsg = getNextAcquisition(msg)
    if nextMsg == None:
        locationMessage = msgutils.getLocationMessage(msg)
        return  timezone.getDayBoundaryTimeStampFromUtcTimeStamp(msg['t'], locationMessage[TIME_ZONE_KEY])
    locationMessage = msgutils.getLocationMessage(nextMsg)
    timeZone = locationMessage[TIME_ZONE_KEY]
    nextDayBoundary = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(nextMsg['t'], timeZone)
    if debug:
        thisDayBoundary = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(msg['t'], locationMessage[TIME_ZONE_KEY])
        print "getNextDayBoundary: dayBoundary difference ", (nextDayBoundary - thisDayBoundary) / 60 / 60
    return nextDayBoundary

# get minute index offset from given time in seconds.
# startTime is the starting time from which to compute the offset.
def getIndex(time, startTime) :
    return int (float(time - startTime) / float(60))


def generateOccupancyForFFTPower(msg, fileNamePrefix):
    measurementDuration = msg["mPar"]["td"]
    nM = msg['nM']
    n = msg['mPar']['n']
    cutoff = msg['cutoff']
    miliSecondsPerMeasurement = float(measurementDuration * 1000) / float(nM)
    spectrogramData = msgutils.getData(msg)
    # Generate the occupancy stats for the acquisition.
    occupancyCount = [0 for i in range(0, nM)]
    for i in range(0, nM):
        occupancyCount[i] = util.roundTo3DecimalPlaces(float(len(filter(lambda x: x >= cutoff, spectrogramData[i, :]))) / float(n) * 100)
    timeArray = [i * miliSecondsPerMeasurement for i in range(0, nM)]
    minOccupancy = np.minimum(occupancyCount)
    maxOccupancy = np.maximum(occupancyCount)
    plt.figure(figsize=(6, 4))
    plt.axes([0, measurementDuration * 1000, minOccupancy, maxOccupancy])
    plt.xlim([0, measurementDuration * 1000])
    plt.plot(timeArray, occupancyCount, "g.")
    plt.xlabel("Time (ms) since start of acquisition")
    plt.ylabel("Band Occupancy (%)")
    plt.title("Band Occupancy; Cutoff : " + str(cutoff))
    occupancyFilePath = util.getPath("static/generated/") + fileNamePrefix + '.occupancy.png'
    plt.savefig(occupancyFilePath)
    plt.clf()
    plt.close()
    # plt.close('all')
    return  fileNamePrefix + ".occupancy.png"

def trimSpectrumToSubBand(msg, subBandMinFreq, subBandMaxFreq):
    data = msgutils.getData(msg)
    n = msg["mPar"]["n"]
    nM = msg["nM"]
    minFreq = msg["mPar"]["fStart"]
    maxFreq = msg["mPar"]["fStop"]
    freqRangePerReading = float(maxFreq - minFreq) / float(n)
    endReadingsToIgnore = int((maxFreq - subBandMaxFreq) / freqRangePerReading)
    topReadingsToIgnore = int((subBandMinFreq - minFreq) / freqRangePerReading)
    powerArray = np.array([data[i] for i in range(topReadingsToIgnore, n - endReadingsToIgnore)])
    # util.debugPrint("Length " + str(len(powerArray)))
    return powerArray


def computeDailyMaxMinMeanMedianStatsForSweptFreq(cursor, subBandMinFreq, subBandMaxFreq):
    meanOccupancy = 0
    minOccupancy = 10000
    maxOccupancy = -1
    occupancy = []
    n = 0
    for msg in cursor:
        cutoff = msg["cutoff"]
        powerArray = trimSpectrumToSubBand(msg, subBandMinFreq, subBandMaxFreq)
        msgOccupancy = float(len(filter(lambda x: x >= cutoff, powerArray))) / float(len(powerArray))
        occupancy.append(msgOccupancy)

    maxOccupancy = float(np.max(occupancy))
    minOccupancy = float(np.min(occupancy))
    meanOccupancy = float(np.mean(occupancy))
    medianOccupancy = float(np.median(occupancy))
    retval = (n, subBandMaxFreq, subBandMinFreq, cutoff, \
        {"maxOccupancy":util.roundTo3DecimalPlaces(maxOccupancy), "minOccupancy":util.roundTo3DecimalPlaces(minOccupancy), \
        "meanOccupancy":util.roundTo3DecimalPlaces(meanOccupancy), "medianOccupancy":util.roundTo3DecimalPlaces(medianOccupancy)})
    util.debugPrint(retval)
    return retval

# Compute the daily max min and mean stats. The cursor starts on a day
# boundary and ends on a day boundary.
def computeDailyMaxMinMeanStats(cursor):
    util.debugPrint("computeDailyMaxMinMeanStats")
    meanOccupancy = 0
    minOccupancy = 10000
    maxOccupancy = -1
    nReadings = cursor.count()
    print "nreadings" , nReadings
    if nReadings == 0:
        util.debugPrint ("zero count")
        return None
    for msg in cursor:
        n = msg["mPar"]["n"]
        minFreq = msg["mPar"]["fStart"]
        maxFreq = msg["mPar"]["fStop"]
        cutoff = msg["cutoff"]
        if msg["mType"] == "FFT-Power" :
            maxOccupancy = np.maximum(maxOccupancy, msg["maxOccupancy"])
            minOccupancy = np.minimum(minOccupancy, msg["minOccupancy"])
            meanOccupancy = meanOccupancy + msg["meanOccupancy"]
        else:
            maxOccupancy = np.maximum(maxOccupancy, msg["occupancy"])
            minOccupancy = np.minimum(maxOccupancy, msg["occupancy"])
            meanOccupancy = meanOccupancy + msg["occupancy"]
    meanOccupancy = float(meanOccupancy) / float(nReadings)
    return (n, maxFreq, minFreq, cutoff, \
        {"maxOccupancy":util.roundTo3DecimalPlaces(maxOccupancy), "minOccupancy":util.roundTo3DecimalPlaces(minOccupancy), \
        "meanOccupancy":util.roundTo3DecimalPlaces(meanOccupancy)})

def generateSingleDaySpectrogramAndOccupancyForSweptFrequency(msg, sessionId, startTime, fstart, fstop, subBandMinFreq, subBandMaxFreq):
    try :
        locationMessage = msgutils.getLocationMessage(msg)
        tz = locationMessage[TIME_ZONE_KEY]
        startTimeUtc = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(startTime, tz)
        startMsg = db.dataMessages.find_one({SENSOR_ID:msg[SENSOR_ID], "t":{"$gte":startTimeUtc}, \
                "freqRange":populate_db.freqRange(fstart, fstop)})
        if startMsg == None:
            util.debugPrint("Not found")
            abort(404)
        if startMsg['t'] - startTimeUtc > SECONDS_PER_DAY:
            util.debugPrint("Not found - outside day boundary")
            abort(404)

        msg = startMsg
        sensorId = msg[SENSOR_ID]
        noiseFloor = msg["wnI"]
        powerValues = trimSpectrumToSubBand(msg, subBandMinFreq, subBandMaxFreq)
        vectorLength = len(powerValues)
        cutoff = int(request.args.get("cutoff", msg['cutoff']))
        spectrogramFile = sessionId + "/" + sensorId + "." + str(startTimeUtc) + "." + str(cutoff) + "." + str(subBandMinFreq) + "." + str(subBandMaxFreq)
        spectrogramFilePath = util.getPath("static/generated/") + spectrogramFile
        powerVal = np.array([cutoff for i in range(0, MINUTES_PER_DAY * vectorLength)])
        spectrogramData = powerVal.reshape(vectorLength, MINUTES_PER_DAY)
        # artificial power value when sensor is off.
        sensorOffPower = np.transpose(np.array([2000 for i in range(0, vectorLength)]))

        prevMessage = getPrevAcquisition(msg)

        if prevMessage == None:
            util.debugPrint ("prevMessage not found")
            prevMessage = msg
            prevAcquisition = sensorOffPower
        else:
            prevAcquisitionTime = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(prevMessage['t'], tz)
            util.debugPrint ("prevMessage[t] " + str(prevMessage['t']) + " msg[t] " + str(msg['t']) + " prevDayBoundary " + str(prevAcquisitionTime))
            prevAcquisition = np.transpose(np.array(trimSpectrumToSubBand(prevMessage, subBandMinFreq, subBandMaxFreq)))
        occupancy = []
        timeArray = []
        maxpower = -1000
        minpower = 1000
        while True:
            data = trimSpectrumToSubBand(msg, subBandMinFreq, subBandMaxFreq)
            acquisition = trimSpectrumToSubBand(msg, subBandMinFreq, subBandMaxFreq)
            minpower = np.minimum(minpower, msg['minPower'])
            maxpower = np.maximum(maxpower, msg['maxPower'])
            if prevMessage['t1'] != msg['t1']:
                 # GAP detected so fill it with sensorOff
                print "Gap generated"
                for i in range(getIndex(prevMessage["t"], startTimeUtc), getIndex(msg["t"], startTimeUtc)):
                    spectrogramData[:, i] = sensorOffPower
            elif prevMessage["t"] > startTimeUtc:
                # Prev message is the same tstart and prevMessage is in the range of interest.
                # Sensor was not turned off.
                # fill forward using the prev acquisition.
                for i in range(getIndex(prevMessage['t'], startTimeUtc), getIndex(msg["t"], startTimeUtc)):
                    spectrogramData[:, i] = prevAcquisition
            else :
                # forward fill from prev acquisition to the start time
                # with the previous power value
                for i in range(0, getIndex(msg["t"], startTimeUtc)):
                    spectrogramData[:, i] = prevAcquisition
            colIndex = getIndex(msg['t'], startTimeUtc)
            spectrogramData[:, colIndex] = acquisition
            timeArray.append(float(msg['t'] - startTimeUtc) / float(3600))
            occupancy.append(util.roundTo1DecimalPlaces(msg['occupancy']))
            prevMessage = msg
            prevAcquisition = acquisition
            msg = getNextAcquisition(msg)
            if msg == None:
                lastMessage = prevMessage
                for i in range(getIndex(prevMessage["t"], startTimeUtc), MINUTES_PER_DAY):
                    spectrogramData[:, i] = sensorOffPower
                break
            elif msg['t'] - startTimeUtc > SECONDS_PER_DAY:
                for i in range(getIndex(prevMessage["t"], startTimeUtc), MINUTES_PER_DAY):
                    spectrogramData[:, i] = prevAcquisition
                lastMessage = prevMessage
                break

        # generate the spectrogram as an image.
        if not os.path.exists(spectrogramFilePath + ".png"):
           fig = plt.figure(figsize=(6, 4))
           frame1 = plt.gca()
           frame1.axes.get_xaxis().set_visible(False)
           frame1.axes.get_yaxis().set_visible(False)
           cmap = plt.cm.spectral
           cmap.set_under(UNDER_CUTOFF_COLOR)
           cmap.set_over(OVER_CUTOFF_COLOR)
           dirname = util.getPath("static/generated/") + sessionId
           if not os.path.exists(dirname):
              os.makedirs(dirname)
           fig = plt.imshow(spectrogramData, interpolation='none', origin='lower', aspect='auto', vmin=cutoff, vmax=maxpower, cmap=cmap)
           print "Generated fig"
           plt.savefig(spectrogramFilePath + '.png', bbox_inches='tight', pad_inches=0, dpi=100)
           plt.clf()
           plt.close()
        else:
           util.debugPrint("File exists - not generating image")

        util.debugPrint("FileName : " + spectrogramFilePath + ".png")

        util.debugPrint("Reading " + spectrogramFilePath + ".png")
        # get the size of the generated png.
        reader = png.Reader(filename=spectrogramFilePath + ".png")
        (width, height, pixels, metadata) = reader.read()

        util.debugPrint("width = " + str(width) + " height = " + str(height))

        # generate the colorbar as a separate image.
        if not os.path.exists(spectrogramFilePath + ".cbar.png") :
          norm = mpl.colors.Normalize(vmin=cutoff, vmax=maxpower)
          fig = plt.figure(figsize=(4, 10))
          ax1 = fig.add_axes([0.0, 0, 0.1, 1])
          mpl.colorbar.ColorbarBase(ax1, cmap=cmap, norm=norm, orientation='vertical')
          plt.savefig(spectrogramFilePath + '.cbar.png', bbox_inches='tight', pad_inches=0, dpi=50)
          plt.clf()
          plt.close()
        else:
          util.debugPrint(spectrogramFilePath + ".cbar.png" + " exists -- not generating")


        localTime, tzName = timezone.getLocalTime(startTimeUtc, tz)

        # step back for 24 hours.
        prevAcquisitionTime = getPrevDayBoundary(startMsg)
        nextAcquisitionTime = getNextDayBoundary(lastMessage)


        result = {"spectrogram": spectrogramFile + ".png", \
            "cbar":spectrogramFile + ".cbar.png", \
            "maxPower":maxpower, \
            "cutoff":cutoff, \
            "noiseFloor" : noiseFloor, \
            "minPower":minpower, \
            "tStartTimeUtc": startTimeUtc, \
            TIME_ZONE_KEY : tzName, \
            "timeDelta":HOURS_PER_DAY, \
            "prevAcquisition" : prevAcquisitionTime , \
            "nextAcquisition" : nextAcquisitionTime , \
            "formattedDate" : timezone.formatTimeStampLong(startTimeUtc, tz), \
            "image_width":float(width), \
            "image_height":float(height)}

        util.debugPrint(result)
        result["timeArray"] = timeArray
        result["occupancyArray"] = occupancy
        return jsonify(result)
    except  :
         print "Unexpected error:", sys.exc_info()[0]
         raise

# Generate a spectrogram and occupancy plot for FFTPower data starting at msg.
def generateSingleAcquisitionSpectrogramAndOccupancyForFFTPower(msg, sessionId):
    startTime = msg['t']
    fs = gridfs.GridFS(db, msg[SENSOR_ID] + "/data")
    sensorId = msg[SENSOR_ID]
    messageBytes = fs.get(ObjectId(msg["dataKey"])).read()
    util.debugPrint("Read " + str(len(messageBytes)))
    cutoff = int(request.args.get("cutoff", msg['cutoff']))
    leftBound = float(request.args.get("leftBound", 0))
    rightBound = float(request.args.get("rightBound", 0))
    spectrogramFile = sessionId + "/" + sensorId + "." + str(startTime) + "." + str(leftBound) + "." + str(rightBound) + "." + str(cutoff)
    spectrogramFilePath = util.getPath("static/generated/") + spectrogramFile
    if leftBound < 0 or rightBound < 0 :
        util.debugPrint("Bounds to exlude must be >= 0")
        return None
    measurementDuration = msg["mPar"]["td"]
    miliSecondsPerMeasurement = float(measurementDuration * 1000) / float(msg['nM'])
    leftColumnsToExclude = int(leftBound / miliSecondsPerMeasurement)
    rightColumnsToExclude = int(rightBound / miliSecondsPerMeasurement)
    if leftColumnsToExclude + rightColumnsToExclude >= msg['nM']:
        util.debugPrint("leftColumnToExclude " + str(leftColumnsToExclude) + " rightColumnsToExclude " + str(rightColumnsToExclude))
        return None
    util.debugPrint("LeftColumns to exclude " + str(leftColumnsToExclude) + " right columns to exclude " + str(rightColumnsToExclude))
    noiseFloor = msg['wnI']
    nM = msg["nM"] - leftColumnsToExclude - rightColumnsToExclude
    n = msg["mPar"]["n"]
    locationMessage = msgutils.getLocationMessage(msg)
    lengthToRead = n * msg["nM"]
    # Read the power values
    power = msgutils.getData(msg)
    powerVal = power[n * leftColumnsToExclude:lengthToRead - n * rightColumnsToExclude]
    minTime = float(leftColumnsToExclude * miliSecondsPerMeasurement) / float(1000)
    spectrogramData = powerVal.reshape(nM, n)
    # generate the spectrogram as an image.
    if not os.path.exists(spectrogramFilePath + ".png"):
       dirname = util.getPath("static/generated/") + sessionId
       if not os.path.exists(dirname):
           os.makedirs(util.getPath("static/generated/") + sessionId)
       fig = plt.figure(figsize=(6, 4))
       frame1 = plt.gca()
       frame1.axes.get_xaxis().set_visible(False)
       frame1.axes.get_yaxis().set_visible(False)
       minpower = msg['minPower']
       maxpower = msg['maxPower']
       cmap = plt.cm.spectral
       cmap.set_under(UNDER_CUTOFF_COLOR)
       fig = plt.imshow(np.transpose(spectrogramData), interpolation='none', origin='lower', aspect="auto", vmin=cutoff, vmax=maxpower, cmap=cmap)
       print "Generated fig"
       plt.savefig(spectrogramFilePath + '.png', bbox_inches='tight', pad_inches=0, dpi=100)
       plt.clf()
       plt.close()
    else :
       util.debugPrint("File exists -- not regenerating")

    # generate the occupancy data for the measurement.
    occupancyCount = [0 for i in range(0, nM)]
    for i in range(0, nM):
        occupancyCount[i] = util.roundTo1DecimalPlaces(float(len(filter(lambda x: x >= cutoff, spectrogramData[i, :]))) / float(n) * 100)
    timeArray = [int((i + leftColumnsToExclude) * miliSecondsPerMeasurement)  for i in range(0, nM)]

    # get the size of the generated png.
    reader = png.Reader(filename=spectrogramFilePath + ".png")
    (width, height, pixels, metadata) = reader.read()

    if not os.path.exists(spectrogramFilePath + ".cbar.png"):
       # generate the colorbar as a separate image.
       norm = mpl.colors.Normalize(vmin=cutoff, vmax=maxpower)
       fig = plt.figure(figsize=(4, 10))
       ax1 = fig.add_axes([0.0, 0, 0.1, 1])
       mpl.colorbar.ColorbarBase(ax1, cmap=cmap, norm=norm, orientation='vertical')
       plt.savefig(spectrogramFilePath + '.cbar.png', bbox_inches='tight', pad_inches=0, dpi=50)
       plt.clf()
       plt.close()

    nextAcquisition = getNextAcquisition(msg)
    prevAcquisition = getPrevAcquisition(msg)

    if nextAcquisition != None:
        nextAcquisitionTime = nextAcquisition['t']
    else:
        nextAcquisitionTime = msg['t']

    if prevAcquisition != None:
        prevAcquisitionTime = prevAcquisition['t']
    else:
        prevAcquisitionTime = msg['t']

    tz = locationMessage[TIME_ZONE_KEY]

    timeDelta = msg["mPar"]["td"] - float(leftBound) / float(1000) - float(rightBound) / float(1000)

    result = {"spectrogram": spectrogramFile + ".png", \
            "cbar":spectrogramFile + ".cbar.png", \
            "maxPower":msg['maxPower'], \
            "cutoff":cutoff, \
            "noiseFloor" : noiseFloor, \
            "minPower":msg['minPower'], \
            "maxFreq":msg["mPar"]["fStop"], \
            "minFreq":msg["mPar"]["fStart"], \
            "minTime": minTime, \
            "timeDelta": timeDelta, \
            "prevAcquisition" : prevAcquisitionTime , \
            "nextAcquisition" : nextAcquisitionTime , \
            "formattedDate" : timezone.formatTimeStampLong(msg['t'] + leftBound , tz), \
            "image_width":float(width), \
            "image_height":float(height)}
    # see if it is well formed.
    print dumps(result, indent=4)
    # Now put in the occupancy data
    result["timeArray"] = timeArray
    result["occupancyArray"] = occupancyCount
    return jsonify(result)

def generateSpectrumForSweptFrequency(msg, sessionId, minFreq, maxFreq):
    try:
        spectrumData = trimSpectrumToSubBand(msg, minFreq, maxFreq)
        nSteps = len(spectrumData)
        freqDelta = float(maxFreq - minFreq) / float(1E6) / nSteps
        freqArray = [ float(minFreq) / float(1E6) + i * freqDelta for i in range(0, nSteps)]
        fig = plt.figure(figsize=(6, 4))
        plt.scatter(freqArray, spectrumData)
        plt.xlabel("Freq (MHz)")
        plt.ylabel("Power (dBm)")
        locationMessage = db.locationMessages.find_one({"_id": ObjectId(msg["locationMessageId"])})
        t = msg["t"]
        tz = locationMessage[TIME_ZONE_KEY]
        plt.title("Spectrum at " + timezone.formatTimeStampLong(t, tz))
        spectrumFile = sessionId + "/" + msg[SENSOR_ID] + "." + str(msg['t']) + "." + str(minFreq) + "." + str(maxFreq) + ".spectrum.png"
        spectrumFilePath = util.getPath("static/generated/") + spectrumFile
        plt.savefig(spectrumFilePath, pad_inches=0, dpi=100)
        plt.clf()
        plt.close()
        # plt.close("all")
        retval = {"spectrum" : spectrumFile }
        util.debugPrint(retval)
        return jsonify(retval)
    except:
        print "Unexpected error:", sys.exc_info()[0]
        print sys.exc_info()
        traceback.print_exc()
        raise


# generate the spectrum for a FFT power acquisition at a given milisecond offset.
# from the start time.
def generateSpectrumForFFTPower(msg, milisecOffset, sessionId):
    startTime = msg["t"]
    nM = msg["nM"]
    n = msg["mPar"]["n"]
    measurementDuration = msg["mPar"]["td"]
    miliSecondsPerMeasurement = float(measurementDuration * 1000) / float(nM)
    powerVal = msgutils.getData(msg)
    spectrogramData = np.transpose(powerVal.reshape(nM, n))
    col = milisecOffset / miliSecondsPerMeasurement
    util.debugPrint("Col = " + str(col))
    spectrumData = spectrogramData[:, col]
    maxFreq = msg["mPar"]["fStop"]
    minFreq = msg["mPar"]["fStart"]
    nSteps = len(spectrumData)
    freqDelta = float(maxFreq - minFreq) / float(1E6) / nSteps
    freqArray = [ float(minFreq) / float(1E6) + i * freqDelta for i in range(0, nSteps)]
    fig = plt.figure(figsize=(6, 4))
    plt.scatter(freqArray, spectrumData)
    plt.xlabel("Freq (MHz)")
    plt.ylabel("Power (dBm)")
    locationMessage = db.locationMessages.find_one({"_id": ObjectId(msg["locationMessageId"])})
    t = msg["t"] + milisecOffset / float(1000)
    tz = locationMessage[TIME_ZONE_KEY]
    plt.title("Spectrum at " + timezone.formatTimeStampLong(t, tz))
    spectrumFile = sessionId + "/" + msg[SENSOR_ID] + "." + str(startTime) + "." + str(milisecOffset) + ".spectrum.png"
    spectrumFilePath = util.getPath("static/generated/") + spectrumFile
    plt.savefig(spectrumFilePath, pad_inches=0, dpi=100)
    plt.clf()
    plt.close()
    # plt.close("all")
    retval = {"spectrum" : spectrumFile }
    util.debugPrint(retval)
    return jsonify(retval)

def generatePowerVsTimeForSweptFrequency(msg, freqHz, sessionId):
    (maxFreq, minFreq) = getMaxMinFreq(msg)
    locationMessage = msgutils.getLocationMessage(msg)
    timeZone = locationMessage[TIME_ZONE_KEY]
    if freqHz > maxFreq:
        freqHz = maxFreq
    if freqHz < minFreq:
        freqHz = minFreq
    n = msg["mPar"]["n"]
    freqIndex = int(float(freqHz - minFreq) / float(maxFreq - minFreq) * float(n))
    powerArray = []
    timeArray = []
    startTime = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(msg['t'], timeZone)
    while True:
        data = msgutils.getData(msg)
        powerArray.append(data[freqIndex])
        timeArray.append(float(msg['t'] - startTime) / float(3600))
        nextMsg = getNextAcquisition(msg)
        if nextMsg == None:
            break
        elif nextMsg['t'] - startTime > SECONDS_PER_DAY:
            break
        else:
            msg = nextMsg

    fig = plt.figure(figsize=(6, 4))
    plt.xlim([0, 23])
    freqMHz = float(freqHz) / 1E6
    plt.title("Power vs. Time at " + str(freqMHz) + " MHz")
    plt.xlabel("Time from start of day (Hours)")
    plt.ylabel("Power (dBm)")
    plt.xlim([0, 23])
    plt.scatter(timeArray, powerArray)
    spectrumFile = sessionId + "/" + msg[SENSOR_ID] + "." + str(startTime) + "." + str(freqMHz) + ".power.png"
    spectrumFilePath = util.getPath("static/generated/") + spectrumFile
    plt.savefig(spectrumFilePath, pad_inches=0, dpi=100)
    plt.clf()
    plt.close()
    retval = {"powervstime" : spectrumFile }
    util.debugPrint(retval)
    return jsonify(retval)



# Generate power vs. time plot for FFTPower type data.
# given a frequency in MHz
def generatePowerVsTimeForFFTPower(msg, freqHz, sessionId):
    startTime = msg["t"]
    n = msg["mPar"]["n"]
    leftBound = float(request.args.get("leftBound", 0))
    rightBound = float(request.args.get("rightBound", 0))
    if leftBound < 0 or rightBound < 0 :
        util.debugPrint("Bounds to exlude must be >= 0")
        return None
    measurementDuration = msg["mPar"]["td"]
    miliSecondsPerMeasurement = float(measurementDuration * 1000) / float(msg['nM'])
    leftColumnsToExclude = int(leftBound / miliSecondsPerMeasurement)
    rightColumnsToExclude = int(rightBound / miliSecondsPerMeasurement)
    if leftColumnsToExclude + rightColumnsToExclude >= msg['nM']:
        util.debugPrint("leftColumnToExclude " + str(leftColumnsToExclude) + " rightColumnsToExclude " + str(rightColumnsToExclude))
        return None
    nM = msg["nM"] - leftColumnsToExclude - rightColumnsToExclude
    power = msgutils.getData(msg)
    lengthToRead = n * msg["nM"]
    powerVal = power[n * leftColumnsToExclude:lengthToRead - n * rightColumnsToExclude]
    spectrogramData = np.transpose(powerVal.reshape(nM, n))
    maxFreq = msg["mPar"]["fStop"]
    minFreq = msg["mPar"]["fStart"]
    freqDeltaPerIndex = float(maxFreq - minFreq) / float(n)
    row = int((freqHz - minFreq) / freqDeltaPerIndex)
    util.debugPrint("row = " + str(row))
    if  row < 0 :
        util.debugPrint("WARNING: row < 0")
        row = 0
    powerValues = spectrogramData[row, :]
    timeArray = [(leftColumnsToExclude + i) * miliSecondsPerMeasurement for i in range(0, nM)]
    fig = plt.figure(figsize=(6, 4))
    plt.xlim([leftBound, measurementDuration * 1000 - rightBound])
    plt.scatter(timeArray, powerValues)
    freqMHz = float(freqHz) / 1E6
    plt.title("Power vs. Time at " + str(freqMHz) + " MHz")
    spectrumFile = sessionId + "/" + msg[SENSOR_ID] + "." + str(startTime) + "." + str(leftBound) + "." + str(rightBound) \
        + "." + str(freqMHz) + ".power.png"
    spectrumFilePath = util.getPath("static/generated/") + spectrumFile
    plt.xlabel("Time from start of acquistion (ms)")
    plt.ylabel("Power (dBm)")
    plt.savefig(spectrumFilePath, pad_inches=0, dpi=100)
    plt.clf()
    plt.close()
    retval = {"powervstime" : spectrumFile }
    util.debugPrint(retval)
    return jsonify(retval)



######################################################################################

@app.route("/generated/<path:path>", methods=["GET"])
@app.route("/myicons/<path:path>", methods=["GET"])
@app.route("/spectrumbrowser/<path:path>", methods=["GET"])
def getScript(path):
    util.debugPrint("getScript()")
    p = urlparse.urlparse(request.url)
    urlpath = p.path
    return app.send_static_file(urlpath[1:])


@app.route("/", methods=["GET"])
def root():
    util.debugPrint("root()")
    return app.send_static_file("app.html")

@app.route("/spectrumbrowser/getToken", methods=['POST'])
def getToken():
    if not debug:
        sessionId = "guest-" + str(random.randint(1, 1000))
    else :
        sessionId = "guest-" + str(123)
    sessions[request.remote_addr] = sessionId
    return jsonify({"status":"OK", "sessionId":sessionId})

@app.route("/spectrumbrowser/authenticate/<privilege>/<userName>", methods=['POST'])
def authenticate(privilege, userName):
    p = urlparse.urlparse(request.url)
    query = p.query
    print privilege, userName
    if userName == "guest" and privilege == "user":
       if not debug:
            sessionId = "guest-" + str(random.randint(1, 1000))
       else :
            sessionId = "guest-" + str(123)
       sessions[request.remote_addr] = sessionId
       return jsonify({"status":"OK", "sessionId":sessionId}), 200
    elif privilege == "admin" :
        # will need to do some lookup here. Just a place holder for now.
        # For now - give him a session id and just let him through.
       if not debug:
            sessionId = "admin-" + str(random.randint(1, 1000))
       else :
            sessionId = "admin-" + str(123)
       sessions[request.remote_addr] = sessionId
       return jsonify({"status":"OK", "sessionId":sessionId}), 200
    elif privilege == "user" :
       # TODO : look up user password and actually authenticate here.
       return jsonify({"status":"NOK", "sessionId":"0"}), 401
    elif query == "" :
       return jsonify({"status":"NOK", "sessionId":"0"}), 401
    else :
       # q = urlparse.parse_qs(query,keep_blank_values=True)
       # TODO deal with actual logins consult user database etc.
       return jsonify({"status":"NOK", "sessionId":sessionId}), 401


@app.route("/spectrumbrowser/getLocationInfo/<sessionId>", methods=["POST"])
def getLocationInfo(sessionId):
    try:
        print "getLocationInfo"
        if not checkSessionId(sessionId):
            abort(404)
        queryString = "db.locationMessages.find({})"
        util.debugPrint(queryString)
        cur = eval(queryString)
        cur.batch_size(20)
        retval = {}
        locationMessages = []
        sensorIds = sets.Set()
        for c in cur:
            (c["tStartLocalTime"], c["tStartLocalTimeTzName"]) = timezone.getLocalTime(c["t"], c[TIME_ZONE_KEY])
            c["objectId"] = str(c["_id"])
            del c["_id"]
            del c["SensorKey"]
            locationMessages.append(c)
            sensorIds.add(c[SENSOR_ID])
        retval["locationMessages"] = locationMessages
        systemMessages = []
        for sensorId in sensorIds:
            systemMessage = db.systemMessages.find_one({SENSOR_ID:sensorId})
            del systemMessage["_id"]
            systemMessages.append(systemMessage)
        retval["systemMessages"] = systemMessages
        return jsonify(retval)
    except:
        print "Unexpected error:", sys.exc_info()[0]
        print sys.exc_info()
        traceback.print_exc()
        raise


@app.route("/spectrumbrowser/getDailyMaxMinMeanStats/<sensorId>/<startTime>/<dayCount>/<fmin>/<fmax>/<sessionId>", methods=["POST"])
def getDailyStatistics(sensorId, startTime, dayCount, fmin, fmax, sessionId):
    try:
        util.debugPrint("getDailyMaxMinMeanStats : " + sensorId + " " + startTime + " " + dayCount)
        if not checkSessionId(sessionId):
           abort(404)
        subBandMinFreq = int(request.args.get("subBandMinFreq", fmin))
        subBandMaxFreq = int(request.args.get("subBandMaxFreq", fmax))
        tstart = int(startTime)
        ndays = int(dayCount)
        fmin = int(fmin)
        fmax = int(fmax)
        queryString = { SENSOR_ID : sensorId, "t" : {'$gte':tstart}, "freqRange": populate_db.freqRange(fmin, fmax)}
        startMessage = db.dataMessages.find_one(queryString)
        if startMessage == None:
            errorStr = "Start Message Not Found"
            util.debugPrint(errorStr)
            response = make_response(util.formatError(errorStr), 404)
            return response
        locationMessage = msgutils.getLocationMessage(startMessage)
        tZId = locationMessage[TIME_ZONE_KEY]
        if locationMessage == None:
            errorStr = "Location Message Not Found"
            util.debugPrint(errorStr)
            response = make_response(util.formatError(errorStr), 404)
        tmin = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(startMessage['t'], tZId)
        result = {}
        values = {}
        for day in range(0, ndays):
            tstart = tmin + day * SECONDS_PER_DAY
            tend = tstart + SECONDS_PER_DAY
            queryString = { SENSOR_ID : sensorId, "t" : {'$gte':tstart, '$lte': tend}, "freqRange":populate_db.freqRange(fmin, fmax)}
            print queryString
            cur = db.dataMessages.find(queryString)
            cur.batch_size(20)
            if startMessage['mType'] == "FFT-Power":
                stats = computeDailyMaxMinMeanStats(cur)
            else:
                stats = computeDailyMaxMinMeanMedianStatsForSweptFreq(cur, subBandMinFreq, subBandMaxFreq)
            # gap in readings. continue.
            if stats == None:
                continue
            (nChannels, maxFreq, minFreq, cutoff, dailyStat) = stats
            values[day * 24] = dailyStat
        result["tmin"] = tmin
        result["maxFreq"] = maxFreq
        result["minFreq"] = minFreq
        result["cutoff"] = cutoff
        result["channelCount"] = nChannels
        result["startDate"] = timezone.formatTimeStampLong(tmin, tZId)
        result["values"] = values
        util.debugPrint(result)
        return jsonify(result)
    except:
        print "Unexpected error:", sys.exc_info()[0]
        print sys.exc_info()
        traceback.print_exc()
        raise



@app.route("/spectrumbrowser/getDataSummary/<sensorId>/<lat>/<lon>/<alt>/<sessionId>", methods=["POST"])
def getDataSummary(sensorId, lat, lon, alt, sessionId):
    """
    Get the sensor data descriptions for the sensor ID given its location message ID.
    """
    util.debugPrint("getDataSummary")
    try:
        if not checkSessionId(sessionId):
            util.debugPrint("SessionId not found")
            abort(403)
        longitude = float(lon)
        latitude = float(lat)
        alt = float(alt)
        locationMessage = db.locationMessages.find_one({SENSOR_ID:sensorId, "Lon":longitude, "Lat":latitude, "Alt":alt})
        if locationMessage == None:
            util.debugPrint("Location Message not found")
            abort(404)

        locationMessageId = str(locationMessage["_id"])
        # min and specifies the freq band of interest. If nothing is specified or the freq is -1,
        # then all frequency bands are queried.
        minFreq = int (request.args.get("minFreq", "-1"))
        maxFreq = int(request.args.get("maxFreq", "-1"))
        if minFreq != -1 and maxFreq != -1 :
            freqRange = populate_db.freqRange(minFreq, maxFreq)
        else:
            freqRange = None
        # tmin and tmax specify the min and the max values of the time range of interest.
        tmin = request.args.get('minTime', '')
        dayCount = request.args.get('dayCount', '')
        tzId = locationMessage[TIME_ZONE_KEY]
        if freqRange == None:
            if tmin == '' and dayCount == '':
                query = { SENSOR_ID: sensorId, "locationMessageId":locationMessageId }
            elif tmin != ''  and dayCount == '' :
                mintime = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(int(tmin), tzId)
                query = { SENSOR_ID:sensorId, "locationMessageId":locationMessageId, "t" : {'$gte':mintime} }
            else:
                mintime = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(int(tmin), tzId)
                maxtime = mintime + int(dayCount) * SECONDS_PER_DAY
                query = { SENSOR_ID: sensorId, "locationMessageId":locationMessageId, "t": { '$lte':maxtime, '$gte':mintime}  }
        else :
            if tmin == '' and dayCount == '':
                query = { SENSOR_ID: sensorId, "locationMessageId":locationMessageId, "freqRange": freqRange }
            elif tmin != ''  and dayCount == '' :
                mintime = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(int(tmin), tzId)
                query = { SENSOR_ID:sensorId, "locationMessageId":locationMessageId, "t" : {'$gte':mintime}, "freqRange":freqRange }
            else:
                mintime = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(int(tmin), tzId)
                maxtime = mintime + int(dayCount) * SECONDS_PER_DAY
                query = { SENSOR_ID: sensorId, "locationMessageId":locationMessageId, "t": { '$lte':maxtime, '$gte':mintime} , "freqRange":freqRange }

        util.debugPrint(query)
        cur = db.dataMessages.find(query)
        if cur == None:
            errorStr = "No data found"
            response = make_response(util.formatError(errorStr), 404)
            return response
        nreadings = cur.count()
        if nreadings == 0:
            util.debugPrint("No data found. zero cur count.")
            del query['t']
            msg = db.dataMessages.find_one(query)
            if msg != None:
                tStartDayBoundary = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(msg["t"], tzId)
                if dayCount == '':
                    query["t"] = {"$gte":tStartDayBoundary}
                else:
                    maxtime = tStartDayBoundary + int(dayCount) * SECONDS_PER_DAY
                    query["t"] = {"$gte":tStartDayBoundary, "$lte":maxtime}
                cur = db.dataMessages.find(query)
                nreadings = cur.count()
            else :
                errorStr = "No data found"
                response = make_response(util.formatError(errorStr), 404)
                return response
        util.debugPrint("retrieved " + str(nreadings))
        cur.batch_size(20)
        minOccupancy = 10000
        maxOccupancy = -10000
        maxFreq = 0
        minFreq = -1
        meanOccupancy = 0
        minTime = time.time() + 10000
        minLocalTime = time.time() + 10000
        maxTime = 0
        maxLocalTime = 0
        measurementType = "UNDEFINED"
        lastMessage = None
        tStartDayBoundary = 0
        tStartLocalTimeTzName = None
        for msg in cur:
            if tStartDayBoundary == 0 :
                tStartDayBoundary = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(msg["t"], tzId)
                (minLocalTime, tStartLocalTimeTzName) = timezone.getLocalTime(msg['t'], tzId)
            if msg["mType"] == "FFT-Power" :
                minOccupancy = np.minimum(minOccupancy, msg["minOccupancy"])
                maxOccupancy = np.maximum(maxOccupancy, msg["maxOccupancy"])
            else:
                minOccupancy = np.minimum(minOccupancy, msg["occupancy"])
                maxOccupancy = np.maximum(maxOccupancy, msg["occupancy"])
            maxFreq = np.maximum(msg["mPar"]["fStop"], maxFreq)
            if minFreq == -1 :
                minFreq = msg["mPar"]["fStart"]
            else:
                minFreq = np.minimum(msg["mPar"]["fStart"], minFreq)
            if "meanOccupancy" in msg:
                meanOccupancy += msg["meanOccupancy"]
            else:
                meanOccupancy += msg["occupancy"]
            minTime = np.minimum(minTime, msg["t"])
            maxTime = np.maximum(maxTime, msg["t"])
            measurementType = msg["mType"]
            lastMessage = msg
        tz = locationMessage[TIME_ZONE_KEY]
        (tEndReadingsLocalTime, tEndReadingsLocalTimeTzName) = timezone.getLocalTime(lastMessage['t'], tzId)
        tEndDayBoundary = endDayBoundary = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(lastMessage["t"], tzId)
        # now get the global min and max time of the aquistions.
        if 't' in query:
            del query['t']
        cur = db.dataMessages.find(query)
        firstMessage = cur.next()
        cur = db.dataMessages.find(query)
        sortedCur = cur.sort('t', pymongo.DESCENDING).limit(10)
        lastMessage = sortedCur.next()
        tAquisitionStart = firstMessage['t']
        tAquisitionEnd = lastMessage['t']
        tAquisitionStartFormattedTimeStamp = timezone.formatTimeStampLong(tAquisitionStart, tzId)
        tAquisitionEndFormattedTimeStamp = timezone.formatTimeStampLong(tAquisitionEnd, tzId)
        meanOccupancy = meanOccupancy / nreadings
        retval = {"minOccupancy":minOccupancy, \
            "tAquistionStart": tAquisitionStart, \
            "tAquisitionStartFormattedTimeStamp": tAquisitionStartFormattedTimeStamp, \
            "tAquisitionEnd":tAquisitionEnd, \
            "tAquisitionEndFormattedTimeStamp": tAquisitionEndFormattedTimeStamp, \
            "tStartReadings":minTime, \
            "tStartLocalTime": minLocalTime, \
            "tStartLocalTimeTzName" : tStartLocalTimeTzName, \
            "tStartLocalTimeFormattedTimeStamp" : timezone.formatTimeStampLong(minTime, tzId), \
            "tStartDayBoundary":float(tStartDayBoundary), \
            "tEndReadings":float(maxTime), \
            "tEndReadingsLocalTime":float(tEndReadingsLocalTime), \
            "tEndReadingsLocalTimeTzName" : tEndReadingsLocalTimeTzName, \
            "tEndLocalTimeFormattedTimeStamp" : timezone.formatTimeStampLong(maxTime, tzId), \
            "tEndDayBoundary":float(tEndDayBoundary), \
            "maxOccupancy":util.roundTo3DecimalPlaces(maxOccupancy), \
            "meanOccupancy":util.roundTo3DecimalPlaces(meanOccupancy), \
            "maxFreq":maxFreq, \
            "minFreq":minFreq, \
            "measurementType": measurementType, \
            "readingsCount":float(nreadings)}
        print retval
        return jsonify(retval)
    except :
         print "Unexpected error:", sys.exc_info()[0]
         print sys.exc_info()
         traceback.print_exc()



@app.route("/spectrumbrowser/getOneDayStats/<sensorId>/<startTime>/<minFreq>/<maxFreq>/<sessionId>", methods=["POST"])
def getOneDayStats(sensorId, startTime, minFreq, maxFreq, sessionId):
    """
    Get the statistics for a given sensor given a start time for a single day of data.
    The time is rounded to the start of the day boundary.
    """
    minFreq = int(minFreq)
    maxFreq = int(maxFreq)
    freqRange = populate_db.freqRange(minFreq, maxFreq)
    mintime = int(startTime)
    maxtime = mintime + SECONDS_PER_DAY
    query = { SENSOR_ID: sensorId, "t": { '$lte':maxtime, '$gte':mintime}, "freqRange":freqRange  }
    util.debugPrint(query)
    msg = db.dataMessages.find_one(query)
    query = { "_id": ObjectId(msg["locationMessageId"]) }
    locationMessage = db.locationMessages.find_one(query)
    mintime = timezone.getDayBoundaryTimeStampFromUtcTimeStamp(msg["t"], locationMessage[TIME_ZONE_KEY])
    maxtime = mintime + SECONDS_PER_DAY
    query = { SENSOR_ID: sensorId, "t": { '$lte':maxtime, '$gte':mintime} , "freqRange":freqRange }
    cur = db.dataMessages.find(query)
    if cur == None:
        abort(404)
    res = {}
    values = {}
    res["formattedDate"] = timezone.formatTimeStampLong(mintime, locationMessage[TIME_ZONE_KEY])
    for msg in cur:
        channelCount = msg["mPar"]["n"]
        cutoff = msg["cutoff"]
        values[msg["t"] - mintime] = {"t": msg["t"], \
                        "maxPower" : msg["maxPower"], \
                        "minPower" : msg["minPower"], \
                        "maxOccupancy":util.roundTo3DecimalPlaces(msg["maxOccupancy"]), \
                        "minOccupancy":util.roundTo3DecimalPlaces(msg["minOccupancy"]), \
                        "meanOccupancy":util.roundTo3DecimalPlaces(msg["meanOccupancy"]), \
                        "medianOccupancy":util.roundTo3DecimalPlaces(msg["medianOccupancy"])}
    res["channelCount"] = channelCount
    res["cutoff"] = cutoff
    res["values"] = values
    return jsonify(res)


@app.route("/spectrumbrowser/generateSingleAcquisitionSpectrogramAndOccupancy/<sensorId>/<startTime>/<minFreq>/<maxFreq>/<sessionId>", methods=["POST"])
def generateSingleAcquisitionSpectrogram(sensorId, startTime, minFreq, maxFreq, sessionId):
    """ Generate the single acquisiton spectrogram or the daily spectrogram.
        sensorId is the sensor ID of interest.
        The start time is a day boundary timeStamp for swept freq.
        The start time is the time stamp for the data message for FFT power. """
    try:
        if not checkSessionId(sessionId):
            abort(403)
        startTimeInt = int(startTime)
        minfreq = int(minFreq)
        maxfreq = int(maxFreq)
        query = { SENSOR_ID: sensorId}
        msg = db.dataMessages.find_one(query)
        if msg == None:
            util.debugPrint("Sensor ID not found " + sensorId)
            abort(404)
        if msg["mType"] == "FFT-Power":
            query = { SENSOR_ID: sensorId, "t": startTimeInt, "freqRange": populate_db.freqRange(minfreq, maxfreq)}
            util.debugPrint(query)
            msg = db.dataMessages.find_one(query)
            if msg == None:
                errorStr = "Data message not found for " + startTime
                util.debugPrint(errorStr)
                response = make_response(util.formatError(errorStr), 404)
                return response
            result = generateSingleAcquisitionSpectrogramAndOccupancyForFFTPower(msg, sessionId)
            if result == None:
                errorStr = "Illegal Request"
                response = make_response(util.formatError(errorStr), 400)
                return response
            else:
                return result
        else :
           util.debugPrint("Only FFT-Power type messages supported")
           errorStr = "Illegal Request"
           response = make_response(util.formatError(errorStr), 400)
           return response
    except:
        print "Unexpected error:", sys.exc_info()[0]
        print sys.exc_info()
        traceback.print_exc()
        raise

@app.route("/spectrumbrowser/generateSingleDaySpectrogramAndOccupancy/<sensorId>/<startTime>/<minFreq>/<maxFreq>/<sessionId>", methods=["POST"])
def generateSingleDaySpectrogram(sensorId, startTime, minFreq, maxFreq, sessionId):
    try:
        if not checkSessionId(sessionId):
            abort(403)
        startTimeInt = int(startTime)
        minfreq = int(minFreq)
        maxfreq = int(maxFreq)
        print request
        subBandMinFreq = int(request.args.get("subBandMinFreq", minFreq))
        subBandMaxFreq = int(request.args.get("subBandMaxFreq", maxFreq))
        query = { SENSOR_ID: sensorId}
        msg = db.dataMessages.find_one(query)
        if msg == None:
            util.debugPrint("Sensor ID not found " + sensorId)
            abort(404)
            query = { SENSOR_ID: sensorId, "t":{"$gte" : startTimeInt}, "freqRange":populate_db.freqRange(minfreq, maxfreq)}
            util.debugPrint(query)
            msg = db.dataMessages.find_one(query)
            if msg == None:
                errorStr = "Data message not found for " + startTime
                util.debugPrint(errorStr)
                return make_response(util.formatError(errorStr), 404)
        if msg["mType"] == "Swept-frequency" :
            return generateSingleDaySpectrogramAndOccupancyForSweptFrequency(msg, sessionId, startTimeInt, minfreq, maxfreq, subBandMinFreq, subBandMaxFreq)
        else:
            errorStr = "Illegal message type"
            util.debugPrint(errorStr)
            return make_response(util.formatError(errorStr), 400)
    except:
        print "Unexpected error:", sys.exc_info()[0]
        print sys.exc_info()
        traceback.print_exc()
        raise



@app.route("/spectrumbrowser/generateSpectrum/<sensorId>/<start>/<timeOffset>/<sessionId>", methods=["POST"])
def generateSpectrum(sensorId, start, timeOffset, sessionId):
    """ Generate a spectrum image given the sensorId, start time of acquisition and timeOffset and return the location
    of the generated image """
    try:
        if not checkSessionId(sessionId):
            abort(403)
        startTime = int(start)
        # get the type of the measurement.
        msg = db.dataMessages.find_one({SENSOR_ID:sensorId})
        if msg["mType"] == "FFT-Power":
            msg = db.dataMessages.find_one({SENSOR_ID:sensorId, "t":startTime})
            if msg == None:
                errorStr = "dataMessage not found " + dataMessageOid
                util.debugPrint(errorStr)
                abort(404)
            milisecOffset = int(timeOffset)
            return generateSpectrumForFFTPower(msg, milisecOffset, sessionId)
        else :
            secondOffset = int(timeOffset)
            time = secondOffset + startTime
            print "time " , time
            time = secondOffset + startTime
            msg = db.dataMessages.find_one({SENSOR_ID:sensorId, "t":{"$gte": time}})
            minFreq = int(request.args.get("subBandMinFrequency", msg["mPar"]["fStart"]))
            maxFreq = int(request.args.get("subBandMaxFrequency", msg["mPar"]["fStop"]))
            if msg == None:
                errorStr = "dataMessage not found "
                util.debugPrint(errorStr)
                abort(404)
            return generateSpectrumForSweptFrequency(msg, sessionId, minFreq, maxFreq)
    except:
         print "Unexpected error:", sys.exc_info()[0]
         print sys.exc_info()
         traceback.print_exc()
         raise

@app.route("/spectrumbrowser/generateZipFileFileForDownload/<sensorId>/<startTime>/<days>/<minFreq>/<maxFreq>/<sessionId>", methods=["POST"])
def generateZipFileForDownload(sensorId, startTime, days, minFreq, maxFreq, sessionId):
    try:
        if not checkSessionId(sessionId):
            abort(403)
        return GenerateZipFileForDownload.generateZipFileForDownload(sensorId, startTime, days, minFreq, maxFreq, sessionId)
    except:
         print "Unexpected error:", sys.exc_info()[0]
         print sys.exc_info()
         traceback.print_exc()
         raise

@app.route("/spectrumbrowser/emailDumpUrlToUser/<emailAddress>/<sessionId>", methods=["POST"])
def emailDumpUrlToUser(emailAddress, sessionId):
    """
    Send email to the given user when his requested dump file becomes available.
    """
    try:
        if not checkSessionId(sessionId):
            abort(403)
        urlPrefix = request.args.get("urlPrefix", None)
        util.debugPrint(urlPrefix)
        uri = request.args.get("uri", None)
        util.debugPrint(uri)
        if urlPrefix == None or uri == None :
            abort(400)
        url = urlPrefix + uri
        return GenerateZipFileForDownload.emailDumpUrlToUser(emailAddress, url, uri)
    except:
         print "Unexpected error:", sys.exc_info()[0]
         print sys.exc_info()
         traceback.print_exc()
         raise
     
@app.route("/spectrumbrowser/checkForDumpAvailability/<sessionId>", methods=["POST"])
def checkForDumpAvailability(sessionId):
    """
    Check for availability of a previously generated dump file.
    """
    try:
        if not checkSessionId(sessionId):
            abort(403)
        uri = request.args.get("uri", None)
        util.debugPrint(uri)
        if  uri == None :
            debugPrint("URI not specified.")
            abort(400)
        if  GenerateZipFileForDownload.checkForDumpAvailability(uri):
            return jsonify( {"status":"OK"})
        else:
            return jsonify({"status":"NOT_FOUND"})
    except:
         print "Unexpected error:", sys.exc_info()[0]
         print sys.exc_info()
         traceback.print_exc()
         raise


@app.route("/spectrumbrowser/generatePowerVsTime/<sensorId>/<startTime>/<freq>/<sessionId>", methods=["POST"])
def generatePowerVsTime(sensorId, startTime, freq, sessionId):
    try:
        if not checkSessionId(sessionId):
            abort(403)
        msg = db.dataMessages.find_one({SENSOR_ID:sensorId})
        if msg == None:
            util.debugPrint("Message not found")
            abort(404)
        if msg["mType"] == "FFT-Power":
            msg = db.dataMessages.find_one({SENSOR_ID:sensorId, "t":int(startTime)})
            if msg == None:
                errorMessage = "Message not found"
                util.debugPrint(errorMessage)
                abort(404)
            freqHz = int(freq)
            return generatePowerVsTimeForFFTPower(msg, freqHz, sessionId)
        else:
            msg = db.dataMessages.find_one({SENSOR_ID:sensorId, "t": {"$gt":int(startTime)}})
            if msg == None:
                errorMessage = "Message not found"
                util.debugPrint(errorMessage)
                abort(404)
            freqHz = int(freq)
            return generatePowerVsTimeForSweptFrequency(msg, freqHz, sessionId)
    except:
         print "Unexpected error:", sys.exc_info()[0]
         print sys.exc_info()
         traceback.print_exc()
         raise

@app.route("/spectrumdb/upload", methods=["POST"])
def upload() :
    msg = request.data
    populate_db.put_message(msg)
    return "OK"


@sockets.route("/sensordata", methods=["POST", "GET"])
def getSensorData(ws):
    """
    Handle sensor data streaming requests.
    """
    try :
        print "getSensorData"
        token = ws.receive()
        print "token = " , token
        parts = token.split(":")
        sessionId = parts[0]
        if not checkSessionId(sessionId):
            ws.close()
            return
        sensorId = parts[1]
        util.debugPrint("sensorId " + sensorId)
        if not sensorId in lastDataMessage :
            ws.send(dumps({"status":"NO_DATA"}))
        else:
            ws.send(dumps({"status":"OK"}))
            ws.send(lastDataMessage[sensorId])
            lastdatatime = -1
            while True:
                if lastdatatime != lastdataseen[sensorId]:
                    lastdatatime = lastdataseen[sensorId]
                    ws.send(sensordata[sensorId])
                gevent.sleep(SECONDS_PER_FRAME)
    except:
        ws.close()
        print "Error writing to websocket"


@sockets.route("/spectrumdb/stream", methods=["POST"])
def datastream(ws):
    print "Got a connection"
    bbuf = MyByteBuffer(ws)
    count = 0
    while True:
        lengthString = ""
        while True:
            lastChar = bbuf.readChar()
            if len(lengthString) > 1000:
                raise Exception("Formatting error")
            if lastChar == '{':
                print lengthString
                headerLength = int(lengthString.rstrip())
                break
            else:
                lengthString += str(lastChar)
        jsonStringBytes = "{"
        while len(jsonStringBytes) < headerLength:
            jsonStringBytes += str(bbuf.readChar())

        jsonData = json.loads(jsonStringBytes)
        print dumps(jsonData, sort_keys=True, indent=4)
        if jsonData["Type"] == "Data":
            dataSize = jsonData["nM"] * jsonData["mPar"]["n"]
            td = jsonData["mPar"]["td"]
            nM = jsonData["nM"]
            n = jsonData["mPar"]["n"]
            sensorId = jsonData["SensorID"]
            lastDataMessage[sensorId] = jsonStringBytes
            timePerMeasurement = float(td) / float(nM)
            spectrumsPerFrame = int(SECONDS_PER_FRAME / timePerMeasurement)
            measurementsPerFrame = spectrumsPerFrame * n
            util.debugPrint("measurementsPerFrame : " + str(measurementsPerFrame) + " n = " + str(n) + " spectrumsPerFrame = " + str(spectrumsPerFrame))
            cutoff = jsonData["wnI"] + 2
            while True:
                counter = 0
                startTime = time.time()
                if peakDetection:
                    powerVal = [-100 for i in range(0, n)]
                else:
                    powerVal = [0 for i in range(0, n)]
                for i in range(0, measurementsPerFrame):
                    data = bbuf.readByte()
                    if peakDetection:
                        powerVal[i % n] = np.maximum(powerVal[i % n], data)
                    else:
                        powerVal[i % n] += data
                if not peakDetection:
                    for i in range(0, len(powerVal)):
                        powerVal[i] = powerVal[i] / spectrumsPerFrame
                # sending data as CSV values.
                sensordata[sensorId] = str(powerVal)[1:-1].replace(" ", "")
                lastdataseen[sensorId] = time.time()
                endTime = time.time()
                delta = 0.7 * SECONDS_PER_FRAME - endTime + startTime
                if delta > 0:
                    gevent.sleep(delta)
                else:
                    gevent.sleep(0.7 * SECONDS_PER_FRAME)
                # print "count " , count
        elif jsonData["Type"] == "Sys":
            print "Got a System message"
        elif jsonData["Type"] == "Loc":
            print "Got a Location Message"

@sockets.route("/spectrumdb/test", methods=["POST"])
def websockettest(ws):
    count = 0
    try :
        msg = ws.receive()
        print "got something " + str(msg)
        while True:
            gevent.sleep(0.5)
            dataAscii = ws.receive()
            data = binascii.a2b_base64(dataAscii)
            count += len(data)
            print "got something " + str(count) + str(data)
    except:
        print "Unexpected error:", sys.exc_info()[0]
        print sys.exc_info()
        traceback.print_exc()
        raise

@app.route("/spectrumbrowser/log", methods=["POST"])
def log():
    data = request.data
    jsonValue = json.loads(data)
    message = jsonValue["message"]
    print "Log Message : " + message
    exceptionInfo = jsonValue["ExceptionInfo"]
    if len(exceptionInfo) != 0 :
        print "Exception Info:"
        for i in range(0, len(exceptionInfo)):
            print "Exception Message:"
            exceptionMessage = exceptionInfo[i]["ExceptionMessage"]
            print "Stack Trace :"
            stackTrace = exceptionInfo[i]["StackTrace"]
            print exceptionMessage
            util.decodeStackTrace(stackTrace)
    return "OK"

# @app.route("/spectrumbrowser/login", methods=["POST"])
# def login() :
#    sessionId = random.randint(0,1000)
#    returnVal = {}
#    returnVal["status"] = "OK"
#    returnVal["sessionId"] = sessionId
#    secureSessions[request.remote_addr] = sessionId
#    return JSONEncoder().encode(returnVal)


if __name__ == '__main__':
    launchedFromMain = True
    util.loadGwtSymbolMap()
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    # app.run('0.0.0.0',port=8000,debug="True")
    server = pywsgi.WSGIServer(('0.0.0.0', 8000), app, handler_class=WebSocketHandler)
    server.serve_forever()
