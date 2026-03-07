# changed bytes in the control unit are mostly refreshed in the addressParameters struct by retrieving and updating settings

import socket
import datetime
import queue
import time

import paho.mqtt.client as mqttc
import schedule
import logging

class etathermSendReceiveError(Exception):
    pass

class etathermOpenSessionError(Exception):
    pass
# sends frame to the control unit. Frame is complete, with preambule etc. In case of timeout it retransmits the frame
# input variables   a (int) input variable
#                   b (string) input variable
# returns c (int) number of something
class etatherm:

    def __init__(self, hostname="localhost", port=50001, addrBusH=0x00, addrBusL=0x01):

        self.dayCodes = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun", 8: "PWM"}
# self.reqOpCodeRead = 0x08
# self.reqOpCodeWrite = 0x0c
        self.reqDle = 0x10
        self.reqSoh = 0x01
        self.respEtb = 0x17
        self.respHeader = 0xff
        self.reqTrailer = 0xff
        self.etathermHostname = socket.gethostbyname(hostname)
        self.etathermPort = port
        self.reqAddrBusH = addrBusH
        self.reqAddrBusL = addrBusL
        self.commSleep = 0.5
        self.addressParameters = {}
        self.tries = 10
        self.initTries = 3
        self.initTimeout = 5
        self.receiveTimeout = 2
        self.etathermSession = 0
# CMD queue and allowed commands
        self.cmdQueue = queue.SimpleQueue()
        self.CMD_STORE_FOC_TEMPERATURE = 1
        self.CMD_FOC_ACTIVATE = 2
        self.CMD_FOC_DEACTIVATE = 3
        self.CMD_RETRIEVE_ADDR_PARAM = 4
        self.CMD_UPDATE_MQTT = 5
        self.CMD_ACTIVATE_HEATING_MAP = 6
        self.CMD_UPDATE_MQTT_ACTIVE_HEATING_MAP = 7
        self.CMD_GOC_ACTIVATE = 8
        self.CMD_GOC_DEACTIVATE = 9
# MQTT settings
        self.mqttSession = 0
        self.mqttHostname = ""
        self.mqttPort = ""
        self.mqttProtocol = mqttc.MQTTv311
        self.mqttClientID = "etatherm"
        self.mqttQos = 0
        self.mqttKeepAlive = 60
        self.mqttAuth = ""
        self.mqttMsgCount = 1
        self.mqttRetained = False
        self.mqttWill = {}
        self.mqttTls = {}
        self.mqttTransport = "tcp"
#logging settings
        logging.basicConfig(filename='/var/log/etatherm.log', format='%(asctime)s-%(levelname)s-%(message)s', level=logging.DEBUG)
        logging.debug(
            "Etatherm library initialized. Etatherm device at %s", self.etathermHostname + "/" + str(self.etathermPort))
        self.readConfigFile("")
#        logging.debug(self.HOMEOFFICEWINTERMAP)
        logging.debug("Initializing attributes")
# preset constants
        self.FOC_TYPE_OFF = "off"
        self.FOC_TYPE_HOLD = "hold"
        self.FOC_TYPE_OPCHANGE = "fastchange"
        self.HVAC_MODE_AUTO = "auto"
        self.HVAC_MODE_OFF = "off"
        self.HVAC_MODE_HEAT = "heat"
        self.DEVICE_TYPE_UNDEF = "undefined"
        self.DEVICE_TYPE_NOTUSED = "not_used"
        self.DEVICE_TYPE_REGULATION = "regulation"
        self.DEVICE_TYPE_HEATER = "heater"
        self.DEVICE_TYPE_SWITCH1 = "switch1"
        self.DEVICE_TYPE_SWITCH2 = "switch2"

        logging.debug("Etatherm session opened")

    # TODO: should read config file and initialize variables
    # input variables configFilePath    file path with configuration information
    # returns   1: valid
    #           0: invalid
    def readConfigFile(self, configFilePath):

        self.heatingMaps = { 1 : {'name' : 'Home Office letni', 'type' : 'ho',
                                1 : [1, 1, 1, 1, 1, 1, 1, 96], 2 : [2, 2, 2, 2, 2, 2, 2, 96],
                                3 :  [3, 3, 3, 3, 3, 3, 3, 96], 4 : [4, 4, 4, 4, 4, 4, 4, 96],
                                5 : [5, 5, 5, 5, 5, 5, 5, 96], 6 : [6, 6, 6, 6, 6, 6, 6, 96],
                                7 : [7, 7, 7, 7, 7, 7, 7, 96], 8 : [8, 8, 8, 8, 8, 8, 8, 96],
                                9 : [9, 9, 9, 9, 9, 9, 9, 96], 10 : [10, 10, 10, 10, 10, 10, 10, 96],
                                11 : [11, 11, 11, 11, 11, 11, 11, 96], 12 : [12, 12, 12, 12, 12, 12, 12, 96],
                                13 : [13, 13, 13, 13, 13, 13, 13, 96], 14 : [14, 14, 14, 14, 14, 14, 14, 96],
                                15 : [94, 94, 94, 94, 94, 94, 94, 96], 16 : [95, 95, 95, 95, 95, 95, 95, 97] },
                             2 : {'name' : 'Home Office zimni', 'type' : 'ho',
                                1 : [15, 15, 15, 15, 15, 15, 15, 96], 2 : [16, 16, 16, 16, 16, 16, 16, 96],
                                3 : [17, 17, 17, 17, 17, 17, 17, 96], 4 : [18, 18, 18, 18, 18, 18, 18, 96],
                                5 : [19, 19, 19, 19, 19, 19, 19, 96], 6: [20, 20, 20, 20, 20, 20, 20, 96],
                                7 : [21, 21, 21, 21, 21, 21, 21, 96], 8 : [22, 22, 22, 22, 22, 22, 22, 96],
                                9 : [23, 23, 23, 23, 23, 23, 23, 96], 10 : [24, 24, 24, 24, 24, 24, 24, 96],
                                11 : [25, 25, 25, 25, 25, 25, 25, 96], 12 : [26, 26, 26, 26, 26, 26, 26, 96],
                                13 : [27, 27, 27, 27, 27, 27, 27, 96], 14 : [28, 28, 28, 28, 28, 28, 28, 96],
                                15 : [94, 94, 94, 94, 94, 94, 94, 96], 16 : [95, 95, 95, 95, 95, 95, 95, 97] },
                             3 : {'name': 'Letni', 'type': 'normal',
                                1 : [29, 29, 29, 29, 29, 43, 43, 96], 2 : [30, 30, 30, 30, 30, 44, 44, 96],
                                3 : [31, 31, 31, 31, 31, 45, 45, 96], 4 : [32, 32, 32, 32, 32, 46, 46, 96],
                                5 : [33, 33, 33, 33, 33, 47, 47, 96], 6 : [34, 34, 34, 34, 34, 48, 48, 96],
                                7 : [35, 35, 35, 35, 35, 49, 49, 96], 8 : [36, 36, 36, 36, 36, 50, 50, 96],
                                9 : [37, 37, 37, 37, 37, 51, 51, 96], 10 : [38, 38, 38, 38, 38, 52, 52, 96],
                                11 : [39, 39, 39, 39, 39, 53, 53, 96], 12: [40, 40, 40, 40, 40, 54, 54, 96],
                                13 : [41, 41, 41, 41, 41, 55, 55, 96], 14: [42, 42, 42, 42, 42, 56, 56, 96],
                                15 : [94, 94, 94, 94, 94, 94, 94, 96], 16: [95, 95, 95, 95, 95, 95, 95, 97] },
                             4 : {'name': 'Zimni', 'type': 'normal',
                                1 : [57, 57, 57, 57, 57, 71, 71, 96], 2 : [58, 58, 58, 58, 58, 72, 72, 96],
                                3 : [59, 59, 59, 59, 59, 73, 73, 96], 4 : [60, 60, 60, 60, 60, 74, 74, 96],
                                5 : [61, 61, 61, 61, 61, 75, 75, 96], 6 : [62, 62, 62, 62, 62, 76, 76, 96],
                                7 : [63, 63, 63, 63, 63, 77, 77, 96], 8 : [64, 64, 64, 64, 64, 78, 78, 96],
                                9 : [65, 65, 65, 65, 65, 79, 79, 96], 10 : [66, 66, 66, 66, 66, 80, 80, 96],
                                11 : [67, 67, 67, 67, 67, 81, 81, 96], 12 : [68, 68, 68, 68, 68, 82, 82, 96],
                                13 : [69, 69, 69, 69, 69, 83, 83, 96], 14 : [70, 70, 70, 70, 70, 84, 84, 96],
                                15 : [94, 94, 94, 94, 94, 94, 94, 96], 16 : [95, 95, 95, 95, 95, 95, 95, 97] }}
        self.SPECHEATERMAP = ["Kotel", 95]
        self.SPECPWMMAP = ["PWM", 96]
        self.SPECPUMPMAP = ["Cerpadlo", 94]
        return 0

    # validates control unit response. Response is invalid if first five bytes do not contain 0xff10170000 as defined in the documentation
    # input variables response  response bytes
    # returns   1: valid
    #           0: invalid
    def validateResponse(self, response):

        length = len(response)
#        logging.debug("Response",response,length)
        if ((response[0] == 0xff) and (response[1] == 0x10) and (response[2] == 0x17) and (
                response[length - 4] == 0x00) and (response[length - 3] == 0x00)):
#            logging.debug("Response valid")
            return 0
        else:
#            logging.debug("Response invalid")
            return 1

    # sends frame to the control unit. Frame is complete, with preambule etc. In case of timeout it retransmits the frame
    # input variables   reqFrame request frame bytes
    # returns response frame or invalid frame
    def etathermSendFrame(self, reqFrame):

        responseValid = 0
#        raise etathermSendReceiveError
#        logging.debug("Continue after raise in etathermSendFrame")
        for i in range(0, self.tries):
            try:
                self.etathermSession.send(reqFrame)
# TODO: mozna sem zabudovat zavreni a znovu otevreni socketu?
            except socket.timeout as err:
                logging.error("Socket timeout on send, resending frame %s", reqFrame.hex())
                continue
            except socket.error as err:
                logging.error("Socket error on send, resending frame", reqFrame.hex())
                continue

            try:
                respFrame = self.etathermSession.recv(100)
            except socket.timeout as err:
                logging.error("Socket timeout on receive, resending frame %s", reqFrame.hex())
                continue
            except socket.error as err:
                logging.error("Socket error on receive, resending frame %s", reqFrame.hex())
                continue

            if (self.validateResponse(respFrame) == 0):
                responseValid = 1
                break

        if (responseValid == 1):
            return respFrame
        else:
