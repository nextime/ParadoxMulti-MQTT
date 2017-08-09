#encoding=utf-8

import hashlib
import socket
import time
import lib.client as mqtt
import sys
import array
import random
import ConfigParser
import struct
import importlib
import serial
import logging
import re
import json

Label_Regex = re.compile('[^a-zA-Z0-9\ \-]')

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger()

# Alarm controls can be given in payload, e.g. Paradox/C/P1, payl = Disarm

# Do not edit these variables here, use the config.ini file instead.
Zone_Amount = 32
passw = "0000"
user = "1000"

SERIAL_PORT = "/dev/ttyS1"

MQTT_IP = "127.0.0.1"
MQTT_Port = 1883
MQTT_KeepAlive = 60  # Seconds

# Options are Arm, Disarm, Stay, Sleep (case sensitive!)
Topic_Publish_Battery = "Paradox/Voltage"
Topic_Publish_Events = "Paradox/Events"
Topic_Publish_Status = "Paradox/Status"
Events_Payload_Numeric = False
Topic_Subscribe_Control = "Paradox/Control/" # e.g. To arm partition 1: Paradox/C/P1/Arm
Startup_Publish_All_Info = "True"
Startup_Update_All_Labels = "True"
Topic_Publish_Labels = "Paradox/Labels"
Topic_Publish_AppState = "Paradox/State"
Alarm_Model = "ParadoxMG5050"
Alarm_Registry_Map = "ParadoxMG5050"
Alarm_Event_Map = "ParadoxMG5050"

# Global variables
Alarm_Control_Action = 0
Alarm_Control_Partition = 0
Alarm_Control_NewState = ""
Output_FControl_Action = 0
Output_FControl_Number = 0
Output_FControl_NewState = ""
Output_PControl_Action = 0
Output_PControl_Number = 0
Output_PControl_NewState = ""
State_Machine = 0
Debug_Mode = 2
Poll_Speed = 1
Debug_Packets = False
Keep_Alive_Interval = 5

Alarm_Data = {}

def ConfigSectionMap(section):
    dict1 = {}
    options = Config.options(section)
    for option in options:
        try:
            dict1[option] = Config.get(section, option)
            if dict1[option] == -1:
                logger.debug ("skip: %s" % option)
        except:
            logger.exception("exception on %s!" % option)
            dict1[option] = None
    return dict1


