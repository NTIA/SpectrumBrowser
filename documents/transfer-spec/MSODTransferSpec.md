**Data Transfer Specification for the Measured Spectrum Occupancy Database**

*Version 1.0.16 (October 21  2016)*

# 1.  Description

This data transfer specification defines the format and required
information for data to be ingested into the Measured Spectrum Occupancy
Database (MSOD). MSOD is being developed in a collaborative effort between
NTIA’s Institute for Telecommunication Sciences (ITS) and NIST’s
Communication Technology Laboratory (CTL). The MSOD system consists
of a federated server infrastructure and sensors that send data to the
server. The focus of this document is a specicfication of the data format
and transport for transferring information from sensors to the server.

Identifiers and mappings:

1. Each sensor is identified by a globally unique SensorID and is
authenticated by a <sensorId,sensorKey> pair. This is sent with every
Meta-Data message sent to the server by the sensor and allows the server
to authenticate the sensor. A sensor is associated with a single server.

2. Each server is identified by a globally unique ServerID and is
authenticated by a <serverId,serverKey> pair. This is sent by the server
on every Federation message and allows peer servers to authenticate
federation metadata.  The data format for the metadata exchanges
between servers for the purpose of federation is outside the scope of
this document.

Interactions with the Server:

Sensors report data either by periodically POSTing readings or streaming
sending power spectrums periodically as a vector through a persistant
secure TCP connection.  Streaming Sensors may also be set up to capture
I/Q data for forensic analysis.

# 2.  Meta-data message format

The messages between sensor and MSOD will be in JavaScript Object Notation
(JSON). The following is an example of a JSON Loc (Location) message
(to be defined below):

```json
{
    "version": "1.0.16",
    "messageType": "Loc",
    "sensorId": "101010101",
    "sensorKey": 846859034,
    "time": 987654321,
    "mobility": "Stationary",
    "environment": "Outdoor",
    "latitude": 40.0,
    "longitude": -105.26,
    "altitude": 1655,
    "timeZone": "America/Denver"
}
```

(Note: JSON is a language-independent data-interchange format that is
easy for humans to read and write. There are code and functions readily
available in C, C++, C\#, Java, JavaScript, MATLAB, Perl, and Python
for parsing and generating JSON. It is a lightweight alternative to XML,
commonly used to transmit data between server and browser applications.)

# 3.  JSON Message Descriptions

The data fields in the JSON message descriptions below are required
fields. If an attribute is not relevant to the sensor implementation,
then the value is set to NaN or "NaN". Each message (in general)
will begin with a header comprised of attribute-value pairs in ASCII
characters. The first five fields are the same for all messages; they are:

1.  version = Schema/data transfer version with the major.minor.revision syntax `string`
2.  messageType = Type of JSON message (“Sys”| ”Loc”| “Data”|"Capture-Event") `string of URL unreserved characters`
3.  sensorId = Unique identifier of sensor `string`
4.  sensorKey = Authentication key given out by MSOD `integer`
5.  time = Time [seconds since Jan 1, 1970 UTC] `long integer`

The following are specific formatting rules to be followed to avoid
problems when messages are ingested into MSOD: (1) All timestamps, i.e.,
time (defined above) and t1 (to be defined in Data message description)
will be reported as seconds since 1/1/1970 midnight UTC in the UTC time
zone; (2) String values for SensorID and Sys2Detect (to be defined in
Data message description) must only contain URL unreserved characters
(i.e., uppercase and lowercase letters, decimal digits, hyphen, period,
underscore, and tilde); and (3) Field names cannot start with an
underscore because that convention is reserved for MSOD internal use.

We define four types of JSON messages for our purposes: (1) Sys, (2)
Loc, (3) Data, and (4) Event. The Sys and Data messages can contain data in
addition to the header information. Required fields for each message
type are defined in the following subsections.

### 3.1.  Sys Messages

The Sys (System) message lists the critical hardware components of
the sensor along with relevant RF specifications. It can also contain
calibration data. Sys messages are sent when the sensor “registers”
with the database, at the start of a sequence of measurements, and/or
at a specified calibration frequency (e.g., hourly, daily). If the
Sys message does not contain calibration data, the Cal data structure
(9 below) and data block are excluded. The Sys message is comprised of
header information and an optional data block. The Sys header contains
the following fields:

1.  version = Schema/data transfer version with the major.minor.revision syntax `string`
2.  messageType = Type of JSON message (”Sys”) `string`
3.  sensorId = Unique identifier of sensor `string of URL unreserved characters`
4.  sensorKey = Authentication key given out by MSOD `integer`
5.  time = Time [seconds since Jan 1, 1970 UTC] `long integer`
6.  antenna = data that describes the antenna (see Antenna object below)
7.  preselector = data that describes RF hardware components in preselector (see Preselector object below)
8.  cotsSensor = data that describes the COTS sensor (see COTSsensor object below)
9.  calibration = data structure that describes the calibration measurement (optional, see Cal object below)

The Sys data block is comprised of two vectors of numbers of the specified data type and byte order. If DataType = “ASCII”, then the data block is enclosed by square brackets.

If processed = “False”, then the data streams are

10a. noiseSourceOnPowers(n) = Raw measured data vector [dBm ref to input of COTS sensor] when known source is on.

11a. noiseSourceOffPowers(n) = Raw measured data vector [dBm ref to input of COTS sensor] when known source is off.

where n = MeasurementParameters.n is specified in the Sys message header. Raw cal data is
straight from the COTS sensor and is provided for the first calibration
in a sequence. The Sys raw stream is ordered as follows: [wOn(1), wOn(2),
… wOn(n), wOff(1), wOff(2), …, wOff(n)], where the argument denotes
a frequency index and wOn = noiseSourceOnPowers and wOff = noiseSourceOffPowers

If processed = “True”, then the data streams are,

10b. noiseFigure(n) = Noise figure [dB] referenced to input of preselector.

11b. gain(n) = System gain [dB] referenced to input of preselector

The Sys processed stream is ordered as follows: [noiseFigure(1), noiseFigure(2), … noiseFigure(n), 
    gain(1), gain(2), …, gain(n)].

### 3.2.  Loc Messages

The Loc message specifies the geolocation of the sensor. Loc messages
are sent when the location information changes, e.g., if the sensor
is mobile it will be sent with each data file. It is also sent when a
sequence of continuous acquisitions is initiated. It is comprised only
of header information with the following fields:

1.  version = Schema/data transfer version with the major.minor.revision syntax `string`
2.  messageType = Type of JSON message (“Loc”) `string`
3.  sensorId = Unique identifier of sensor `string of URL unreserved characters`
4.  sensorKey = Authentication key given out by MSOD `integer`
5.  time = Time [seconds since Jan 1, 1970 UTC] `long integer`
6.  mobility = Mobility of sensor (“Stationary”| “Mobile”) `string`
7.  environment = Description of the environment where antenna is mounted ("Indoor"| "Outdoor") 'string'
8.  latitude = angle [degrees N] from equatorial plane (0 – 360) `float`
9.  longitude = angle [degrees E] from Greenwich median (-180 – 180) `(float`
10. altitude = height above sea level [m] (0 - 10<sup>6</sup>) `float`
11. timeZone = Local time zone identifier (“America/New_York”, “America/Chicago”, “America/Denver”, “America/Phoenix”, or “America/Los_Angeles”) `string`

### 3.3.  Data Messages

The Data message contains acquired data from measurements of the environment using an antenna. 
The Data message is sent after each acquisition, i.e., after a burst of nM measurements are acquired. 
Each acquisition is preceded by a Data Message followed by nM power spectrum readings, each of length n.
Some measurement schemes will involve an imposed pause after each acquisition. 
Each Data message is comprised of a header and a data block. Streaming transfers consist of a single Data message
followed by a continuous stream of power arrays, each of length n.
The JSON header information contains the following:

1.  version = Schema/data transfer version with the major.minor.revision syntax `string`
2.  messageType = Type of JSON message “Data” `string`
3.  sensorId = Unique identifier of sensor `string of URL unreserved characters`
4.  sensorKey = Authentication key for the sensor `string`
5.  time = Time [seconds since Jan 1, 1970 UTC] `long integer` in the UTC time zone. 
6.  sysToDetect = System that measurement is designed to detect (“Radar–SPN43”| “LTE”| “None”) `string of URL unreserved characters`
7.  sensitivity = Sensitivity of the data (“Low” | “Medium” | “High”) `string`
8.  measurementType = Type of measurement (“Swept-frequency”| “FFT-power”) `string`
9.  timeOfAcquisition = Time of 1<sup>st</sup> acquisition in a sequence [seconds since Jan 1, 1970 UTC] `long integer` in the UTC time     zone.
10. acquisitionIndex = Index of current acquisition in a sequence `integer`
11. numOfMeasurements = Number of measurements per acquisition `integer`. Not relevant for streaming transfers (set to -1).
12. timeBetweenAcquisitions = Imposed time between acquisition starts `float`. This is the time between successive Data messages (not             relevant for streaming transfers).
13. timeBetweenStreams = Time between spectrums when data is sent as a stream via a tcp socket ( relevant for streaming transfers ).
14. overloadFlag = Overload flag(s) (0 | 1) `integer`
15. detectedSysNoisePowers = Detected system noise power [dBm ref to output of isotropic antenna] `float`
16. comment `string`
17. processed = Indicator on processing of data ("True"|"False") `string`
18. dataType = Data type ("Binary–float32", "Binary–int16", "Binary–int8", "ASCII") `string`
19. byteOrder = Order of bytes for binary data ("Network" | "Big Endian" | "Little Endian" |  "N/A") `string`
20. compression = Indicator on compression of data ("Zip" | "None") `string`
21. measurementParameters = Measurement parameters (elements listed in Objects section below)

The data block is comprised of an array of numbers of the specified data type and byte order. If DataType = “ASCII”, then the data block is enclosed by square brackets. 

If processed = “False”, then the data stream is

21a. rawMeasuredPowers(n, nM) = Raw measured data vector [dBm ref to input of COTS sensor]

where n = measurementParameters.n is specified in the Data message header. Raw data is
straight from the COTS sensor and is provided for the first acquisition
in a sequence. Raw data allows for a quality assurance check on the
system specifications. The Data raw stream is ordered as follows: [w(1,
1), w(2, 1), … w(n, 1), w(1, 2), w(2, 2), …, w(n, 2), …, w(1, nM),
w(2, nM), …, w(n, nM)], where the first argument denotes a frequency
index and the second argument denotes measurement index.

If processed = “True”, then the data stream is

21b. measuredPowers(n, nM) = Measured power vector [dBm ref to output of isotropic antenna]

Processed data is adjusted to remove system gains and losses and provide
signal amplitude that is sensor-independent. Processed data is intended
for ingest straight into MSOD. The Data processed stream is ordered
as follows: [wI(1, 1), wI(2, 1), … wI(n, 1), w(1, 2), wI(2, 2), …,
wI(n, 2), …, wI(1, nM), wI(2, nM), …, wI(n, nM)].

### 3.4 Capture-Event Messages

The Capture-Event Message is used to POST an asynchronous event from the
sensor to the server. In the one use case implemented thusfar, a sensor
(designed to measure and decode LTE downlink signals) is armed by the
server to enable I/Q capture, after which it captures the data based on
a local trigger. The Event message to ARM the sensor is sent from the
server via the persistent TCP connection which it establishes with the
server. When a sensor is in the ARMed state, it may capture I/Q data
based on a local detection criterion such as energy detection. When
an ARMed sensor captures I/Q data, it POSTs an Event message to the
server, indicating that it has captured data. Later, the sensor may
further analyze the data and post another Capture-Event message to the server
indicating that specific features such as Base Station identifier have
been detected. The POSted Event message contains information to correlate
it to the previous Capture-Event.

(Note: Extensions to this specification will include other types of
asynchronous event reporting such as sensor operational error conditions,
temperature etc. to the server.)

The Capture-Event message contains the following:

1.   version = Schema/data transfer version with the major.minor.revision syntax `string`
2.   messageType = Type of JSON message “Capture-Event” `string`
3.   sensorId = Unique identifier of sensor `string of URL unreserved characters`
4.   sensorKey = Authentication key for the sensor `string`
5.   time = Time [seconds since Jan 1, 1970 UTC] `long integer` in the UTC time zone. 
6.   sysToDetect = System that measurement is designed to detect (“Radar–SPN43”| “LTE”| “None”) `string of URL unreserved characters`
7.   sensitivity = Sensitivity of the data (“Low” | “Medium” | “High”) `string`
8.   measurementType = Type of measurement (“I_Q”) `string`
9.   dataType = Data type ("Binary–float32", "Binary–int16", "Binary–int8") `string`
10.  measurementParameters = Measurement parameters (elements listed in Objects section below)
11.  decode = Detection results (elements listed in Objects section below)
12.  sampleCount: Number of captured samples.

Note that after completing the anaysis, the sensor POSTs a second
Capture-Event that matches a previously POSTed capture event with an
additional Decode Object. This decoding step can take some time and
hence it runs asynchronously. The sensorId, time stamp t, sysToDetect,
sensorId, MeasurementParameters.sampleRate, MeasurementParameters.centerFrequency must match the previously posted
Capture-Event. This associates the posted Decode with the previouosly
posted Capture-Event.

# 4.  Objects

The following are JSON object definitions that exist in the JSON data messages above.

antenna = antennas parameters with elements

1.  model = Make/model (“AAC SPBODA-1080\_NFi”| “Alpha AW3232”) `string`
2.  lowFrequency = Low frequency [Hz] of operational range `float`
3.  highFrequency = High frequency [Hz] of operational range `float`
4.  gain = Antenna gain [dBi] `float`
5.  horizontalBeamWidth = Horizontal 3-dB beamwidth [degrees] `float`
6.  verticalBeamWidth = Vertical 3-dB beamwidth [degrees] `float`
7.  azmithBeamDir = direction of main beam in azimuthal plane [degrees from N] `float`
8.  elevationBeamDir = direction of main beam in elevation plane [degrees from horizontal] `float`
9.  polarization = Polarization (“VL”| “HL”| “LHC”| “RHC”, “Slant”) `string`
10. crossPolarDiscrimination = Cross-polarization discrimination [dB] `float`
11. voltageStandingWaveRatio = Voltage standing wave ratio `float`
12. cableLoss = Cable loss (dB) for cable connecting antenna and preselector `float`


preselector = preselector parameters with elements

1.  lowFreqPassband = Low frequency [Hz] of filter 1-dB passband float
2.  highFreqPassband= High frequency [Hz] of filter 1-dB passband float
3.  lowFreqStopband = Low frequency [Hz] of filter 60-dB stopband float
4.  lowFreqStopBand = High frequency [Hz] of filter 60-dB stopband float
5.  lnaNoiseFigure = Noise figure [dB] of LNA float
6.  lnaGain = Gain [dB] of LNA float
7.  lnaMaxPowerOut = Max power [dBm] at output of LNA, e.g., 1-dB compression point float
8.  excessNoiseRatio = Excess noise ratio of noise [dB] diode for y-factor calibrations


cotsSensor = COTS sensor parameters with elements

1.  model = Make and model ("Agilent N6841A"| "Agilent E4440A"| "CRFS RFeye"| "NI USRP N210"| "ThinkRF WSA5000-108"| "Spectrum Hound BB60C") `string`
2.  lowFrequency = LowMinimum frequency [Hz] of operational range `float`
3.  highFrequency = HighMaximum frequency [Hz] of operational range `float`
4.  noiseFigure = Noise figure [dB] of COTS sensor in contrast to overall system `float`
5.  maxPower = Maximum power [dBm at input] of COTS sensor `float`

calibration = Calibration parameters with elements

1.  calsPerHour = Number of cals per hour `float`
2.  temp = Measured temperature inside preselctor [F] `float`
3.  measurementType: Type of measurement (“Swept-frequency”, “FFT-power”) `string`
4.  numOfMeasurmentsPerCal = Number of measurements per calibration `integer`
5.  processed = Indicator on processing of data ("True"| "False") `string`
6.  dataType = Data type ("Binary–float32"| "Binary–int16"| "Binary–int8"| "ASCII") `string`
7.  byteOrder = Order of bytes for binary data ("Network", "Big Endian", "Little Endian", "N/A") `string`
8.  compression = Compression of data ("Zip"| "None") `string`
9.  MeasurementParameters = Measurement parameters (elements listed in Objects section below)