#            return invalidFrame
            raise etathermSendReceiveError

    # TODO: retrieves temperature offset
    # -> dodelat!!!!!!
    def retrieveTemperatureOffset(self):

        return 5

    # retrieves real temperature of all devices on the BUS w/ offset and updates addressParameters
    # input variables  none
    # returns real temperature dictionary
    def retrieveRealTemperature(self):

        realTemp = {}
        reqDelay = 0x02
        reqAddrB0 = 0x00
        reqAddrB1 = 0x60
        reqResponseLen = 0x70
        reqOpCode = 0x08

        logging.debug("retrieveRealTemperature called")
        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                reqResponseLen | reqOpCode) + reqDelay) & 0xff
        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                reqResponseLen | reqOpCode) ^ reqDelay) & 0xff

        reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                              (reqResponseLen | reqOpCode), reqDelay, reqAdds, reqXors, self.reqTrailer,
                              self.reqTrailer])
        try:
            respFrame = self.etathermSendFrame(reqFrame)
        except etathermSendReceiveError:
            return realTemp
        else:
            for j in range(1, 17):
                realTemp.update({j: respFrame[j + 4]})
            return realTemp

    # starts service mode
    def startServiceMode(self):

        # Enter Service mode

        reqDelay = 0x00
        reqAddrB0 = 0xff
        reqAddrB1 = 0x01
        reqResponseLen = 0x10
        reqOpCode = 0x0c
        reqData = 0x00
        self.reqAddrBusH = 0x00
        self.reqAddrBusL = 0x01
        # reqDelay nema u zapisu co delat
        #        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
        #                reqResponseLen | reqOpCode) + reqDelay + reqData) & 0xff
        #        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
        #                reqResponseLen | reqOpCode) ^ reqDelay ^ reqData) & 0xff

        #        reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
        #                              (reqResponseLen | reqOpCode), reqDelay, reqData, reqAdds, reqXors, self.reqTrailer,
        #                              self.reqTrailer])
        logging.debug("startServiceMode called")
        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                reqResponseLen | reqOpCode) + reqData) & 0xff
        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                reqResponseLen | reqOpCode) ^ reqData) & 0xff

        reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                              (reqResponseLen | reqOpCode), reqData, reqAdds, reqXors, self.reqTrailer,
                              self.reqTrailer])
        try:
            respFrame = self.etathermSendFrame(reqFrame)
        except etathermSendReceiveError:
            return 1
        else:
            return 0

    # stops service mode
    def stopServiceMode(self):

        # Return from Service mode

        reqDelay = 0x00
        reqAddrB0 = 0xff
        reqAddrB1 = 0x02
        reqResponseLen = 0x10
        reqOpCode = 0x0c
        reqData = 0x00
        #        self.reqAddrBusH = 0x00
        #        self.reqAddrBusL = 0x01

        # reqDelay u zapisu nema co delat
        #        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
        #                reqResponseLen | reqOpCode) + reqDelay + reqData) & 0xff
        #        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
        #                reqResponseLen | reqOpCode) ^ reqDelay ^ reqData) & 0xff

        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                reqResponseLen | reqOpCode) + reqData) & 0xff
        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                reqResponseLen | reqOpCode) ^ reqData) & 0xff

        #        reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
        #                              (reqResponseLen | reqOpCode), reqDelay, reqData, reqAdds, reqXors, self.reqTrailer,
        #                              self.reqTrailer])

        reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                              (reqResponseLen | reqOpCode), reqData, reqAdds, reqXors, self.reqTrailer,
                              self.reqTrailer])

        logging.debug("stopServiceMode called")
        try:
            respFrame = self.etathermSendFrame(reqFrame)
        except etathermSendReceiveError:
            return 1
        else:
            return 0

    # retrieves immediate (not in device stored) real temperatures of all devices on the BUS and updates addressParameters
    # input variables none
    # returns none
    def retrieveRealTemperaturesNow(self):
        self.startServiceMode()
        self.stopServiceMode()
        realTemperature = self.retrieveRealTemperatures()
        return realTemperature


    def retrieveActiveHeatingProgram(self, deviceID):

        BASEADDR = 0x1100
        BASEADDRINCREMENT = 0x10
        PROGRAMOFFSET = 0x08
        addrIncrement = BASEADDRINCREMENT * (deviceID - 1)
        programAddr = BASEADDR + addrIncrement + PROGRAMOFFSET
        reqDelay = 0x02
        reqAddrB0 = (programAddr & 0xff00) >> 8
        reqAddrB1 = programAddr & 0x00ff
        reqResponseLen = 0x30
        reqOpCode = 0x08
        activeHeatingProgram = {}

        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                reqResponseLen | reqOpCode) + reqDelay) & 0xff
        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                reqResponseLen | reqOpCode) ^ reqDelay) & 0xff

        reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                              (reqResponseLen | reqOpCode), reqDelay, reqAdds, reqXors, self.reqTrailer,
                              self.reqTrailer])

        try:
            respFrame = self.etathermSendFrame(reqFrame)
        except etathermSendReceiveError:
            return activeHeatingProgram
        else:
            activeHeatingProgram = {"DeviceID": deviceID, self.dayCodes[1]: respFrame[5] + 1,
                              self.dayCodes[2]: respFrame[6] + 1, self.dayCodes[3]: respFrame[7] + 1,
                              self.dayCodes[4]: respFrame[8] + 1, self.dayCodes[5]: respFrame[9] + 1,
                              self.dayCodes[6]: respFrame[10] + 1, self.dayCodes[7]: respFrame[11] + 1,
                              self.dayCodes[8]: respFrame[12] + 1}
            return activeHeatingProgram

    # retrieves active programs of all device on the bus
    def retrieveAllActiveHeatingPrograms(self):

        BASEADDR = 0x1100
        BASEADDRINCREMENT = 0x10
        PROGRAMOFFSET = 0x08
        reqDelay = 0x02
        reqResponseLen = 0x30
        reqOpCode = 0x08
        allActiveHeatingPrograms = []
        activeProgram = {}

        for deviceBusId in range(1, 17):
            addrIncrement = BASEADDRINCREMENT * (deviceBusId - 1)
            programAddr = BASEADDR + addrIncrement + PROGRAMOFFSET
            reqAddrB0 = (programAddr & 0xff00) >> 8
            reqAddrB1 = programAddr & 0x00ff

            reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                    reqResponseLen | reqOpCode) + reqDelay) & 0xff
            reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                    reqResponseLen | reqOpCode) ^ reqDelay) & 0xff

            reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                                  (reqResponseLen | reqOpCode), reqDelay, reqAdds, reqXors, self.reqTrailer,
                                  self.reqTrailer])

            try:
                respFrame = self.etathermSendFrame(reqFrame)
            except etathermSendReceiveError:
                allActiveHeatingPrograms = []
                return allActiveHeatingPrograms
            else:
                activeProgram = {"DeviceID": deviceBusId, self.dayCodes[1]: respFrame[5] + 1,
                                  self.dayCodes[2]: respFrame[6] + 1, self.dayCodes[3]: respFrame[7] + 1,
                                  self.dayCodes[4]: respFrame[8] + 1, self.dayCodes[5]: respFrame[9] + 1,
                                  self.dayCodes[6]: respFrame[10] + 1,
                                  self.dayCodes[7]: respFrame[11] + 1, self.dayCodes[8]: respFrame[12] + 1}
                allActiveHeatingPrograms.append(activeProgram)
        return allActiveHeatingPrograms

    # upload specified program map for all devices on the bus
    def storeActivatedHeatingMap(self, heatingMapID):

        deviceBusId = 1

        BASEADDR = 0x1100
        BASEADDRINCREMENT = 0x10
        PROGRAMOFFSET = 0x08

        reqDataLen = 0x70
        reqOpCode = 0x0c
        invalidResponse = 0

        logging.debug("storeActivatedHeatingMap called")
        self.etathermSessionOpen()
        for deviceBusId in range(1, 17):
            addrIncrement = BASEADDRINCREMENT * (deviceBusId - 1)
            programAddr = BASEADDR + addrIncrement + PROGRAMOFFSET
            reqAddrB0 = (programAddr & 0xff00) >> 8
            reqAddrB1 = programAddr & 0x00ff
            print(self.heatingMaps[heatingMapID][deviceBusId])

            reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                    reqDataLen | reqOpCode) + self.heatingMaps[heatingMapID][deviceBusId][0] - 1 + self.heatingMaps[heatingMapID][deviceBusId][1] - 1 +
                       self.heatingMaps[heatingMapID][deviceBusId][2] - 1 + self.heatingMaps[heatingMapID][deviceBusId][3] - 1 + self.heatingMaps[heatingMapID][deviceBusId][
                           4] - 1 + self.heatingMaps[heatingMapID][deviceBusId][5] - 1 + self.heatingMaps[heatingMapID][deviceBusId][6] - 1 +
                       self.heatingMaps[heatingMapID][deviceBusId][7] - 1) & 0xff
            reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                    reqDataLen | reqOpCode) ^ self.heatingMaps[heatingMapID][deviceBusId][0] - 1 ^ self.heatingMaps[heatingMapID][deviceBusId][1] - 1 ^
                       self.heatingMaps[heatingMapID][deviceBusId][2] - 1 ^ self.heatingMaps[heatingMapID][deviceBusId][3] - 1 ^ self.heatingMaps[heatingMapID][deviceBusId][
                           4] - 1 ^ self.heatingMaps[heatingMapID][deviceBusId][5] - 1 ^ self.heatingMaps[heatingMapID][deviceBusId][6] - 1 ^
                       self.heatingMaps[heatingMapID][deviceBusId][7] - 1) & 0xff

            reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                                  (reqDataLen | reqOpCode), self.heatingMaps[heatingMapID][deviceBusId][0] - 1,
                                  self.heatingMaps[heatingMapID][deviceBusId][1] - 1, self.heatingMaps[heatingMapID][deviceBusId][2] - 1,
                                  self.heatingMaps[heatingMapID][deviceBusId][3] - 1, self.heatingMaps[heatingMapID][deviceBusId][4] - 1,
                                  self.heatingMaps[heatingMapID][deviceBusId][5] - 1, self.heatingMaps[heatingMapID][deviceBusId][6] - 1,
                                  self.heatingMaps[heatingMapID][deviceBusId][7] - 1, reqAdds, reqXors, self.reqTrailer,
                                  self.reqTrailer])
            try:
                respFrame = self.etathermSendFrame(reqFrame)
            except etathermSendReceiveError:
                self.etathermSessionClose()
                return 1
        self.mqttUpdateActiveHeatingMap()
        self.etathermSessionClose()
        return 0

    # retrieves target temperature w/ offset of all devices on the BUS and updates addressParameters
    # input variables none
    # returns targetTemo dictionary
    @property
    def retrieveTargetTemperature(self):

        targetTemp = {}
        reqDelay = 0x02
        reqAddrB0 = 0x00
        reqAddrB1 = 0x70
        reqResponseLen = 0x70
        reqOpCode = 0x08

        logging.debug("retrieveTargetTemperature called")
        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                reqResponseLen | reqOpCode) + reqDelay) & 0xff
        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                reqResponseLen | reqOpCode) ^ reqDelay) & 0xff

        reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                              (reqResponseLen | reqOpCode), reqDelay, reqAdds, reqXors, self.reqTrailer,
                              self.reqTrailer])
        try:
            respFrame = self.etathermSendFrame(reqFrame)
        except etathermSendReceiveError:
            return targetTemp
        else:
            for j in range(1, 17):
                targetTemp.update({j: respFrame[j + 4] & 0x1f})
            return targetTemp

    # retrieves names of all devices on the BUS
    # input variables s: open socket
    # returns address names dictionary indexed by device ID
    def retrieveAddressNames(self):
        reqDelay = 0x02
        reqOpCode = 0x08

        # retrieves address names
        reqResponseLen = 0x30
        BASEADDR = 0x1030
        BASEADDRINCREMENT = 0x08
        addressNames = {}
        invalidResponse = 0

        logging.debug("retrieveAddressNames called")
        for deviceBusId in range(1, 17):
            addrIncrement = BASEADDRINCREMENT * (deviceBusId - 1)
            namesAddr = BASEADDR + addrIncrement
            reqAddrB0 = (namesAddr & 0xff00) >> 8
            reqAddrB1 = namesAddr & 0x00ff

            reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                    reqResponseLen | reqOpCode) + reqDelay) & 0xff
            reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                    reqResponseLen | reqOpCode) ^ reqDelay) & 0xff

            reqFrame = bytearray(
                [self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                 (reqResponseLen | reqOpCode), reqDelay, reqAdds, reqXors, self.reqTrailer,
                 self.reqTrailer])
            try:
                respFrame = self.etathermSendFrame(reqFrame)
            except etathermSendReceiveError:
#                logging.debug("retrieveAddressNames etathermSendReceiveError")
                addressNames = {}
                return addressNames
            else:
                addressNames.update({deviceBusId: respFrame[5:13].decode('cp1250').rstrip('\x00')})
        return addressNames

    # retrieves Global Operational Change parameters of all devices on the BUS
    # input variables s: open socket
    # returns GOC parameters dictionary indexed by device ID
    def retrieveGOCParameters(self):

        reqDelay = 0x02
        reqOpCode = 0x08
        reqResponseLen = 0x70
        BASEADDR = 0x10F0
        globalTempChange = {}

        logging.debug("retrieveGOCParameters")

        reqAddrB0 = (BASEADDR & 0xff00) >> 8
        reqAddrB1 = BASEADDR & 0x00ff

        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                reqResponseLen | reqOpCode) + reqDelay) & 0xff
        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                reqResponseLen | reqOpCode) ^ reqDelay) & 0xff

        reqFrame = bytearray(
            [self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
             (reqResponseLen | reqOpCode), reqDelay, reqAdds, reqXors, self.reqTrailer,
             self.reqTrailer])
        try:
            respFrame = self.etathermSendFrame(reqFrame)
        except etathermSendReceiveError:
            return globalTempChange
        else:
            globalTempChangeLength = 0
            for j in range(1, 17):
                globalTempChange.update({j: respFrame[j + 4]})
                globalTempChangeLength = globalTempChangeLength + ((respFrame[j + 4] & 0x80) >> 7 << (j - 1))
            globalTempChange.update({"GTCLength": globalTempChangeLength})
            return globalTempChange

    # returns Fast Operational Change parameters of the selected device
    # input variables deviceBusID: selected device ID
    # returns FOC parameters dictionary for the seected device ID
    def getFOCParameters(self, deviceID):

        logging.debug("getFOCParameters called")
        focParams = self.addressParameters[deviceID]["opChangeAll"]
        return focParams

    # retrieves Fast Operational Change parameters of all devices on the BUS
    # input variables s: open socket
    # returns FOC parameters dictionary indexed by device ID
    def retrieveFOCParameters(self):

        reqDelay = 0x02
        reqOpCode = 0x08
        reqResponseLen = 0x70
        BASEADDR = 0x10B0
        BASEADDRINCREMENT = 0x10
        fastTempChange = {}
        ftc = []
        invalidResponse = 0

        logging.debug("retrieveFOCParameters called")
        # 16 bytes of data in 4 iterations; each FTC information contains 4 bytes of data * 16 addresses = 64 bytes
        for i in range(1, 5):
            addrIncrement = BASEADDRINCREMENT * (i - 1)
            attribAddr = BASEADDR + addrIncrement
            reqAddrB0 = (attribAddr & 0xff00) >> 8
            reqAddrB1 = attribAddr & 0x00ff

            reqAdds = (
                              self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                              reqResponseLen | reqOpCode) + reqDelay) & 0xff
            reqXors = (
                              self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                              reqResponseLen | reqOpCode) ^ reqDelay) & 0xff

            reqFrame = bytearray(
                [self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                 (reqResponseLen | reqOpCode), reqDelay, reqAdds, reqXors, self.reqTrailer,
                 self.reqTrailer])
            try:
                respFrame = self.etathermSendFrame(reqFrame)
            except etathermSendReceiveError:
                fastTempChange = {}
                return fastTempChange
            else:
                # each 5th to 21st byte of the response frame contains FastOperationalChange data, 1st four is packet header
                for j in range(5, 21):
                    #                logging.debug("FOC bytes",hex(respFrame[j]))
                    ftc.append(respFrame[j])
        for i in range(0, 16):
            ftc1 = []
            for j in range(0, 4):
                ftc1.append(ftc[4 * i + j])
            fastTempChange.update({(i + 1): ftc1})
        return fastTempChange

    # retrieves address parameters for all devices on the BUS
    # input variables none
    # returns address parameters dictionary indexed by device ID
    def retrieveAddressParameters(self):

        reqDelay = 0x02
        reqOpCode = 0x08
        reqResponseLen = 0x70
        BASEADDR = 0x1100
        BASEADDRINCREMENT = 0x10
        invalidResponse = 0
        addressParams = {}
        addressParameters = {}

        logging.debug("retrieveAddressParameters called")
        for j in range(1, 17):
            addrIncrement = BASEADDRINCREMENT * (j - 1)
            attribAddr = BASEADDR + addrIncrement
            reqAddrB0 = (attribAddr & 0xff00) >> 8
            reqAddrB1 = attribAddr & 0x00ff

            reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                    reqResponseLen | reqOpCode) + reqDelay) & 0xff
            reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                    reqResponseLen | reqOpCode) ^ reqDelay) & 0xff

            reqFrame = bytearray(
                [self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                 (reqResponseLen | reqOpCode), reqDelay, reqAdds, reqXors, self.reqTrailer,
                 self.reqTrailer])

            try:
                respFrame = self.etathermSendFrame(reqFrame)
            except etathermSendReceiveError:
                addressParameters = {}
                return addressParameters
            else:
                deviceType = self.DEVICE_TYPE_UNDEF
                if (respFrame[5] & 0x07) == 0:
                    deviceType = self.DEVICE_TYPE_NOTUSED
                if (respFrame[5] & 0x07) == 1:
                    deviceType = self.DEVICE_TYPE_REGULATION
                if (respFrame[5] & 0x07) == 2:
                    deviceType = self.DEVICE_TYPE_HEATER
                if (respFrame[5] & 0x07) == 3:
                    deviceType = self.DEVICE_TYPE_SWITCH1
                if (respFrame[5] & 0x07) == 4:
                    deviceType = self.DEVICE_TYPE_SWITCH2

                addressParams = {
                    #                "deviceTypeAll": (respFrame[5]),
                    "deviceType": deviceType,
                    "serviceTime": ((respFrame[5]) & 0x08) >> 3,
                    "controlsSwitch1": ((respFrame[5]) & 0x10) >> 4,
                    "controlsSwitch2": ((respFrame[5]) & 0x20) >> 5,
                    "devicePass": respFrame[6],
                    "tempOffset": respFrame[7],
                    "opChangeAll": respFrame[8],
                    "opChangeTemp": (respFrame[8] & 0x1f),
                    "opChangeHoldActive": (respFrame[8] & 0x20) >> 5,
                    "opChangeEndNextYear": (respFrame[8] & 0x40) >> 6,
                    "opChangeStartNextYear": (respFrame[8] & 0x80) >> 7,
                    #                 "opChangeStartTime":
                    #                 "opChangeEndTime":
                    "opChangeStartByteHigh": respFrame[9],
                    "opChangeStartByteLow": respFrame[10],
                    "opChangeEndByteHigh": respFrame[11],
                    "opChangeEndByteLow": respFrame[12],
                    "activeHeatingMap" : [
                        respFrame[13]+1,
                        respFrame[14]+1,
                        respFrame[15]+1,
                        respFrame[16]+1,
                        respFrame[17]+1,
                        respFrame[18]+1,
                        respFrame[19]+1,
                        respFrame[20]+1
                    ]
                }
                addressParameters.update({j: addressParams})

        return addressParameters

    # stores FTC Parameters into internal parameters structure and writes data to the device
    # into ROZ registry
    # temperature is real, length in num*15minutes
    # input variables   deviceBusID: ID of the device on the BUS
    #                   type: type of the FTC
    #                   temperature: temperature of the FTC
    #                   length: length of the FTC in n*15 minutes
    #  returns true or false
    def storeFOCParams(self, deviceID, type, temperature, length):

        reqOpCode = 0x0c
        reqResponseLen = 0x30
        BASEADDR = 0x10B0
        fastChangeModeSetLength = 0x04

        logging.debug("retrieveFOCParameters called")
        #        logging.debug(self.addressParameters[deviceBusID])
        if self.verifyFTCModeType(type) == 1:
            return 1
        self.addressParameters[deviceID]["fastChangeType"] = type
        self.addressParameters[deviceID]["fastChangeTemp"] = temperature
        self.addressParameters[deviceID]["fastChangeLength"] = length
        #        logging.debug(self.addressParameters[deviceBusID])

        addrIncrement = (deviceID - 1) * fastChangeModeSetLength
        attribAddr = BASEADDR + addrIncrement
        reqAddrB0 = (attribAddr & 0xff00) >> 8
        reqAddrB1 = attribAddr & 0x00ff
        #        logging.debug(hex(reqAddrB0),hex(reqAddrB1))

        reqData = self.makeFTCParamsPayload(deviceID, type, temperature, length)
        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                reqResponseLen | reqOpCode) + reqData[0] + reqData[1] + reqData[2] + reqData[3]) & 0xff
        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                reqResponseLen | reqOpCode) ^ reqData[0] ^ reqData[1] ^ reqData[2] ^ reqData[3]) & 0xff

        reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                              (reqResponseLen | reqOpCode), reqData[0], reqData[1], reqData[2], reqData[3], reqAdds,
                              reqXors, self.reqTrailer,
                              self.reqTrailer])

        #        logging.debug(reqFrame.hex())
        try:
            respFrame = self.etathermSendFrame(reqFrame)
        except etathermSendReceiveError:
            return 1
        else:
            return 0

    # creates 4 bytes array of the FOC Payload
    # input variables   deviceID: ID of the device on the BUS
    #                   type: type of the FOC
    #                   temperature: temperature to set
    #                   length: length of the FTC
    # returns true or false
    def makeFOCParamsPayload(self, deviceID, type, temperature, length):

        payload = [0, 0, 0, 0]

        if self.verifyFTCModeType(type) == 0:
            return 1
        temperature = temperature - self.addressParameters[deviceID]["tempOffset"]
        payload[0] = temperature
        if type == self.FOC_TYPE_HOLD:
            payload[0] = payload[0] | (0x1 << 5)
        if type == self.FOC_TYPE_OPCHANGE:
            payload[0] = payload[0] | (0x2 << 5)
        if type == self.FOC_TYPE_OFF:
            payload[0] = payload[0] | (0x0 << 5)

        payload[1] = (length & 0xff00) >> 8
        payload[2] = length & 0xff
        return payload

    # verifies FTC Mode Type
    # input variables type: FTC type
    # returns true or false
    def verifyFTCModeType(self, type):

        logging.debug("verifyFTCModeType called")
        if (type == self.FOC_TYPE_HOLD) or (type == self.FOC_TYPE_OPCHANGE) or (type == self.FOC_TYPE_OFF):
            return 0
        else:
            logging.debug("Bad FOC mode type: %s", type)
            return 1

    # creates FOC time payload from datetime
    # used to create payload of start and end FOC time
    def makeFOCTimeLengthPayload(self, changeTime):

        timePayload = (int(changeTime.minute) // 15) | (int(changeTime.hour) << 2) | (int(changeTime.day) << 7) | (
                    int(changeTime.month) << 12)
        return timePayload



    # activates preset FOC = reads FOC parameters from the struct, calculates start/end time and temperature
    # and sends it to the device; FOC activation is just setting of start and end time
    # input variables   deviceID: int ID of the device
    # returns 1 or 0 according to the operation result

    def activateFOC(self, deviceID):
        length = 0
        temperature = 0
        payload = []
        reqOpCode = 0x0c
        reqResponseLen = 0x40
        BASEADDR = 0x1100
        addrIncrement = 0x10
        fastChangeModeOffset = 0x03
        ftcByte = 0

        logging.debug("activateFOC called")
        length = self.addressParameters[deviceID]["opChangePresetLength"] * 15
        start = datetime.datetime.now()
        end = start + datetime.timedelta(minutes=length)
        startPayload = self.makeFOCTimeLengthPayload(start)
        endPayload = self.makeFOCTimeLengthPayload(end)
        s = start.strftime("%Y-%m-%d %H:%M:%S")
        e = end.strftime("%Y-%m-%d %H:%M:%S")
#        self.addressParameters[deviceID].update({"opChangeStartTime": s, "opChangeEndTime": e})
#        temperature = self.addressParameters[deviceID]["opChangePresetTemp"]
        logging.debug("Activating FOC temperature for device %d %d", deviceID, self.addressParameters[deviceID]["opChangeTemp"]+self.addressParameters[deviceID]["tempOffset"])
        type = self.addressParameters[deviceID]["opChangePresetType"]
        #        logging.debug("%s", type)
        ftcByte = self.addressParameters[deviceID]["opChangeTemp"]
        if type == self.FOC_TYPE_HOLD:
            ftcByte = ftcByte | 0x20
        if end.year > start.year:
            ftcByte = ftcByte | 0x40
            logging.debug("end next year")
        #        logging.debug(hex(ftcByte))

        attribAddr = BASEADDR + (deviceID - 1) * addrIncrement + fastChangeModeOffset
        reqAddrB0 = (attribAddr & 0xff00) >> 8
        reqAddrB1 = attribAddr & 0x00ff
        #        logging.debug(hex(reqAddrB0),hex(reqAddrB1))
        #        logging.debug(endPayload)
        #        logging.debug(hex(endPayload & 0xff00))
        #        logging.debug(hex(startPayload & 0x00ff))
        #        logging.debug(hex((startPayload & 0xff00)>>8))
        #        logging.debug(hex(endPayload & 0x00ff))
        #        logging.debug(hex((endPayload & 0xff00)>>8))
        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                reqResponseLen | reqOpCode) + ftcByte + ((startPayload & 0xff00) >> 8) + (startPayload & 0x00ff) + (
                               (endPayload & 0xff00) >> 8) + (endPayload & 0x00ff)) & 0xff
        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                reqResponseLen | reqOpCode) ^ ftcByte ^ ((startPayload & 0xff00) >> 8) ^ (startPayload & 0x00ff) ^ (
                               (endPayload & 0xff00) >> 8) ^ (endPayload & 0x00ff)) & 0xff

        reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                              (reqResponseLen | reqOpCode), ftcByte, (startPayload & 0xff00) >> 8,
                              startPayload & 0x00ff, (endPayload & 0xff00) >> 8, (endPayload & 0x00ff), reqAdds,
                              reqXors, self.reqTrailer, self.reqTrailer])

        #        logging.debug("ramec %s",reqFrame.hex())
        self.etathermSessionOpen()
        try:
            respFrame = self.etathermSendFrame(reqFrame)
        except etathermSendReceiveError:
#           logging.debug("Error activating FOC")
            self.etathermSessionClose()
            return 1
        else:
#           logging.debug("FOC activated")
            self.etathermSessionClose()
            return 0



    def deactivateFOC(self, deviceID):
        length = 0
        temperature = 0
        payload = []
        reqOpCode = 0x0c
        reqResponseLen = 0x40
        BASEADDR = 0x1100
        addrIncrement = 0x10
        fastChangeModeOffset = 0x03
        ftcByte = 0

        logging.debug("deactivateFOC called")
        # 24.12.2023 nahrazen start a end capturovane hodnoty za vypocet 1.1. daneho roku
        #startPayload = 0x1080
        #endPayload = 0x1080
#        start = self.convertFOCBytesToTimeString(startPayload, 0)
#        end = self.convertFOCBytesToTimeString(endPayload, 0)
        start = datetime.datetime(datetime.date.today().year, 1, 1, 00, 00)
        end = datetime.datetime(datetime.date.today().year, 1, 1, 00, 00)
        startPayload = self.makeFOCTimeLengthPayload(start)
        endPayload = self.makeFOCTimeLengthPayload(end)