def on_connect(client, userdata, flags, rc):
    logger.info("Connected to MQTT broker with result code " + str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    # client.subscribe("$SYS/#")


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global Alarm_Control_Partition
    global Alarm_Control_NewState
    global Alarm_Control_Action
    global Output_FControl_Number
    global Output_FControl_NewState
    global Output_FControl_Action
    global Output_PControl_Number
    global Output_PControl_NewState
    global Output_PControl_Action

    valid_states = ['Arm', 'Disarm', 'Sleep', 'Stay']

    logger.debug("MQTT Message: " + msg.topic + " " + str(msg.payload))

    topic = msg.topic


    if Topic_Subscribe_Control in msg.topic:
        if "/Output/" in msg.topic:
            try:
                Output_FControl_Number = msg.topic.split("/")[-1]

                logger.debug("Output force control number: ", Output_FControl_Number)
                Output_FControl_NewState = msg.payload
                if len(Output_FControl_NewState) == 0:
                    logger.warning("No payload for output: e.g. On")
                    return

                logger.debug( "Output force control state: ", Output_FControl_NewState)
                client.publish(Topic_Publish_AppState,
                               "Output: Forcing PGM " + str(Output_FControl_Number) + " to state: " + Output_FControl_NewState, 0, True)
                Output_FControl_Action = 1
            except:
                logger.exception("MQTT message received with incorrect structure")

        elif "/Pulse/" in msg.topic:
            try:
                Output_PControl_Number = msg.topic.split("/")[-1]

                logger.debug("Output pulse control number: ", Output_PControl_Number)
                Output_PControl_NewState = msg.payload
                if len(Output_PControl_NewState) == 0:
                    logger.warning("No payload for output: e.g. On")
                    return
                
                logger.debug( "Output pulse control state: ", Output_PControl_NewState)
                client.publish(Topic_Publish_AppState,
                               "Output: Pulsing PGM " + str(Output_PControl_Number) + " to state: " + Output_PControl_NewState,
                               0, True)
                Output_PControl_Action = 1
            except:
                logger.exception("MQTT message received with incorrect structure")
        elif "/Partition/" in msg.topic:
            try:
                Alarm_Control_Partition = topic.split("/")[-1]
                logger.debug( "Alarm control partition: %s ", Alarm_Control_Partition)
                Alarm_Control_NewState = msg.payload
                if len(Alarm_Control_NewState) < 1:
                    logger.warning('No payload given for alarm control: e.g. Disarm')
                    return

                logger.debug( "Alarm control state: %s", Alarm_Control_NewState)
                client.publish(Topic_Publish_AppState,
                               "Alarm: Control partition " + str(Alarm_Control_Partition) + " to state: " + Alarm_Control_NewState,
                               0, True)
                Alarm_Control_Action = 1
            except:
                logger.exception("MQTT message received with incorrect structure")



class CommSerial:
    comm = None
    
    def __init__(self, serialport):
        self.serialport = serialport
        self.comm = None

    def connect(self, baud=9600, timeout=1):
        try:
            logger.info( "Opening Serial port: " + self.serialport)
            self.comm = serial.Serial()
            self.comm.baudrate = baud
            self.comm.port =  self.serialport
            self.comm.timeout = timeout
            self.comm.open()
            logger.info( "Serial port open!")
        except:
            return False

        return True

    def write(self, data):
        if Debug_Packets and logger.isEnabledFor(logging.DEBUG):
            m = "Data OUT -> " + str(len(data)) + " -b- "
            for c in data:
                m += " %02x" % ord(c)
            logger.debug(m)

        self.comm.write(data)
        
    def read(self, sz=37, timeout=1):
	self.comm.timeout = timeout

        data = self.comm.read(sz)

        if Debug_Packets and logger.isEnabledFor(logging.DEBUG):
            if data is not None and len(data) > 0:
                m = "Data IN  <- " + str(len(data)) + " -b- "                

                for c in data:
                    m += " %02x" % ord(c)
                logger.debug(m)

        return data
    def disconnect(self):
        self.comm.close()
        pass


# To be implemented. Do dot have the hardware to proceed. 
class CommIP150:
    def connect():
        pass

    def write():
        pass

    def read():
        pass

    def disconnect():
        pass


class Paradox:
    loggedin = 0
    alarmName = None
    zoneTotal = 0
    zoneStatus = ['']
    zoneNames = ['']
    zonePartition = None
    partitionStatus = None
    partitionName = None
    Skip_Update_Labels = 0

    def __init__(self, _transport, _encrypted=0, _retries=3, _alarmeventmap="ParadoxMG5050",
                 _alarmregmap="ParadoxMG5050"):
        self.comms = _transport  # instance variable unique to each instance
        self.retries = _retries
        self.encrypted = _encrypted
        self.alarmeventmap = _alarmeventmap
        self.alarmregmap = _alarmregmap

        # MyClass = getattr(importlib.import_module("." + self.alarmmodel + "EventMap", __name__))

        try:
            mod = __import__("ParadoxMap", fromlist=[self.alarmeventmap + "EventMap"])
            self.eventmap = getattr(mod, self.alarmeventmap + "EventMap")
        except Exception, e:
            logger.exception("Failed to load Event Map: ", repr(e))
            logger.info("Defaulting to MG5050 Event Map...")
            try:
                mod = __import__("ParadoxMap", fromlist=["ParadoxMG5050EventMap"])
                self.eventmap = getattr(mod, "ParadoxMG5050EventMap")
            except Exception, e:
                logger.exception( "Failed to load Event Map (exiting): ", repr(e))
                sys.exit()

        try:
            mod = __import__("ParadoxMap", fromlist=[self.alarmregmap + "Registers"])
            self.registermap = getattr(mod, self.alarmregmap + "Registers")
        except Exception, e:
            logger.exception( "Failed to load Register Map (defaulting to not update labels from alarm): ", repr(e))
            self.Skip_Update_Labels = 1



            # self.eventmap = ParadoxMG5050EventMap  # Need to check panel type here and assign correct dictionary!
            # self.registermap = ParadoxMG5050Registers  # Need to check panel type here and assign correct dictionary!

    def skipLabelUpdate(self):
        return self.Skip_Update_Labels

    def saveState(self):
        self.eventmap.save()

    def loadState(self):
        logger.debug("Loading previous event states and labels from file")
        self.eventmap.load()

    def login(self, password, Debug_Mode=0): 
        logger.info("Connecting to Alarm System")
        message = '\x72\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw(message, Debug_Mode)

        message = '\x50\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw(message, Debug_Mode)

        message = '\x5f\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw(message, Debug_Mode)

        message = reply
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw( message, Debug_Mode)

        message = '\x50\x00\x1f\xe0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x4f'
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw(message, Debug_Mode)


        message = '\x50\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw(message, Debug_Mode)

        message = '\x50\x00\x0e\x52\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        message = self.format37ByteMessage(message)
        reply = self.readDataRaw(message, Debug_Mode)

        return True

    def format37ByteMessage(self, message):
        checksum = 0

        if len(message) % 37 != 0:
            for val in message:
                checksum += ord(val)

            while checksum > 255:
                checksum = checksum - (checksum / 256) * 256

            message += bytes(bytearray([checksum]))  # Add check to end of message

        return message

    def updateAllLabels(self, Startup_Publish_All_Info="True", Topic_Publish_Labels="True", Debug_Mode=0):
        Alarm_Data['labels'] = dict()

        for func in self.registermap.getsupportedItems():

            logger.debug("Reading from alarm: " + func)

            try:

                register_dict = getattr(self.registermap, "get" + func + "Register")()
                mapping_dict = getattr(self.eventmap, "set" + func)

                total = sum(1 for x in register_dict if isinstance(x, int))

                logger.debug("Amount of numeric items in dictionary to read: " + str(total))

                skip_next = 0
                last_index = -1
                for x in range(1, total + 1):

                    message = register_dict[x]["Send"]
                    try:
                        next_message = register_dict[x + 1]["Send"]
                    except KeyError:
                        skip_next = 1

                    assert isinstance(message, basestring), "Message to be sent is not a string: %r" % message
                    message = message.ljust(36, '\x00')

                    reply = self.readDataRaw(self.format37ByteMessage(message), Debug_Mode)
                    start = reply.find('\x00')

                    if start == -1 or len(reply) < start + 19:
                        logger.warning("Invalid message!")
                        continue

                    if last_index == reply[start + 2]:
                        start += 16

                    last_index = reply[start + 2]

                    finish = start + 3 + 16
                    label = reply[start + 3:finish].strip()
                    mapping_dict(x, label)
                try:
                    completed_dict = getattr(self.eventmap, "getAll" + func)()
                    if Debug_Mode >= 1:
                        logger.info("Labels detected for " + func + ": " + str(completed_dict))
                except Exception, e:
                    logger.exception( "Failed to load supported function's completed mappings after updating: " + repr(e))
                
                Alarm_Data['labels'][func] = completed_dict

                if Startup_Publish_All_Info == "True":
                    topic = func.split("Label")[0]
                    client.publish(Topic_Publish_Labels + "/" + topic[0].upper() + topic[1:] + "s",
                                   ';'.join('{}{}'.format(key, ":" + val) for key, val in completed_dict.items()))


            except Exception, e:
                logger.exception( "Failed to load supported function's mapping: " + repr(e))
        
        return

    def testForEvents(self, Events_Payload_Numeric=0, Debug_Mode=0, timeout=1):
    
        message = self.comms.read(timeout=0.01)
        
        if message is None or len(message) < 2:
            return None

        reply = '.'

        if len(message) > 0:
            if message[0] == '\xe2' or message[0] == '\xe0':
                try:

                    event, subevent = self.eventmap.getEventDescription(ord(message[7]), ord(message[8]))
                    event = event.strip()
                    subevent = subevent.strip()

                    reply = json.dumps({"Event": event, "SubEvent":subevent})
                    logger.info(reply)

                    client.publish(Topic_Publish_Events, reply, qos=0, retain=False)
                    if event.find("Zone ") == 0:
                        client.publish(Topic_Publish_Status + "/Zones/"+subevent.replace(' ','_').title(), event, qos=0, retain=True)
                    elif event == 'Partition status':
                        client.publish(Topic_Publish_Status + "/Partitions/", subevent, qos=0, retain=True)
                    elif event.find('Bell status ') == 0:
                        client.publish(Topic_Publish_Status + "/Bell/", subevent, qos=0, retain=True)
                    elif (event == "Non-reportable event" and subevent.find("arm") >= 0) or event == "Special arming":
                        client.publish(Topic_Publish_Status + "/Partitions/", subevent, qos=0, retain=True)
                    elif event == "Arming with user":
                        client.publish(Topic_Publish_Status + "/Partitions/", event + " " +subevent, qos=0, retain=True)
                    else:
                        client.publish(Topic_Publish_Status + "/System/", event + " -> " + subevent, qos=0, retain=True)

                except ValueError:
                    reply = "No register entry for Event: " + str(ord(message[7])) + ", Sub-Event: " + str(
                        ord(message[8]))

            else:
                reply = "Unknown event: " + " ".join(hex(ord(i)) for i in message)



        return reply

    def readDataRaw(self, request='', Debug_Mode=2):

        self.testForEvents(timeout=0.01)                # First check for any pending events received

        tries = self.retries

        while tries > 0:
            try:
                if len(request) > 0:
                    self.comms.write(request)
                
                inc_data = self.comms.read()
                
                if inc_data is None:
                    if tries > 0:
                        logger.warning("Error reading data from panel, retrying again... (" + str(tries) + ")")
                        tries -= 1
                        time.sleep(0.5)
                        continue
                    elif tries == 0:
                        return ''
                    else:
                        break
                else:
                    return inc_data

            except Exception, e:
                logger.exception("Error reading from panel")
                sys.exit(-1)

    def readDataStruct37(self, inputData='', Debug_Mode=0):  # Sends data, read input data and return the Header and Message

        rawdata = self.readDataRaw(inputData, Debug_Mode)
        return rawdata

    def controlGenericOutput(self, mapping_dict, outputs, state, Debug_Mode=0):

        registers = mapping_dict
        if outputs == "ALL":
            outputs = range(1, 1 + len(Alarm_Data['labels']['outputLabel']))
        else:
            outputs = [output]

        logger.info("Sending generic Output Control: Output: " + str(outputs) + ", State: " + state)

        for output in outputs:

            message = registers[output][state]

            if not isinstance(message, basestring):
                logger.warning("Generic Output: Message to be sent is not a string: %r" % message)
                continue

            message = message.ljust(36, '\x00')

            reply = self.readDataRaw(self.format37ByteMessage(message), Debug_Mode)

        return

    def controlPGM(self, pgm, state="OFF", Debug_Mode=0):
        if pgm == "ALL":
            pgms = range(0, 17)
        else:
            if not isinstance(pgm, int) or not (pgm >= 0 and pgm <= 16):
                logger.warning("Problem with PGM number: %r" % str(pgm))
                return
            pgms = [pgm]

        if not isinstance(state, basestring):
            logger.warning("PGM State given is not a string: %r" % str(state))
            return

        if not state in ["ON", "1", "TRUE", "ENABLE", "OFF", "FALSE", "0", "DISABLE"]:
            logger.warning("PGM State is not given correctly: %r" % str(state))
            return

        for p in pgms:
            self.controlGenericOutput(self.registermap.getcontrolOutputRegister(), p, state, Debug_Mode)

        return

    def controlGenericAlarm(self, mapping_dict, partition, state, Debug_Mode):
        registers = mapping_dict

        logger.info("Sending generic Alarm Control: Partition: " + str(partition) + ", State: " + state)
        if partition == "ALL":
            partition = range(1, 1 + len(Alarm_Data['labels']['partitionLabel']))
        else:
            partition = [partition]

        for p in partition:
            message = registers[p][state]

            message = message.ljust(36, '\x00')

            reply = self.readDataRaw(self.format37ByteMessage(message), Debug_Mode)

        return

    def controlAlarm(self, partition=1, state="Disarm", Debug_Mode=0):

            
        if not isinstance(state, basestring):
            logger.warning("State given is not a string: %r" % str(state))
            return
    
        if partition.upper() == "ALL":
            logger.debug("Setting ALL Partitions")
            if not(state.upper() in self.registermap.getcontrolAlarmRegister()[Alarm_Data['labels']['partitionLabel'].keys()[0]]):
                logger.warning("State is not given correctly: %r" % str(state))
                return
        elif  isinstance(partition, int):
            if not (partition >= 0 and partition <= 16):
                logger.warning("Problem with partition number: %r" % str(partition))
                return
            if not(state.upper() in self.registermap.getcontrolAlarmRegister()[partition]):
                logger.warning("State is not given correctly: %r" % str(state))
                return

        self.controlGenericAlarm(self.registermap.getcontrolAlarmRegister(), partition.upper(), state.upper(), Debug_Mode)

        return

    def disconnect(self, Debug_Mode=0):
        message = "\x70\x00\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x76"
        self.readDataRaw(self.format37ByteMessage(message))

        self.comms.disconnect()


    def keepAlive(self, Debug_Mode=0):
        aliveSeq = 0

        while aliveSeq < 7:
            message = "\x50\x00\x80"
            message += bytes(bytearray([aliveSeq]))
            message += "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

            data = self.readDataRaw(self.format37ByteMessage(message))
            if aliveSeq == 0:
                Alarm_Data['date_time'] = {"year": ord(data[9])*100 + ord(data[10]),
                        "month": ord(data[11]),
                        "day": ord(data[12]),
                        "hours": ord(data[13]),
                        "minutes": ord(data[14])}
            
                voltage =   {'vdc': round(ord(data[15])*(20.3-1.4)/255.0+1.4,1) , 
                            'dc': round(ord(data[16])*22.8/255.0,1),
                            'battery': round(ord(data[17])*22.8/255.0,1)}
                if not 'voltage' in Alarm_Data.keys() or \
                    voltage['vdc'] != Alarm_Data['voltage']['vdc'] or voltage['dc'] != Alarm_Data['voltage']['dc'] or voltage['battery'] != Alarm_Data['voltage']['battery']:
                
                    client.publish(Topic_Publish_Battery, json.dumps(voltage))
                    Alarm_Data['voltage'] = voltage
            
            elif aliveSeq == 1:
                pass

            aliveSeq += 1
        
    def walker(self, ):
        self.zoneTotal = Zone_Amount

        logger.debug("Reading (" + str(Zone_Amount) + ") zone names...")

        for x in range(16, 65535, 32):
            message = "\xe2\x00"
            zone = x
            zone = list(struct.pack("H", zone))
            swop = zone[0]
            zone[0] = zone[1]
            zone[1] = swop

            temp = "".join(zone)
            message += temp

            message += "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            reply = self.readDataRaw(self.format37ByteMessage(message))
        return


if __name__ == '__main__':

    State_Machine = 0
    attempts = 3
    lastKeepAlive = 0

    while True:

        # -------------- Read Config file ----------------
        if State_Machine <= 0:

            logger.info("Reading config.ini file...")

            try:

                Config = ConfigParser.ConfigParser()
                Config.read("config.ini")
                Alarm_Model = Config.get("Alarm", "Alarm_Model")
                Alarm_Registry_Map = Config.get("Alarm", "Alarm_Registry_Map")
                Alarm_Event_Map = Config.get("Alarm", "Alarm_Event_Map")
                Zone_Amount = int(Config.get("Alarm", "Zone_Amount"))
                if Zone_Amount % 2 != 0:
                    Zone_Amount += 1

                MQTT_IP = Config.get("MQTT Broker", "IP")
                MQTT_Port = int(Config.get("MQTT Broker", "Port"))

                Topic_Publish_Events = Config.get("MQTT Topics", "Topic_Publish_Events")
                Events_Payload_Numeric = Config.get("MQTT Topics", "Events_Payload_Numeric")
                Topic_Subscribe_Control = Config.get("MQTT Topics", "Topic_Subscribe_Control")
                Startup_Publish_All_Info = Config.get("MQTT Topics", "Startup_Publish_All_Info")
                Topic_Publish_Labels = Config.get("MQTT Topics", "Topic_Publish_Labels")
                Topic_Publish_AppState = Config.get("MQTT Topics", "Topic_Publish_AppState")
                Startup_Update_All_Labels = Config.get("Application", "Startup_Update_All_Labels")
                Debug_Mode = int(Config.get("Application", "Debug_Mode"))
                if Debug_Mode == 1:
                    logger.setLevel(logging.INFO)
                elif Debug_Mode == 2:
                    logger.setLevel(logging.DEBUG)
                else: 
                    logger.setLevel(logging.WARN)
                logger.info("config.ini file read successfully")
                State_Machine += 1

            except Exception, e:
                logger.exception( "******************* Error reading config.ini file (will use defaults): " + repr(e))
                State_Machine = 1
                attempts = 3
        # -------------- MQTT ----------------
        elif State_Machine == 1:

            try:

                logger.info("Attempting connection to MQTT Broker: " + MQTT_IP + ":" + str(MQTT_Port))
                client = mqtt.Client()
                client.on_connect = on_connect
                client.on_message = on_message

                client.connect(MQTT_IP, MQTT_Port, MQTT_KeepAlive)

                client.loop_start()

                client.subscribe(Topic_Subscribe_Control + "#")

                logger.info("MQTT client subscribed to control messages on topic: " + Topic_Subscribe_Control + "#")

                client.publish(Topic_Publish_AppState,"State Machine 1, Connected to MQTT Broker",0,True)

                State_Machine += 1

            except Exception, e:

                logger.exception( "MQTT connection error (" + str(attempts) + ": " + repr(e))
                time.sleep(attempts * 2)
                attempts -= 1

                if attempts < 1:
                    logger.error("Error within State_Machine: " + str(State_Machine) + ": " + repr(e))
                    State_Machine -= 1
                    logger.debug("Going to State_Machine: " + str(State_Machine))
                    attempts = 3

        # -------------- Login to Module ----------------
        elif State_Machine == 2:

            try:
                client.publish(Topic_Publish_AppState, "State Machine 2, Connecting to Alarm...", 0, True)

                comms = CommSerial(SERIAL_PORT)
                if not comms.connect():
                    logger.critical("Error connecting to Alarm")
                    sys.exit(0)

                client.publish(Topic_Publish_AppState,
                               "State Machine 2, Connected to Alarm, unlocking...",
                               0, True)

                myAlarm = Paradox(comms, 0, 3, Alarm_Event_Map, Alarm_Registry_Map)

                if not myAlarm.login(passw, Debug_Mode):
                    logger.warning("Failed to login & unlock panel, check if another app is using the port. Retrying... ")
                    client.publish(Topic_Publish_AppState,
                                   "State Machine 2, Failed to login & unlock panel, check if another app is using the port. Retrying... ",
                                   0, True)
                    comms.close()
                    time.sleep(Poll_Speed * 20)
                else:
                    client.publish(Topic_Publish_AppState, "State Machine 2, Logged into panel successfully", 0, True)
                    State_Machine += 1

            except Exception, e:
                logger.exception("Error attempting connection to panel (" + str(attempts) + ": " + repr(e))
                client.publish(Topic_Publish_AppState,
                               "State Machine 2, Exception, retrying... (" + str(attempts) + ": " + repr(e),
                               0, True)
                time.sleep(Poll_Speed * 5)
                attempts -= 1

                if attempts < 1:
                    logger.error("Error within State_Machine: " + str(State_Machine) + ": " + repr(e))
                    client.publish(Topic_Publish_AppState, "State Machine 2, Error, moving to previous state", 0, True)
                    State_Machine -= 1
                    logger.error("Going to State_Machine: " + str(State_Machine))
                    attempts = 3
        # -------------- Reading Labels ----------------
        elif State_Machine == 3:

            try:

                if Startup_Update_All_Labels == "True" and myAlarm.skipLabelUpdate() == 0:

                    client.publish(Topic_Publish_AppState, "State Machine 3, Reading labels from alarm", 0, True)

                    logger.info("Updating all labels from alarm")
                    myAlarm.updateAllLabels(Startup_Publish_All_Info, Topic_Publish_Labels, Debug_Mode)

                    State_Machine += 1
                    logger.info("Listening for events...")
                    client.publish(Topic_Publish_AppState, "State Machine 4, Listening for events...", 0, True)
                else:
                    State_Machine += 1
                    logger.info("Listening for events...")
                    client.publish(Topic_Publish_AppState, "State Machine 4, Listening for events...", 0, True)
            except Exception, e:

                logger.exception( "Error reading labels: " + repr(e))
                client.publish(Topic_Publish_AppState, "State Machine 3, Exception: " + repr(e), 0, True)
                time.sleep(Poll_Speed * 5)
                attempts -= 1

                if attempts < 1:
                    logger.error("Error within State_Machine: " + str(State_Machine) + ": " + repr(e))
                    client.publish(Topic_Publish_AppState, "State Machine 3, Error, moving to previous state", 0, True)
                    State_Machine -= 1
                    logger.debug("Going to State_Machine: " + str(State_Machine))

            Alarm_Control_Action = 0
            attempts = 3

            # -------------- Checking Events & Actioning Controls ----------------
        elif State_Machine == 4:

            try:
                # Test for new events & publish to broker
                myAlarm.testForEvents(Events_Payload_Numeric, Debug_Mode)

                # Test for pending Alarm Control
                if Alarm_Control_Action == 1:
                    myAlarm.login(passw)
                    myAlarm.controlAlarm(Alarm_Control_Partition, Alarm_Control_NewState, Debug_Mode)
                    Alarm_Control_Action = 0
                    logger.info( "Listening for events...")
                    client.publish(Topic_Publish_AppState, "State Machine 4, Listening for events...", 0, True)

                # Test for pending Force Output Control
                if Output_FControl_Action == 1:
                    myAlarm.login(passw)
                    myAlarm.controlPGM(Output_FControl_Number, Output_FControl_NewState.upper(), Debug_Mode)
                    Output_FControl_Action = 0
                    logger.info("Listening for events...")
                    client.publish(Topic_Publish_AppState, "State Machine 4, Listening for events...", 0, True)

                # Test for pending Pulse Output Control
                if Output_PControl_Action == 1:
                    myAlarm.login(passw)
                    myAlarm.controlPGM(Output_PControl_Number, Output_PControl_NewState.upper(), Debug_Mode)
                    time.sleep(0.5)
                    if Output_PControl_NewState.upper() in ["ON", "1", "TRUE", "ENABLE"]:
                        myAlarm.controlPGM(Output_PControl_Number, "OFF", Debug_Mode)
                    else:
                        myAlarm.controlPGM(Output_PControl_Number, "ON", Debug_Mode)

                    Output_PControl_Action = 0
                    logger.info("Listening for events...")
                    client.publish(Topic_Publish_AppState, "State Machine 4, Listening for events...", 0, True)
                
                if time.time() > lastKeepAlive + Keep_Alive_Interval:
                    myAlarm.keepAlive(Debug_Mode)
                    lastKeepAlive = time.time()

            except Exception, e:

                logger.exception( "Error during normal poll: " + repr(e) + ", Attempt: " + str(attempts))
                client.publish(Topic_Publish_AppState, "State Machine 4, Exception: " + repr(e), 0, True)
                time.sleep(Poll_Speed * 5)
                attempts -= 1

                if attempts < 1:
                    logger.error("Error within State_Machine: " + str(State_Machine) + ": " + repr(e))
                    State_Machine -= 1
                    client.publish(Topic_Publish_AppState, "State Machine 4, Error, moving to previous state", 0, True)
                    attempts = 3
        elif State_Machine == 10:
            time.sleep(3)

        else:
            State_Machine = 2