measurementParameters = Measurement parameters

1.  startFrequency = Start frequency [Hz] of sweep \<Required for swept-freq\> `float`
2.  stopFrequency = Stop frequency [Hz] of sweep \<Required for swept-freq\> `float`
3.  numOfFreqsInSweep = Number of frequencies in sweep \<Required for swept-freq\> `float`
4.  dwellTime = Dwell time [s] at each frequency in a sweep \<Required for swept-freq\> `float`
5.  detector = Detector: ("RMS"| "Positive” | "Peak" | "Average")  \<Required for swept-freq\> `string`
6.  resolutionBw = Resolution bandwidth [Hz] \<Required for swept-freq\> `float`
7.  videoBw = Video bandwidth [Hz] \<Required for swept-freq\> `float`
8.  attenuation = COTS sensor attenuation [dB] \<Required for swept-freq\> `float`
9.  sampleRate = Sampling rate [Samples/second] \<Required for I/Q capture\>
10. equivalentNoiseBw = Equivalent Noise Bandwidth [Hz]
11. centerFrequencies = Center frequency [Hz] \<Required for I/Q capture\>

Note: \<systemToDetect,startFrequency,stopFrequency\> determine the MSOD band for which we are capturing I/Q data.
centerFrequency and CaptureEvent.sampFreq determine the bandwidth of the I/Q samples. In the case of a 
swept frequency sensor, there could be several capture events corresponding to a single scan.

Decode = Decoded LTE information

Our first target is coherent detection, where we assume complete knowledge
of the signal we are trying to detect. For LTE, the following are 
detection parameters reported by the sensor for LTE Detection:

1.  algorithm = Algorithm used for detection ("coherent"|"matched-filter"|"cyclostationary")

The following additional fields are relevant to the "coherent" scheme for LTE detection:

1.  cellId = Cell identification number `integer` 
2.  sectorId = Sector identification `integer` 
3.  linktype = ("uplink" | "downlink") 

# 5.  Transfer Mechanism

TCP sockets or HTTPS POST will be used to transfer data from sensor (client) to  the server either real time or post-acquisition. 

### Secure socket transport

#### 5.1.  Socket Setup

The sensor is a pure client. For security reasons, it does not accept
inbound connections (may be placed behind a firewall that blocks inbound
connection). The client initiates the connection to the server. 


The connection is established and maintained as follows:

1. When the sensor starts, it optionally reads its configuration from the server
using a REST API that returns its configuration. It uses this information
to configure itself and connect to a streaming port to begin sending
data. The API to accomplush this will be described in a separate API
document.
2. As soon as it connects to the streaming port, it sends a System
Message, followed by a Location Message, thus establishing its system
and location parameters. These two messages are mandatory on every
connection or re-connection. After this, the sensor sends a Data Message,
followed by a stream of power vectors. Each power vector has a length
of DataMessage.mPar.n.
3. If the sensor is re-configured at the server, the server will drop
the connection.  This causes the sensor to reconfigure itself and repeat
the sequence (step 1).

The detailed messaging for sensor configuration is outside the scope of this document.
It will be further detailed in a separte API document.
   

### 5.2.  HTTPS post

Sensors may also intermittently connect and POST data by connecting to the server 
and POSTing data to it. The steps involved are as follows:

1. (Optional) The Sensor configures itself by reading its configuration from the server.
2. The sensor sends a System message.
3. The sensor sends a Location mesage.
4. The sensor then periodically POSts messages consisting of a ascii
length field <CRLF>, followed by a  DataMessage header followed
by DataMesasge.mPar.nM power spectrums, with each vector of size
DataMessage.mPar.n
5. The server compares the DataMessage header fields to the configuration
information of the sensor. If settings do not match, server rejects the sensor data.
6. If settings do not match, the server will return a 406 - Not Acceptable
error code. Assuming the sensor has this capability (optional), this
causes the sensor to re-read its configuration (step 1) and proceed as
above. The detailed messaging for sensor configuration is outside the
scope of this document.


### 5.3.  MSOD Ingest Process

The data streamed or POSTed to the server is maintained in a database for subsequent analysis.
The process of ingesting the data and accessing it described in a separate API document.