#        self.addressParameters[deviceID].update({"opChangeStartTime": start, "opChangeEndTime": end})
        #        logging.debug(start, end)
        #        logging.debug("startend %s %s",hex(startPayload),hex(endPayload))
        # zmena 24.12.2023 nahrazen opChangePresetTemp za opChangeTemp
        temperature = self.addressParameters[deviceID]["opChangeTemp"]
        #        logging.debug(hex(temperature))
        type = self.addressParameters[deviceID]["opChangePresetType"]
        #        logging.debug(type)
        ftcByte = temperature
        if type == self.FOC_TYPE_HOLD:
            ftcByte = ftcByte | 0x20

        attribAddr = BASEADDR + (deviceID - 1) * addrIncrement + fastChangeModeOffset
        reqAddrB0 = (attribAddr & 0xff00) >> 8
        reqAddrB1 = attribAddr & 0x00ff
        #        logging.debug(hex(reqAddrB0),hex(reqAddrB1))
        #        logging.debug(endPayload)
        #        logging.debug(hex(endPayload & 0xff00))
        #        logging.debug(hex(startPayload & 0x00ff))
        #        logging.debug(hex((startPayload & 0xff00)>>8))
        #        logging.debug(hex(endPayload & 0x00ff))
        #        logging.debug(hex((endPayload & 0xff00)>>8))
        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                reqResponseLen | reqOpCode) + ftcByte + ((startPayload & 0xff00) >> 8) + (startPayload & 0x00ff) + (
                           (endPayload & 0xff00) >> 8) + (endPayload & 0x00ff)) & 0xff
        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                reqResponseLen | reqOpCode) ^ ftcByte ^ ((startPayload & 0xff00) >> 8) ^ (startPayload & 0x00ff) ^ (
                           (endPayload & 0xff00) >> 8) ^ (endPayload & 0x00ff)) & 0xff

        reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                              (reqResponseLen | reqOpCode), ftcByte, (startPayload & 0xff00) >> 8,
                              startPayload & 0x00ff, (endPayload & 0xff00) >> 8, (endPayload & 0x00ff), reqAdds,
                              reqXors, self.reqTrailer, self.reqTrailer])

        #        logging.debug(reqFrame.hex())
        self.etathermSessionOpen()
        try:
            respFrame = self.etathermSendFrame(reqFrame)
        except etathermSendReceiveError:
            logging.debug("Error deactivating FOC")
            self.etathermSessionClose()
            return 1
        else:
            logging.debug("FOC deactivated")
            self.etathermSessionClose()
            return 0

    # activates preset GOC = reads GOC parameters from the struct, calculates start/end time and temperature
    # and sends it to all devices; GOC activation is just setting of start and end time or hold mode (with start/end 1/1/year) and temperature
    # if activation fails for some deviceID, it calls deactivateGOC()
    # input variables   none
    # returns 1 or 0 according to the operation result
    def activateGOC(self):

        length = 0
        temperature = 0
        payload = []
        reqOpCode = 0x0c
        reqResponseLen = 0x40
        BASEADDR = 0x1100
        addrIncrement = 0x10
        fastChangeModeOffset = 0x03
        ftcByte = 0

        logging.debug("activateGOC called")
        self.etathermSessionOpen()
        for deviceID in range(1, 17):
            if self.addressParameters[deviceID]["globalOpChangePresetType"] != self.FOC_TYPE_OFF:
                length = self.addressParameters[deviceID]["globalOpChangePresetLength"] * 15
                if self.addressParameters[deviceID]["globalOpChangePresetType"] == self.FOC_TYPE_HOLD:
                    start = datetime.datetime(datetime.date.today().year,1,1, 00, 00)
                    end = datetime.datetime(datetime.date.today().year,1,1, 00, 00)
                else:
                    start = datetime.datetime.now()
                    end = start + datetime.timedelta(minutes=length)

                startPayload = self.makeFOCTimeLengthPayload(start)
                endPayload = self.makeFOCTimeLengthPayload(end)
                s = start.strftime("%Y-%m-%d %H:%M:%S")
                e = end.strftime("%Y-%m-%d %H:%M:%S")
                temperature = self.addressParameters[deviceID]["globalOpChangePresetTemp"]

                logging.debug("Activating GOC temperature for device %d %d", deviceID,
                    self.addressParameters[deviceID]["globalOpChangePresetTemp"] + self.addressParameters[deviceID]["tempOffset"])
                type = self.addressParameters[deviceID]["globalOpChangePresetType"]
                logging.debug("%s", type)
                ftcByte = self.addressParameters[deviceID]["globalOpChangePresetTemp"]
                if type == self.FOC_TYPE_HOLD:
                    ftcByte = ftcByte | 0x20
                if end.year > start.year:
                    ftcByte = ftcByte | 0x40
                    logging.debug("end next year")
                    logging.debug(hex(ftcByte))

                attribAddr = BASEADDR + (deviceID - 1) * addrIncrement + fastChangeModeOffset
                reqAddrB0 = (attribAddr & 0xff00) >> 8
                reqAddrB1 = attribAddr & 0x00ff
        #        logging.debug(hex(reqAddrB0),hex(reqAddrB1))
        #        logging.debug(endPayload)
        #        logging.debug(hex(endPayload & 0xff00))
        #        logging.debug(hex(startPayload & 0x00ff))
        #        logging.debug(hex((startPayload & 0xff00)>>8))
        #        logging.debug(hex(endPayload & 0x00ff))
        #        logging.debug(hex((endPayload & 0xff00)>>8))
                reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                    reqResponseLen | reqOpCode) + ftcByte + ((startPayload & 0xff00) >> 8) + (startPayload & 0x00ff) + (
                           (endPayload & 0xff00) >> 8) + (endPayload & 0x00ff)) & 0xff
                reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                    reqResponseLen | reqOpCode) ^ ftcByte ^ ((startPayload & 0xff00) >> 8) ^ (startPayload & 0x00ff) ^ (
                           (endPayload & 0xff00) >> 8) ^ (endPayload & 0x00ff)) & 0xff

                reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                              (reqResponseLen | reqOpCode), ftcByte, (startPayload & 0xff00) >> 8,
                              startPayload & 0x00ff, (endPayload & 0xff00) >> 8, (endPayload & 0x00ff), reqAdds,
                              reqXors, self.reqTrailer, self.reqTrailer])

        #        logging.debug("ramec %s",reqFrame.hex())

                try:
                    respFrame = self.etathermSendFrame(reqFrame)
                except etathermSendReceiveError:
                    logging.debug("Error activating GOC for device %i", deviceID)
                    self.etathermSessionClose()
                    self.deactivateGOC()
                    return 1
                else:
#                    if self.addressParameters[deviceID]["globalOpChangePresetType"] == self.FOC_TYPE_HOLD:
#                        self.addressParameters[deviceID]["opChangeHoldActive"] = 1

#                    self.addressParameters[deviceID]["opChangeTemp"] = temperature
#                    self.addressParameters[deviceID].update({"opChangeStartTime": s, "opChangeEndTime": e})
                    logging.debug("GOC for device %i activated", deviceID)

        self.etathermSessionClose()
        return 0

    # deactivates GOC = changes start/end to 1/1/year, sets opChangeHoldActive bit to 0 and start/end next year to 0 (setting just temperature and other bits to 0
    # and sends config to all devices
    # input variables   none
    # returns 1 or 0 according to the operation result
    def deactivateGOC(self):
        length = 0
        temperature = 0
        payload = []
        reqOpCode = 0x0c
        reqResponseLen = 0x40
        BASEADDR = 0x1100
        addrIncrement = 0x10
        fastChangeModeOffset = 0x03
        ftcByte = 0
        logging.debug("deactivateGOC called")
        self.etathermSessionOpen()
        for deviceID in range (1, 17):
            if self.addressParameters[deviceID]["globalOpChangePresetType"] != self.FOC_TYPE_OFF:
                start = datetime.datetime(datetime.date.today().year, 1, 1, 00, 00)
                end = datetime.datetime(datetime.date.today().year, 1, 1, 00, 00)
                startPayload = self.makeFOCTimeLengthPayload(start)
                endPayload = self.makeFOCTimeLengthPayload(end)

                temperature = self.addressParameters[deviceID]["globalOpChangePresetTemp"]
#            type = self.addressParameters[deviceID]["globalOpChangePresetType"]
        #        logging.debug(type)
                ftcByte = temperature
                attribAddr = BASEADDR + (deviceID - 1) * addrIncrement + fastChangeModeOffset
                reqAddrB0 = (attribAddr & 0xff00) >> 8
                reqAddrB1 = attribAddr & 0x00ff
                reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                    reqResponseLen | reqOpCode) + ftcByte + ((startPayload & 0xff00) >> 8) + (startPayload & 0x00ff) + (
                           (endPayload & 0xff00) >> 8) + (endPayload & 0x00ff)) & 0xff
                reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                    reqResponseLen | reqOpCode) ^ ftcByte ^ ((startPayload & 0xff00) >> 8) ^ (startPayload & 0x00ff) ^ (
                           (endPayload & 0xff00) >> 8) ^ (endPayload & 0x00ff)) & 0xff

                reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                              (reqResponseLen | reqOpCode), ftcByte, (startPayload & 0xff00) >> 8,
                              startPayload & 0x00ff, (endPayload & 0xff00) >> 8, (endPayload & 0x00ff), reqAdds,
                              reqXors, self.reqTrailer, self.reqTrailer])

                try:
                    respFrame = self.etathermSendFrame(reqFrame)
                except etathermSendReceiveError:
                    logging.debug("Error deactivating GOC for device %i", deviceID)
                    self.etathermSessionClose()
                    return 1
                else:
                    logging.debug("GOC deactivated for device %i", deviceID)
#                    if self.addressParameters[deviceID]["globalOpChangePresetType"] == self.FOC_TYPE_HOLD:
#                        self.addressParameters[deviceID]["opChangeHoldActive"] = 0
#                    self.addressParameters[deviceID].update({"opChangeStartTime": start, "opChangeEndTime": end})

        self.etathermSessionClose()
        return 0




    # initializes address parameters dictionary in the class constructor
    # retrieves these addresses
    #
    # input variables none
    # returns address parameters dictionary indexed by device ID
    @property
    def initAddressParameters_(self):

        names = {}
        ftc = {}
        addr = {}
        gtc = {}
        #        addressParameters = {}
        invalidResponse = 0
        addressParams = {}

        logging.debug("Called retrieveAddressNames")
        names = self.retrieveAddressNames()
        logging.debug("Calling retrieveFOCParameters")
        ftc = self.retrieveFOCParameters()
        logging.debug("Calling retrieveGOCParameters")
        gtc = self.retrieveGOCParameters()
        logging.debug("Calling retrieveAddressParameters")
        addr = self.retrieveAddressParameters()

        for j in range(1, 17):
            if (((ftc[j][0]) & 0x60) >> 5) == 2:
                fastOpChangeType = self.FOC_TYPE_OPCHANGE
            if (((ftc[j][0]) & 0x60) >> 5) == 1:
                fastOpChangeType = self.FOC_TYPE_HOLD
            if (((ftc[j][0]) & 0x60) >> 5) == 0:
                fastOpChangeType = self.FOC_TYPE_OFF
            if (((gtc[j]) & 0x60) >> 5) == 2:
                globalOpChangeType = self.FOC_TYPE_OPCHANGE
            if (((gtc[j]) & 0x60) >> 5) == 1:
                globalOpChangeType = self.FOC_TYPE_HOLD
            if (((gtc[j]) & 0x60) >> 5) == 0:
                globalOpChangeType = self.FOC_TYPE_OFF
            #            logging.debug(j, fastTempChangeType, globalTempChangeType)
            startTime = self.convertFOCBytesToTime(
                (addr[j]["opChangeStartByteHigh"] << 8) | (addr[j]["opChangeStartByteLow"]),
                addr[j]["opChangeStartNextYear"])
            endTime = self.convertFOCBytesToTime(
                (addr[j]["opChangeEndByteHigh"] << 8) | (addr[j]["opChangeEndByteLow"]), addr[j]["opChangeEndNextYear"])
            logging.debug(startTime, endTime)
            addressParams = {
                #                   "deviceTypeAll": (respFrame[5])
                #                    "deviceBUSId": j,
                # Address name / 0x1030 - 0x10AF
                "deviceName": names[j],
                # Addresses parameters
                # Type of device / 0x1100 - 0x11FF, byte 0x00, bits 0-2
                "deviceType": addr[j]["deviceType"],
                # Type of time service (0=12.288s, 1=0.384s) / 0x1100 - 0x11FF, byte 0x00, bit 3
                "serviceTime": addr[j]["serviceTime"],
                # Controls switch 1 / 0x1100 - 0x11FF, byte 0x00, bit 4
                "controlsSwitch1": addr[j]["controlsSwitch1"],
                # Controls switch 2 / 0x1100 - 0x11FF, byte 0x00, bit 5
                "controlsSwitch2": addr[j]["controlsSwitch2"],
                # Address password / 0x1100 - 0x11FF, byte 0x01
                "devicePass": addr[j]["devicePass"],
                # Temperature offset / 0x1100 - 0x11FF, byte 0x02
                "tempOffset": addr[j]["tempOffset"],
                # Temperature and FOC parameters, actual settings
                # Temperatures w/o temperature offset
                # FOC parameters / 0x1100 - 0x11FF, byte 0x03
                "opChangeAll": addr[j]["opChangeAll"],
                # FOC temperature w/o offset / 0x1100 - 0x11FF, byte 0x03, bits 0-4
                "opChangeTemp": addr[j]["opChangeTemp"],
                # "Aktivni udrzovaci rezim" / 0x1100 - 0x11FF, byte 0x03, bit 5
                "opChangeHoldActive": addr[j]["opChangeHoldActive"],
                # FOC change ends next year / 0x1100 - 0x11FF, byte 0x03, bit 6
                "opChangeEndNextYear": addr[j]["opChangeEndNextYear"],
                # FOC starts next year / 0x1100 - 0x11FF, byte 0x03, bit 7
                "opChangeStartNextYear": addr[j]["opChangeStartNextYear"],
                # FOC start time byte high / 0x1100 - 0x11FF, byte 0x04
                "opChangeStartByteHigh": addr[j]["opChangeStartByteHigh"],
                # FOC start time byte low / 0x1100 - 0x11FF, byte 0x05
                "opChangeStartByteLow": addr[j]["opChangeStartByteLow"],
                # FOC end time byte high / 0x1100 - 0x11FF, byte 0x06
                "opChangeEndByteHigh": addr[j]["opChangeEndByteHigh"],
                # FOC end time byte low / 0x1100 - 0x11FF, byte 0x07
                "opChangeEndByteLow": addr[j]["opChangeEndByteLow"],
                # FOC start time computed from byte 0x04+0x05
                "opChangeStartTime": startTime,
                # FOC end time computed from byte 0x06+0x07
                "opChangeEndTime": endTime,
                # ??
                "opChangeByte1": ftc[j][0],
                # ??
                "opChangeByte2": ftc[j][1],
                # ??
                "opChangeByte3": ftc[j][2],
                # ??
                "opChangeByte4": ftc[j][3],
                # FOC preset registry, not actual settings (0x10B0)
                # FOC preset temperature w/o offset / 0x10B0 - 0x10EF, bits 0-4
                "opChangePresetTemp": ((ftc[j][0]) & 0x1f),
                # FOC preset type / 0x10B0 - 0x10EF, bits 5-6
                "opChangePresetType": fastOpChangeType,
                # FOC time in 15 minutes computer from bytes 0x01 and 0x02
                "opChangePresetLength": ftc[j][1] * 256 + ftc[j][2],
                # FOC preset length in 15 minutes high byte / 0x10B0 - 0x10EF, byte 0x01
                "opChangePresetLengthHighByte": ftc[j][1],
                # FOC preset length in 15 minutes low byte / 0x10B0 - 0x10EF, byte 0x02
                "opChangePresetLengthLowByte": ftc[j][2],
                # GOC preset registry 0x10F0 - 0x10FF, each byte for one address
                # GOC preset registry / 0x10F0 - 0x10FF, byte device_id
                "globalOpChangePresetAll": gtc[j],
                # GOC preset registry temperature w/o offset / 0x10F0 - 0x10FF, byte device_id, bits 0-4
                "globalOpChangePresetTemp": (gtc[j] & 0x1f),
                # GOC preset registry type / 0x10F0 - 0x10FF, byte device_id, bits 5-6
                "globalOpChangePresetType": globalOpChangeType,
                # GOC preset registry length in 15 minutes, each bit 7 of device_id byte forms part of the 16bits number / 0x10F0 - 0x10FF, byte device_id, bit 7
                "globalOpChangePresetLength": gtc["GTCLength"],
                self.dayCodes[1]: addr[j][self.dayCodes[1]],
                self.dayCodes[2]: addr[j][self.dayCodes[2]],
                self.dayCodes[3]: addr[j][self.dayCodes[3]],
                self.dayCodes[4]: addr[j][self.dayCodes[4]],
                self.dayCodes[5]: addr[j][self.dayCodes[5]],
                self.dayCodes[6]: addr[j][self.dayCodes[6]],
                self.dayCodes[7]: addr[j][self.dayCodes[7]],
                self.dayCodes[8]: addr[j][self.dayCodes[8]],
                # Real temperature w/o offset - 0x0060 - 0x006F
                "realTemp": 0,
                # Target active temperature w/o offset - 0x0070 - 0x007F, bits 0-4
                "targetTemp": 0
            }
            self.addressParameters.update({j: addressParams})

    #        if (invalidResponse == 1):

    #            s.close()
    #            return 0
    #        else:
    #        logging.debug("%s", self.addressParameters)
    #        return addressParameters

    # converts time bytes into datetime
    # input variables   timeBytes: int bytes retrieved from device
    #                   nextYear: 1 - date is next year, 0 - date is current year
    # returns datetime time
    def convertFOCBytesToTimeString(self, timeBytes, nextYear):

        t = datetime.datetime.now()
        if (nextYear == 1):
            x = t.year + 1
        else:
            x = t.year
        t = t.replace(year=(x), month=((timeBytes >> 12) & 0xf), day=((timeBytes >> 7) & 0x1f),
                      hour=((timeBytes >> 2) & 0x1f), minute=((timeBytes & 0x3) * 15), second=0)
        t = datetime.datetime.strftime(t, "%Y-%m-%d %H:%M:%S")
        #        logging.debug ("%d", t)
        return t

    # synchronizes addressParameters struct
    # input variables
    #
    # returns ??
    #  def retrieveAddressParameters(self):

    #       return 1

    # sets FOC temperature into addressParameters struct for deviceID
    # input variables   deviceID: int
    #                   temperature: int temperature w/ offset
    # returns ??
    def setFOCTemperature(self, deviceID, temperature):

        logging.debug("setFOCTemperature called")

        #        logging.debug ("%d %d %d", deviceID, self.addressParameters[deviceID]["tempOffset"], temperature)
        self.addressParameters[deviceID]["opChangeTemp"] = int(temperature) - self.addressParameters[deviceID]["tempOffset"]
        #        self.addressParameters[deviceID]["targetTemp"] = temperature - self.addressParameters[deviceID]["tempOffset"]
        #        self.addressParameters[deviceID]["opChangeTemp"] = (addressParameters[deviceID]["opChangeTemp"] & 0xe0) | (temperature-self.addressParameters[deviceID]["tempOffset"])
        self.enqueueCmd({"cmd": self.CMD_STORE_FOC_TEMPERATURE, "deviceID": deviceID})
        return 1

    # returns FOC temperature from addressParameters struct for deviceID
    # input variables   deviceID: int
    # returns temperature w/ offset
    #    def getFOCTemperature(self, deviceID):

    #       return self.addressParameters[deviceID][]

    # opens etatherm session and stores session handle
    # input variables   none
    # returns none
    def etathermSessionOpen(self):

        for i in range(0, self.tries):
            try:
                self.etathermSession = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.etathermSession.settimeout(self.receiveTimeout)
                self.etathermSession.connect((self.etathermHostname, self.etathermPort))
            except socket.timeout as err:
                logging.error("Socket timeout on sessionOpen, sleeping for %d seconds", self.commSleep)
                time.sleep(self.commSleep)
                continue
            except socket.error as err:
                logging.error("Socket error on sessionOpen, sleeping for %d seconds", self.commSleep)
                time.sleep(self.commSleep)
                continue
            else:
                return 0
        raise etathermOpenSessionError



    # closes persistent etatherm session and frees session handle
    # input variables   none
    # returns none
    def etathermSessionClose(self):

        self.etathermSession.close()

    #        return self.addressParameters[deviceID][]

    #   def getAddressOperationalMode(self, deviceID):

    #        if (self.addressParameters[deviceID][]):

    # stores FOC temperature into control unit for deviceID
    # input variables   deviceID: int
    # returns ??
    def storeFOCTemperature(self, deviceID):

        reqOpCode = 0x0c
        reqResponseLen = 0x00
        BASEADDR = 0x1100
        addrIncrement = 0x10
        fastChangeModeOffset = 0x03

        logging.debug("storeFOCTemperature called")
        attribAddr = BASEADDR + (deviceID - 1) * addrIncrement + fastChangeModeOffset
        reqAddrB0 = (attribAddr & 0xff00) >> 8
        reqAddrB1 = attribAddr & 0x00ff

        logging.debug("Storing opChangeTemp %s for device %d", self.addressParameters[deviceID]["opChangeTemp"], deviceID)
        ftcByte = self.makeFOCTemperatureByte(deviceID)

        reqAdds = (self.reqDle + self.reqSoh + self.reqAddrBusH + self.reqAddrBusL + reqAddrB0 + reqAddrB1 + (
                reqResponseLen | reqOpCode) + ftcByte) & 0xff
        reqXors = (self.reqDle ^ self.reqSoh ^ self.reqAddrBusH ^ self.reqAddrBusL ^ reqAddrB0 ^ reqAddrB1 ^ (
                reqResponseLen | reqOpCode) ^ ftcByte) & 0xff

        reqFrame = bytearray([self.reqDle, self.reqSoh, self.reqAddrBusH, self.reqAddrBusL, reqAddrB0, reqAddrB1,
                              (reqResponseLen | reqOpCode), ftcByte, reqAdds,
                              reqXors, self.reqTrailer, self.reqTrailer])

        #        logging.debug("ramec %s",reqFrame.hex())
        self.etathermSessionOpen()
        try:
            respFrame = self.etathermSendFrame(reqFrame)
        except etathermSendReceiveError:
            self.etathermSessionClose()
            return 1
        else:
            self.etathermSessionClose()
            return 1

    # computes FOC temperature byte (0x1100, byte 0x03)
    # input variables   deviceID: int
    # returns FOC byte 0x1100, byte 0x03
    def makeFOCTemperatureByte(self, deviceID):

        focByte = (self.addressParameters[deviceID]["opChangeTemp"] & 0x1f) | (
                    self.addressParameters[deviceID]["opChangeHoldActive"] << 5)
        focByte = focByte | (self.addressParameters[deviceID]["opChangeEndNextYear"] << 6) | (
                    self.addressParameters[deviceID]["opChangeStartNextYear"] << 7)
        return focByte

    # processes cmdQueue if not empty
    # input variables   none
    # returns ???
    def processCmdQueue(self):

        cmd = {}
        if not self.cmdQueue.empty():
            logging.debug("Queue not empty, processing started")
            cmd = self.cmdQueue.get()
            logging.debug(cmd)
            if cmd["cmd"] == self.CMD_STORE_FOC_TEMPERATURE:
                logging.debug("Q:Storing FOC temperature for device %d", cmd["deviceID"])
                self.storeFOCTemperature(cmd["deviceID"])
            if cmd["cmd"] == self.CMD_FOC_ACTIVATE:
                logging.debug("Q:Activating FOC for device %d", cmd["deviceID"])
                self.activateFOC(cmd["deviceID"])
            if cmd["cmd"] == self.CMD_FOC_DEACTIVATE:
                logging.debug("Q:Deactivating FOC for device %d", cmd["deviceID"])
                self.deactivateFOC(cmd["deviceID"])
            if cmd["cmd"] == self.CMD_UPDATE_MQTT:
                logging.debug("Q:Sending MQTT update for all devices")
                self.mqttUpdate()
            if cmd["cmd"] == self.CMD_RETRIEVE_ADDR_PARAM:
                logging.debug("Q:Updating addressparameters struct")
                self.updateAddressParameters()
            if cmd["cmd"] == self.CMD_ACTIVATE_HEATING_MAP:
                logging.debug("Q:Storing activated heating map %d", cmd["heatingMapID"])
                self.storeActivatedHeatingMap(cmd["heatingMapID"])
                self.enqueuePeriodicAddressParametersUpdate()
                self.enqueueActiveHeatingMapMqttUpdate()
            if cmd["cmd"] == self.CMD_UPDATE_MQTT_ACTIVE_HEATING_MAP:
                logging.debug("Q:Updating active heating map in mqtt")
                self.mqttUpdateActiveHeatingMap()
            if cmd["cmd"] == self.CMD_GOC_ACTIVATE:
                logging.debug("Q:Activating Global Operation Change")
                self.activateGOC()
                self.enqueuePeriodicAddressParametersUpdate()
            if cmd["cmd"] == self.CMD_GOC_DEACTIVATE:
                logging.debug("Q:Deactivating Global Operation Change")
                self.deactivateGOC()
                self.enqueuePeriodicAddressParametersUpdate()

        return

    # enqueues item into cmdQueue
    # input variables   cmd: library {"cmd": etherm.CMD_FOC_ACTIVATE,"deviceID": deviceID}
    # returns ???
    def enqueueCmd(self, cmd):

        self.cmdQueue.put(cmd)
        logging.debug("Enqueued command %s", cmd)

        return

    # parses and sets address names to the struct addressParameters
    # input variables   names: dictionary
    # returns ???
    def setAddressNames(self, names):

#        names = {}
        logging.debug("setAddressNames called")
        if (names):
            logging.debug("Names not empty, updating dictionary %s", names)
            for j in range(1, 17):
            # Address name / 0x1030 - 0x10AF
                self.addressParameters.update({j: {"deviceName": names[j]}})

        #        logging.debug("%s", self.addressParameters)
            return 0
        else:
            logging.debug("Names empty, dictionary not updated")
            return 1

    # parses and sets FOC parameters to the struct addressParameters
    # input variables   foc: dictionary
    # returns ???
    def setFOCPresetParameters(self, foc):
        logging.debug("setFOCPresetParameters called")
        if (foc):
            logging.debug("focPreset not empty, updating dictionary %s", foc)
            for j in range(1, 17):
                if (((foc[j][0]) & 0x60) >> 5) == 2:
                    fastOpChangeType = self.FOC_TYPE_OPCHANGE
                if (((foc[j][0]) & 0x60) >> 5) == 1:
                    fastOpChangeType = self.FOC_TYPE_HOLD
                if (((foc[j][0]) & 0x60) >> 5) == 0:
                    fastOpChangeType = self.FOC_TYPE_OFF

                self.addressParameters[j].update({"opChangeByte1": foc[j][0],
                                              "opChangeByte2": foc[j][1],
                                              "opChangeByte3": foc[j][2],
                                              "opChangeByte4": foc[j][3],
                                              # FOC preset registry, not actual settings (0x10B0)
                                              # FOC preset temperature w/o offset / 0x10B0 - 0x10EF, bits 0-4
                                              "opChangePresetTemp": ((foc[j][0]) & 0x1f),
                                              # FOC preset type / 0x10B0 - 0x10EF, bits 5-6
                                              "opChangePresetType": fastOpChangeType,
                                              # FOC time in 15 minutes computer from bytes 0x01 and 0x02
                                              "opChangePresetLength": foc[j][1] * 256 + foc[j][2],
                                              # FOC preset length in 15 minutes high byte / 0x10B0 - 0x10EF, byte 0x01
                                              "opChangePresetLengthHighByte": foc[j][1],
                                              # FOC preset length in 15 minutes low byte / 0x10B0 - 0x10EF, byte 0x02
                                              "opChangePresetLengthLowByte": foc[j][2]})
        #        logging.debug("%s", self.addressParameters)
        else:
            logging.debug("foc preset empty, dictionary not updated")
        return

    # parses and sets GOC parameters to the struct addressParameters
    # input variables   goc: dictionary
    # returns ???
    def setGOCPresetParameters(self, goc):

        logging.debug("setGOCPresetParameters called")

        if (goc):
            logging.debug("goc not empty, updating dictionary %s", goc)
            for j in range(1, 17):
                if (((goc[j]) & 0x60) >> 5) == 2:
                    globalOpChangeType = self.FOC_TYPE_OPCHANGE
                if (((goc[j]) & 0x60) >> 5) == 1:
                    globalOpChangeType = self.FOC_TYPE_HOLD
                if (((goc[j]) & 0x60) >> 5) == 0:
                    globalOpChangeType = self.FOC_TYPE_OFF
            # GOC preset registry 0x10F0 - 0x10FF, each byte for one address
            # GOC preset registry / 0x10F0 - 0x10FF, byte device_id
                self.addressParameters[j].update({"globalOpChangePresetAll": goc[j],
                                              # GOC preset registry temperature w/o offset / 0x10F0 - 0x10FF, byte device_id, bits 0-4
                                              "globalOpChangePresetTemp": (goc[j] & 0x1f),
                                              # GOC preset registry type / 0x10F0 - 0x10FF, byte device_id, bits 5-6
                                              "globalOpChangePresetType": globalOpChangeType,
                                              # GOC preset registry length in 15 minutes, each bit 7 of device_id byte forms part of the 16bits number / 0x10F0 - 0x10FF, byte device_id, bit 7
                                              "globalOpChangePresetLength": goc["GTCLength"]})
        #        logging.debug("%s", self.addressParameters)
        else:
            logging.debug("goc empty, dictionary not updated")
        return

    # parses and sets address parameters to the struct addressParameters
    # input variables   addr: dictionary
    # returns ???
    def setAddressParameters(self, addr):

        logging.debug("setAddressParameters called")
        if (addr):
            logging.debug("addressParameters not empty, updating dictionary %s", addr)
            for j in range(1, 17):
                startTime = self.convertFOCBytesToTimeString(
                    (addr[j]["opChangeStartByteHigh"] << 8) | (addr[j]["opChangeStartByteLow"]),
                    addr[j]["opChangeStartNextYear"])
                endTime = self.convertFOCBytesToTimeString(
                    (addr[j]["opChangeEndByteHigh"] << 8) | (addr[j]["opChangeEndByteLow"]), addr[j]["opChangeEndNextYear"])
            #            logging.debug(startTime, endTime)
                self.addressParameters[j].update({
                #                   "deviceTypeAll": (respFrame[5])
                #                    "deviceBUSId": j,
                # Addresses parameters
                # Type of device / 0x1100 - 0x11FF, byte 0x00, bits 0-2
                    "deviceType": addr[j]["deviceType"],
                # Type of time service (0=12.288s, 1=0.384s) / 0x1100 - 0x11FF, byte 0x00, bit 3
                    "serviceTime": addr[j]["serviceTime"],
                # Controls switch 1 / 0x1100 - 0x11FF, byte 0x00, bit 4
                    "controlsSwitch1": addr[j]["controlsSwitch1"],
                # Controls switch 2 / 0x1100 - 0x11FF, byte 0x00, bit 5
                    "controlsSwitch2": addr[j]["controlsSwitch2"],
                # Address password / 0x1100 - 0x11FF, byte 0x01
                    "devicePass": addr[j]["devicePass"],
                # Temperature offset / 0x1100 - 0x11FF, byte 0x02
                    "tempOffset": addr[j]["tempOffset"],
                # Temperature and FOC parameters, actual settings
                # Temperatures w/o temperature offset
                # FOC parameters / 0x1100 - 0x11FF, byte 0x03
                    "opChangeAll": addr[j]["opChangeAll"],
                # FOC temperature w/o offset / 0x1100 - 0x11FF, byte 0x03, bits 0-4
                    "opChangeTemp": addr[j]["opChangeTemp"],
                # "Aktivni udrzovaci rezim" / 0x1100 - 0x11FF, byte 0x03, bit 5
                    "opChangeHoldActive": addr[j]["opChangeHoldActive"],
                # FOC change ends next year / 0x1100 - 0x11FF, byte 0x03, bit 6
                    "opChangeEndNextYear": addr[j]["opChangeEndNextYear"],
                # FOC starts next year / 0x1100 - 0x11FF, byte 0x03, bit 7
                    "opChangeStartNextYear": addr[j]["opChangeStartNextYear"],
                # FOC start time byte high / 0x1100 - 0x11FF, byte 0x04
                    "opChangeStartByteHigh": addr[j]["opChangeStartByteHigh"],
                # FOC start time byte low / 0x1100 - 0x11FF, byte 0x05
                    "opChangeStartByteLow": addr[j]["opChangeStartByteLow"],
                # FOC end time byte high / 0x1100 - 0x11FF, byte 0x06
                    "opChangeEndByteHigh": addr[j]["opChangeEndByteHigh"],
                # FOC end time byte low / 0x1100 - 0x11FF, byte 0x07
                    "opChangeEndByteLow": addr[j]["opChangeEndByteLow"],
                # FOC start time computed from byte 0x04+0x05
                    "opChangeStartTime": startTime,
                # FOC end time computed from byte 0x06+0x07
                    "opChangeEndTime": endTime,
                # Program number is addressed from 0, reported from 1
                    "activeHeatingMap" : addr[j]["activeHeatingMap"]
                    })
        #        logging.debug(self.addressParameters)
            return 0
        else:
            logging.debug("addressParameters empty, dictionary not updated")
            return 1

    # parses and sets real address temperatures to the struct addressParameters
    # input variables   realTemp dictionary {deviceID: realTemp}
    # returns none

    def setAddressRealTemperature(self, realTemp):

        logging.debug("setAddressRealTemperature called")
        if (realTemp):
            logging.debug("realTemp not empty, updating dictionary %s", realTemp)
            for j in range(1, 17):
            # Real temperature w/o offset - 0x0060 - 0x006F
                self.addressParameters[j].update({"realTemp": realTemp[j]})
            return 0
        else:
            logging.debug("realTemp empty, dictionary not updated")
            return 1

    # parses and sets target address temperatures to the struct addressParameters
    # input variables   targetTemp dictionary {deviceID: targetTemp}
    # returns none

    def setAddressTargetTemperature(self, targetTemp):

        logging.debug("setAddressTargetTemperature called")
        # Target active temperature w/o offset - 0x0070 - 0x007F, bits 0-4
        if (targetTemp):
            logging.debug("targetTemp not empty, updating dictionary %s", targetTemp)
            for j in range(1, 17):
                self.addressParameters[j].update({"targetTemp": targetTemp[j]})
            return 0
        else:
            logging.debug("targetTemp empty, dictionary not updated")
            return 1

    def initAddressParameters(self):

        initErr = 0
        logging.debug("initAddressParameters called")
        for i in range (0, self.initTries):
            self.addressParameters = {}
            for j in range(1, 17):
                self.addressParameters.update({j: {}})

            self.etathermSessionOpen()
            initErr = initErr or self.setAddressNames(self.retrieveAddressNames())
            initErr = initErr or self.setFOCPresetParameters(self.retrieveFOCParameters())
            initErr = initErr or self.setGOCPresetParameters(self.retrieveGOCParameters())
            initErr = initErr or self.setAddressParameters(self.retrieveAddressParameters())
            initErr = initErr or self.setAddressRealTemperature(self.retrieveRealTemperature())
            initErr = initErr or self.setAddressTargetTemperature(self.retrieveTargetTemperature)
            if not(initErr):
                logging.debug("Initialization complete %d", initErr)
                self.etathermSessionClose()
                break
            else:
                logging.error("Initialization error")
                logging.debug("Sleeping for %d seconds", self.initTimeout)
                time.sleep(self.initTimeout)
                initErr = 0
            self.etathermSessionClose()


        if (i==self.initTries-1):
            self.addressParameters = {}
            logging.debug("initAddressParameters finished, dictionary not initialized")
            return 1
        else:
            logging.debug("initAddressParameters finished, dictionary initialized")
            return 0

    # initializes MQTT variables
    # input variables   brokerHostname string
    #                   brokerPort integer
    #                   username string
    #                   password string
    # returns none

    def initMqtt(self, brokerHostname, brokerPort, username, password):

        logging.debug("initMqtt called")
        self.mqttBrokerHostname = brokerHostname
        self.mqttBrokerPort = brokerPort
        if (username != "" and password != ""):
            self.mqttAuth = {"username": username, "password": password}
        else:
            self.mqttAuth = {}
        #        self.mqttSession = mqtt.Client(protocol=mqtt.MQTTv311, transport="tcp")
        #        mqttc.connect(host=MQTTBROKERHOST, port=MQTTBROKERPORT)
        self.MQTT_TOPIC_ETATHERM_PREFIX = "etatherm"
        self.MQTT_TOPIC_TARGET_TEMPERATURE = "temperature/target"
        self.MQTT_TOPIC_REAL_TEMPERATURE = "temperature/real"
        self.MQTT_TOPIC_SET_PREFIX = "set"
        self.MQTT_TOPIC_MODE_PREFIX = "mode"
        self.MQTT_TOPIC_NAME_PREFIX = "name"
        self.MQTT_TOPIC_DEVICETYPE_PREFIX ="devicetype"
        self.MQTT_TOPIC_SERVICETIME_PREFIX = "servicetime"
        self.MQTT_TOPIC_CONTROLSSWITCH1_PREFIX = "controlsswitch1"
        self.MQTT_TOPIC_CONTROLSSWITCH2_PREFIX = "controlsswitch2"
        self.MQTT_TOPIC_DEVICEPASS_PREFIX = "devicepass"
        self.MQTT_TOPIC_TEMPOFFSET_PREFIX = "tempoffset"
        self.MQTT_TOPIC_OPCHANGETEMP_PREFIX = "opchangetemp"
        self.MQTT_TOPIC_OPCHANGEHOLDACTIVE_PREFIX = "opchangeholdactive"
        self.MQTT_TOPIC_OPCHANGEENDNEXTYEAR_PREFIX = "opchangeendnextyear"
        self.MQTT_TOPIC_OPCHANGESTARTNEXTYEAR_PREFIX = "opchangestartnextyear"
        self.MQTT_TOPIC_OPCHANGESTARTTIME_PREFIX = "opchangestarttime"
        self.MQTT_TOPIC_OPCHANGEENDTIME_PREFIX = "opchangeendtime"
        self.MQTT_TOPIC_OPCHANGEPRESETTEMP_PREFIX = "opchangepresettemp"
        self.MQTT_TOPIC_OPCHANGEPRESETTYPE_PREFIX = "opchangepresettype"
        self.MQTT_TOPIC_OPCHANGEPRESETLENGTH_PREFIX = "opchangepresetlength"
        self.MQTT_TOPIC_GLOBALOPCHANGEPRESETTEMP_PREFIX = "globalopchangepresettemp"
        self.MQTT_TOPIC_GLOBALOPCHANGEPRESETTYPE_PREFIX = "globalopchangepresettype"
        self.MQTT_TOPIC_GLOBALOPCHANGEPRESETLENGTH_PREFIX = "globalopchangepresetlength"
        self.MQTT_TOPIC_SYSTEM_PREFIX = "system"
        self.MQTT_TOPIC_ACTIVEHEATINGMAP_PREFIX = "activeheatingmap"
        self.MQTT_TOPIC_HEATINGMAPS_PREFIX = "heatingmaps"
        self.MQTT_HEATINGMAPSNAME_PREFIX = "name"
        self.MQTT_HEATINGMAPSTYPE_PREFIX = "type"
        self.MQTT_HEATINGMAPSMAP_PREFIX = "map"
        self.MQTT_HEATINGMAPSPRECONFIGURED_PREFIX = "preconfigured"
        self.MQTT_HEATINGMAPSACTIVE_PREFIX = "active"
        self.MQTT_TOPIC_GLOBALOPCHANGE_CMD = "globalopchangecmd"
        self.MQTT_CMD_GLOBAL_OPCHANGE_DEACTIVATE = "deactivate"
        self.MQTT_CMD_GLOBAL_OPCHANGE_ACTIVATE = "activate"
        return

    def mqttSessionOpen(self):

        logging.debug("mqttSessionOpen called")
        self.mqttSession = mqttc.Client(client_id=self.mqttClientID, protocol=self.mqttProtocol,
                                        transport=self.mqttTransport)
        self.mqttSession.connect(host=self.mqttBrokerHostname, port=self.mqttBrokerPort, keepalive=self.mqttKeepAlive)
        return

    def mqttSessionClose(self):

        logging.debug("mqttSessionClose called")
        self.mqttSession.disconnect()
        #        logging.debug(self.mqttSession)
        return

    def mqttUpdateRealTemperature(self):

        logging.debug("mqttUpdateRealTemperature called")

        for j in range(1, 17):
            #            logging.debug(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_REAL_TEMPERATURE,
            #                  self.addressParameters[j]["realTemp"] + self.addressParameters[j]["tempOffset"])
            self.mqttSession.publish(
                self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_REAL_TEMPERATURE,
                self.addressParameters[j]["realTemp"] + self.addressParameters[j]["tempOffset"])

        return

    def mqttUpdateTargetTemperature(self):
        logging.debug("mqttUpdateTargetTemperature called")

        for j in range(1, 17):
            #            logging.debug(self.MQTT_TOPIC_ETATHERM_PREFIX+"/"+str(j)+"/"+self.MQTT_TOPIC_TARGET_TEMPERATURE,self.addressParameters[j]["targetTemp"]+self.addressParameters[j]["tempOffset"])
            if self.isFOCActive(j):
                logging.debug("opChange active for device %d, opChangeTemp %d, targetTemp %d ", j, self.addressParameters[j]["opChangeTemp"] + 5, self.addressParameters[j]["targetTemp"] + 5)
                self.mqttSession.publish(
                    self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_TARGET_TEMPERATURE,
                    self.addressParameters[j]["opChangeTemp"] + self.addressParameters[j]["tempOffset"])
            else:
                logging.debug("opChange inactive for device %d", j)
                self.mqttSession.publish(
                    self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_TARGET_TEMPERATURE,
                    self.addressParameters[j]["targetTemp"] + self.addressParameters[j]["tempOffset"])

        return

    # detects whether FOC is active for the device
    # input variables   deviceID integer
    # returns true/false

    def isFOCActive(self, deviceID):

        #        logging.debug(self.addressParameters[deviceID]["opChangeStartTime"],"->",self.addressParameters[deviceID]["opChangeEndTime"])
        timeNow = datetime.datetime.now()
        #        logging.debug(timeNow)
        if ((timeNow >= datetime.datetime.strptime(self.addressParameters[deviceID]["opChangeStartTime"],
                                                  "%Y-%m-%d %H:%M:%S") and timeNow <= datetime.datetime.strptime(
                self.addressParameters[deviceID]["opChangeEndTime"], "%Y-%m-%d %H:%M:%S")) or (self.addressParameters[deviceID]["opChangeHoldActive"] == 1)):
            logging.debug("FOC active for device %d", deviceID)
            return True
        else:
            return False

    def mqttUpdateMode(self):

        logging.debug("mqttUpdateMode called")
        for j in range(1, 17):
            mode = self.getMode(j)
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_MODE_PREFIX
            logging.debug("%s %s", topic, mode)
            logging.debug("Set mode %s for device %d", mode, j)
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_MODE_PREFIX,
                                     mode)
            logging.debug("Set mode %s for device %d", mode, j)

    def mqttUpdateMode_(self):

        for j in range(1, 17):
            focActive = self.isFOCActive(j)
            #            if focActive:
            #                logging.debug("FOC status %s for device %d",focActive,j)
            #                logging.debug("%s", self.addressParameters[j]["targetTemp"])
            if (focActive and (
                    self.addressParameters[j]["opChangeTemp"] == (6 - self.addressParameters[j]["tempOffset"]))):
                mode = "off"
            else:
                # jak poznam FOC off = 6st. a FOC heat s teplotou 6st? Asi nemuzu umoznit nastavit 6 st v modu heat
                if (focActive and (
                        self.addressParameters[j]["opChangeTemp"] > (6 - self.addressParameters[j]["tempOffset"]))):
                    mode = "heat"
                else:
                    mode = "auto"
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_MODE_PREFIX,
                                     mode)
            logging.debug("Set mode %s for device %d", mode, j)

    def enqueuePeriodicMqttUpdate(self):

        logging.debug("enqueuePeriodicMqttUpdate called")
        self.enqueueCmd({"cmd": self.CMD_UPDATE_MQTT, "deviceID": 0})
        return 0

    def enqueuePeriodicAddressParametersUpdate(self):

        logging.debug("enqueuePeriodicAddressParametersUpdate called")
        self.enqueueCmd({"cmd": self.CMD_RETRIEVE_ADDR_PARAM, "deviceID": 0})
        return 0

    def enqueueActiveHeatingMapMqttUpdate(self):

        logging.debug("enqueueActiveHeatingMapMqttUpdate called")
        self.enqueueCmd({"cmd" : self.CMD_UPDATE_MQTT_ACTIVE_HEATING_MAP})
        return 0

    def schedulePeriodicMqttUpdate(self):

        logging.debug("schedulePeriodicMqttUpdate called")
        schedule.every(60).seconds.do(self.enqueuePeriodicMqttUpdate)

    def schedulePeriodicAddressParametersUpdate(self):

        logging.debug("schedulePeriodicAddressParametersUpdate called")
        schedule.every(30).seconds.do(self.enqueuePeriodicAddressParametersUpdate)

    def mqttUpdate(self):

        logging.debug("mqttUpdate called")
        #        self.mqttSessionOpen()
        self.mqttUpdateMode()
        self.mqttUpdateTargetTemperature()
        self.mqttUpdateRealTemperature()
        self.mqttUpdateName()
        self.mqttUpdateDeviceType()
        self.mqttUpdateServiceTime()
        self.mqttUpdateControlsSwitch1()
        self.mqttUpdateControlsSwitch2()
        self.mqttUpdateDevicePass()
        self.mqttUpdateTempOffset()
        self.mqttUpdateOpChangeTemp()
        self.mqttUpdateOpChangeHoldActive()
        self.mqttUpdateOpChangeStartNextYear()
        self.mqttUpdateOpChangeEndNextYear()
        self.mqttUpdateOpChangeStartTime()
        self.mqttUpdateOpChangeEndTime()
        self.mqttUpdateOpChangePresetTemp()
        self.mqttUpdateOpChangePresetType()
        self.mqttUpdateOpChangePresetLength()
        self.mqttUpdateGlobalOpChangePresetTemp()
        self.mqttUpdateGlobalOpChangePresetType()
        self.mqttUpdateGlobalOpChangePresetLength()
        self.mqttUpdateActiveHeatingMap()






    #        self.mqttSessionClose()

    # retrieves address parameters and updates addressParameters dictionary
    # input variables   none
    # returns none

    def updateAddressParameters(self):

        logging.debug("updateAddressParameters called")

        self.etathermSessionOpen()
        self.setAddressParameters(self.retrieveAddressParameters())
        self.setAddressRealTemperature(self.retrieveRealTemperature())
        self.setAddressTargetTemperature(self.retrieveTargetTemperature)
        self.setFOCPresetParameters(self.retrieveFOCParameters())
        self.setGOCPresetParameters(self.retrieveGOCParameters())
        self.etathermSessionClose()

        logging.debug("updateAddressParameters finished")
#        logging.debug("%s", self.addressParameters)
        return

    # subscribes to all MQTT topics
    # input variables   none
    # returns           none

    def mqttSubscribeTopics(self):

        logging.debug("mqttSubscribeTopics called")

        for i in range(1, 17):
            modeTopic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(
                i) + "/" + self.MQTT_TOPIC_MODE_PREFIX + "/" + self.MQTT_TOPIC_SET_PREFIX
            #            logging.debug("%s", modeTopic)
            targetTemperatureTopic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(
                i) + "/" + self.MQTT_TOPIC_TARGET_TEMPERATURE + "/" + self.MQTT_TOPIC_SET_PREFIX
            #            logging.debug("%s", targetTemperatureTopic)
            self.mqttSession.subscribe(topic=modeTopic)
            self.mqttSession.subscribe(topic=targetTemperatureTopic)
        #    heatingProgramTopic = ETATHERMMQTTPREFIX + 'sys/heatingprogram/set'
        # logging.debug("%s", heatingProgramTopic)
#                 actHeatMap = self.findActiveHeatingMap()
        activatedHeatingMap = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + self.MQTT_TOPIC_SYSTEM_PREFIX + "/" + self.MQTT_TOPIC_HEATINGMAPS_PREFIX + "/" + self.MQTT_HEATINGMAPSACTIVE_PREFIX + "/" + self.MQTT_TOPIC_SET_PREFIX
        self.mqttSession.subscribe(topic=activatedHeatingMap)
        gocCmdTopic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + self.MQTT_TOPIC_SYSTEM_PREFIX + "/" + self.MQTT_TOPIC_GLOBALOPCHANGE_CMD
        self.mqttSession.subscribe(topic=gocCmdTopic)
        return 0

    def mqttDequeueMessage(self, client, userdata, message):
        # etatherm/1/mode/set
        # etatherm/1/mode/set
        # etatherm/1/temperature/target
        # etatherm/1/temperature/real
        # etatherm/1/temperature/target/set
        # etatherm/system/heatingmaps/active/set
        logging.debug("mqttDequeueMessage called")

        msg = str(message.payload, 'utf-8')
        topic = message.topic
        activatedHeatingMapTopic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + self.MQTT_TOPIC_SYSTEM_PREFIX + "/" + self.MQTT_TOPIC_HEATINGMAPS_PREFIX + "/" + self.MQTT_HEATINGMAPSACTIVE_PREFIX + "/" + self.MQTT_TOPIC_SET_PREFIX
        globalOpChangeCmdTopic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + self.MQTT_TOPIC_SYSTEM_PREFIX + "/" + self.MQTT_TOPIC_GLOBALOPCHANGE_CMD

        if topic == globalOpChangeCmdTopic:
            if msg == self.MQTT_CMD_GLOBAL_OPCHANGE_ACTIVATE:
                self.enqueueCmd({"cmd": self.CMD_GOC_ACTIVATE})
            if msg == self.MQTT_CMD_GLOBAL_OPCHANGE_DEACTIVATE:
                self.enqueueCmd({"cmd": self.CMD_GOC_DEACTIVATE})
            return 0
        if topic == activatedHeatingMapTopic:
            self.enqueueCmd({"cmd": self.CMD_ACTIVATE_HEATING_MAP, "heatingMapID": int(msg)})
            return 0

        for deviceID in range(1, 17):
            # User requested to set FTC mode
            # etatherm/1/mode/set
            if (topic == "etatherm/" + str(deviceID) + "/mode/set"):
                # Commit mode by sending it back to HA
                logging.debug("Publish->etatherm/%s %s", str(deviceID) + "/mode:", msg)
                # etatherm/1/mode
                self.mqttSession.publish("etatherm/" + str(deviceID) + "/mode", msg)
                newMode = msg
                if (newMode == self.HVAC_MODE_OFF):
                    logging.debug("Publish->etatherm/%s 6", str(deviceID) + "/temperature/target:")
                    logging.debug("Publish->etatherm/ %s %d", str(deviceID) + "/temperature/real:",
                          self.addressParameters[deviceID]["realTemp"] + self.addressParameters[deviceID]["tempOffset"])
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/target", "5")
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/target", "6")
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/real",
                                             self.addressParameters[deviceID]["realTemp"] +
                                             self.addressParameters[deviceID]["tempOffset"])
                    self.setFOCTemperature(deviceID, 6)
                    self.enqueueCmd({"cmd": self.CMD_FOC_ACTIVATE, "deviceID": deviceID})
                # activate FOC if not active

                if (newMode == self.HVAC_MODE_AUTO):
                    logging.debug("Publish->etatherm/%s %d", str(deviceID) + "/temperature/target:",
                          self.addressParameters[deviceID]["targetTemp"] + self.addressParameters[deviceID][
                              "tempOffset"])
                    logging.debug("Publish->etatherm/%s %d", str(deviceID) + "/temperature/real:",
                          self.addressParameters[deviceID]["realTemp"] + self.addressParameters[deviceID]["tempOffset"])
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/target",
                                             self.addressParameters[deviceID]["targetTemp"] +
                                             self.addressParameters[deviceID]["tempOffset"])
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/real",
                                             self.addressParameters[deviceID]["realTemp"] +
                                             self.addressParameters[deviceID]["tempOffset"])
                    # deactivate FOC if FOC active / enable auto mode
                    self.enqueueCmd({"cmd": self.CMD_FOC_DEACTIVATE, "deviceID": deviceID})

                if (newMode == self.HVAC_MODE_HEAT):
                    logging.debug("Publish->etatherm/%s %d", str(deviceID) + "/temperature/target:",
                          self.addressParameters[deviceID]["opChangePresetTemp"] + self.addressParameters[deviceID][
                              "tempOffset"])
                    logging.debug("Publish->etatherm/%s %d", str(deviceID) + "/temperature/real:",
                          self.addressParameters[deviceID]["realTemp"] + self.addressParameters[deviceID]["tempOffset"])
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/target",
                                             self.addressParameters[deviceID]["opChangePresetTemp"] +
                                             self.addressParameters[deviceID]["tempOffset"])
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/real",
                                             self.addressParameters[deviceID]["realTemp"] +
                                             self.addressParameters[deviceID]["tempOffset"])
                    self.setFOCTemperature(deviceID,self.addressParameters[deviceID]["opChangePresetTemp"]+self.addressParameters[deviceID]["tempOffset"])
                    self.enqueueCmd({"cmd": self.CMD_FOC_ACTIVATE, "deviceID": deviceID})
            # activate FOC if not active

            # User requested to set target temperature
            if (topic == "etatherm/" + str(deviceID) + "/temperature/target/set"):
                logging.debug("Temperature was set")
                setTemp = float(msg)
                mode = self.getMode(deviceID)
                logging.debug("Mode %s", mode)
                if mode == self.HVAC_MODE_OFF:
                    logging.debug("Publish->etatherm/%s 6", str(deviceID) + "/temperature/target:")
                    logging.debug("Publish->etatherm/%s %d", str(deviceID) + "/temperature/real:",
                          self.addressParameters[deviceID]["realTemp"] + self.addressParameters[deviceID]["tempOffset"])
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/target", "5")
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/target", "6")
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/real",
                                             self.addressParameters[deviceID]["realTemp"] +
                                             self.addressParameters[deviceID]["tempOffset"])

                if mode == self.HVAC_MODE_AUTO:
                    logging.debug("Publish->etatherm/%s %d", str(deviceID) + "/temperature/target:",
                          self.addressParameters[deviceID]["targetTemp"] + self.addressParameters[deviceID][
                              "tempOffset"])
                    logging.debug("Publish->etatherm/%s %d", str(deviceID) + "/temperature/real:",
                          self.addressParameters[deviceID]["realTemp"] + self.addressParameters[deviceID]["tempOffset"])
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/target",
                                             self.addressParameters[deviceID]["targetTemp"] +
                                             self.addressParameters[deviceID]["tempOffset"] - 1)
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/target",
                                             self.addressParameters[deviceID]["targetTemp"] +
                                             self.addressParameters[deviceID]["tempOffset"])
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/real",
                                             self.addressParameters[deviceID]["realTemp"] +
                                             self.addressParameters[deviceID]["tempOffset"])

                if mode == self.HVAC_MODE_HEAT:
                    logging.debug("Publish->etatherm/%s %d", str(deviceID) + "/temperature/target:", setTemp)
                    logging.debug("Publish->etatherm/%s %d", str(deviceID) + "/temperature/real:",
                          self.addressParameters[deviceID]["realTemp"] + self.addressParameters[deviceID]["tempOffset"])
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/target", setTemp)
                    self.mqttSession.publish("etatherm/" + str(deviceID) + "/temperature/real",
                                             self.addressParameters[deviceID]["realTemp"] +
                                             self.addressParameters[deviceID]["tempOffset"])
                    self.setFOCTemperature(deviceID, int(setTemp))
                    self.storeFOCTemperature(deviceID)

    #            logging.debug("%s", etherm.addressParameters)
        return 0


    def mqttRegisterCallback(self):

        logging.debug("mqttRegisterCallback called")
        self.mqttSession.on_message = self.mqttDequeueMessage
        return

    def getMode(self, deviceID):

        logging.debug("getMode called")
        focActive = self.isFOCActive(deviceID)
        #        if focActive:
        #            logging.debug("FOC status", focActive, "for device", deviceID)
        #            logging.debug(self.addressParameters[deviceID]["targetTemp"])
        logging.debug("FOC opChangeTemp for device %d is %d", deviceID, self.addressParameters[deviceID]["opChangeTemp"])
        if (focActive and (self.addressParameters[deviceID]["opChangeTemp"] == (
                6 - self.addressParameters[deviceID]["tempOffset"]))):
            mode = "off"
            logging.debug("Detected mode %s", mode)
        else:
            # jak poznam FOC off = 6st. a FOC heat s teplotou 6st? Asi nemuzu umoznit nastavit 6 st v modu heat
            if (focActive and (self.addressParameters[deviceID]["opChangeTemp"] > (
                    6 - self.addressParameters[deviceID]["tempOffset"]))):
                mode = "heat"
                logging.debug("Detected mode %s", mode)
            else:
                mode = "auto"
                logging.debug("Detected mode %s", mode)
        return mode

    def mqttUpdateName(self):

        logging.debug("mqttUpdateName called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_NAME_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["deviceName"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_NAME_PREFIX,
                                     self.addressParameters[j]["deviceName"])
        return 0

    def mqttUpdateDeviceType(self):
        logging.debug("mqttUpdateDeviceType called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_DEVICETYPE_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["deviceType"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_DEVICETYPE_PREFIX,
                                     self.addressParameters[j]["deviceType"])
        return 0


    def mqttUpdateServiceTime(self):
        logging.debug("mqttUpdateServiceTime called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_SERVICETIME_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["serviceTime"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_SERVICETIME_PREFIX,
                                     self.addressParameters[j]["serviceTime"])
        return 0

    def mqttUpdateControlsSwitch1(self):
        logging.debug("mqttUpdateControlsSwitch1 called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_CONTROLSSWITCH1_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["controlsSwitch1"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_CONTROLSSWITCH1_PREFIX,
                                     self.addressParameters[j]["controlsSwitch1"])
        return 0

    def mqttUpdateControlsSwitch2(self):
        logging.debug("mqttUpdateControlsSwitch2 called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_CONTROLSSWITCH2_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["controlsSwitch2"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_CONTROLSSWITCH2_PREFIX,
                                     self.addressParameters[j]["controlsSwitch2"])
        return 0

    def mqttUpdateDevicePass(self):
        logging.debug("mqttUpdateDevicePass called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_DEVICEPASS_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["devicePass"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_DEVICEPASS_PREFIX,
                                     self.addressParameters[j]["devicePass"])
        return 0

    def mqttUpdateTempOffset(self):
        logging.debug("mqttUpdateTempOffset called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_TEMPOFFSET_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["tempOffset"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_TEMPOFFSET_PREFIX,
                                     self.addressParameters[j]["tempOffset"])
        return 0


    def mqttUpdateOpChangeTemp(self):
        logging.debug("mqttUpdateOpChangeTemp called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGETEMP_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["opChangeTemp"] + self.addressParameters[j]["tempOffset"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGETEMP_PREFIX,
                                     self.addressParameters[j]["opChangeTemp"] + self.addressParameters[j]["tempOffset"])
        return 0


    def mqttUpdateOpChangeHoldActive(self):
        logging.debug("mqttUpdateOpChangeHoldActive called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEHOLDACTIVE_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["opChangeHoldActive"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEHOLDACTIVE_PREFIX,
                                     self.addressParameters[j]["opChangeHoldActive"])
        return 0

    def mqttUpdateOpChangeEndNextYear(self):
        logging.debug("mqttUpdateOpChangeEndNextYear called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEENDNEXTYEAR_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["opChangeEndNextYear"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEENDNEXTYEAR_PREFIX,
                                     self.addressParameters[j]["opChangeEndNextYear"])
        return 0

    def mqttUpdateOpChangeStartNextYear(self):
        logging.debug("mqttUpdateOpChangeStartNextYear called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGESTARTNEXTYEAR_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["opChangeStartNextYear"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGESTARTNEXTYEAR_PREFIX,
                                     self.addressParameters[j]["opChangeStartNextYear"])
        return 0

    def mqttUpdateOpChangeStartTime(self):
        logging.debug("mqttUpdateOpChangeStartTime called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGESTARTTIME_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["opChangeStartTime"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGESTARTTIME_PREFIX,
                                     self.addressParameters[j]["opChangeStartTime"])
        return 0


    def mqttUpdateOpChangePresetTemp(self):
        logging.debug("mqttUpdateOpChangePresetTemp called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEPRESETTEMP_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["opChangePresetTemp"] + self.addressParameters[j]["tempOffset"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEPRESETTEMP_PREFIX,
                                     self.addressParameters[j]["opChangePresetTemp"] + self.addressParameters[j]["tempOffset"])
        return 0


    def mqttUpdateOpChangePresetType(self):
        logging.debug("mqttUpdateOpChangePresetType called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEPRESETTYPE_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["opChangePresetType"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEPRESETTYPE_PREFIX,
                                     self.addressParameters[j]["opChangePresetType"])
        return 0

    def mqttUpdateOpChangeEndTime(self):
        logging.debug("mqttUpdateOpChangeEndTime called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEENDTIME_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["opChangeEndTime"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEENDTIME_PREFIX,
                                     self.addressParameters[j]["opChangeEndTime"])
        return 0


    def mqttUpdateOpChangePresetLength(self):
        logging.debug("mqttUpdateOpChangePresetLength called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEPRESETLENGTH_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["opChangePresetLength"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_OPCHANGEPRESETLENGTH_PREFIX,
                                     self.addressParameters[j]["opChangePresetLength"])
        return 0


    def mqttUpdateGlobalOpChangePresetTemp(self):
        logging.debug("mqttUpdateGlobalOpChangePresetTemp called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_GLOBALOPCHANGEPRESETTEMP_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["globalOpChangePresetTemp"] + self.addressParameters[j]["tempOffset"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_GLOBALOPCHANGEPRESETTEMP_PREFIX,
                                     self.addressParameters[j]["globalOpChangePresetTemp"] + self.addressParameters[j]["tempOffset"])
        return 0


    def mqttUpdateGlobalOpChangePresetType(self):
        logging.debug("mqttUpdateGlobalOpChangePresetType called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_GLOBALOPCHANGEPRESETTYPE_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["globalOpChangePresetType"])
            self.mqttSession.publish(self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_GLOBALOPCHANGEPRESETTYPE_PREFIX,
                                     self.addressParameters[j]["globalOpChangePresetType"])
        return 0

    def mqttUpdateGlobalOpChangePresetLength(self):
        logging.debug("mqttUpdateGlobalOpChangePresetLength called")
        for j in range(1, 17):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(
                j) + "/" + self.MQTT_TOPIC_GLOBALOPCHANGEPRESETLENGTH_PREFIX
            logging.debug("%s %s", topic, self.addressParameters[j]["globalOpChangePresetLength"])
            self.mqttSession.publish(
                self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + str(j) + "/" + self.MQTT_TOPIC_GLOBALOPCHANGEPRESETLENGTH_PREFIX,
                self.addressParameters[j]["globalOpChangePresetLength"])
        return 0

    def mqttUpdateHeatingMaps(self):

        logging.debug("mqttUpdateHeatingMaps called")
        dicLen = len(self.heatingMaps)
        topicPreconfigured = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + self.MQTT_TOPIC_SYSTEM_PREFIX + "/" + self.MQTT_TOPIC_HEATINGMAPS_PREFIX +"/" + self.MQTT_HEATINGMAPSPRECONFIGURED_PREFIX
        self.mqttSession.publish(topicPreconfigured, dicLen)
        for i in range(1, dicLen+1):
            topic = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + self.MQTT_TOPIC_SYSTEM_PREFIX + "/" + self.MQTT_TOPIC_HEATINGMAPS_PREFIX + "/" + str(i)
            topicName = topic + "/" + self.MQTT_HEATINGMAPSNAME_PREFIX
            topicType = topic + "/" + self.MQTT_HEATINGMAPSTYPE_PREFIX
            self.mqttSession.publish(topicName, self.heatingMaps[i]['name'])
            self.mqttSession.publish(topicType, self.heatingMaps[i]['type'])
            for j in range(1, 17):
                topicMap = topic + "/" + self.MQTT_HEATINGMAPSMAP_PREFIX + "/" + str(j)
                self.mqttSession.publish(topicMap, str(self.heatingMaps[i][j]))
        return 0

    def mqttUpdateActiveHeatingMap(self):

        logging.debug("mqttUpdateActiveHeatingMap called")
        actHeatMap = self.findActiveHeatingMap()
        topicActiveHeatingMap = self.MQTT_TOPIC_ETATHERM_PREFIX + "/" + self.MQTT_TOPIC_SYSTEM_PREFIX + "/" + self.MQTT_TOPIC_HEATINGMAPS_PREFIX + "/" + self.MQTT_HEATINGMAPSACTIVE_PREFIX
        self.mqttSession.publish(topicActiveHeatingMap, actHeatMap)
        return 0

    def findActiveHeatingMap(self):

        logging.debug("findActiveHeatingMap called")
        for i in range(1, len(self.heatingMaps)+1):
            actHeatMap = 0
            for j in range (1, 17):
#                logging.debug("Heating map %d for device %d is %s", i, j, str(self.heatingMaps[i][j]))
#                logging.debug("Heating map for device %d is %s", j, str(self.addressParameters[j]["activeHeatingMap"]))
                if self.heatingMaps[i][j] == self.addressParameters[j]["activeHeatingMap"]:
                    actHeatMap = actHeatMap+1
#                    logging.debug("actHeatMap %d", actHeatMap)
            if actHeatMap == 16:
                logging.debug("ActiveHeatingMap is %d", i)
                return i

        logging.debug("findActiveHeatingMap finished")
        return 0

