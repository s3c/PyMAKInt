#!/user/bin/env python3

import serial
import struct
import math
import os

class PyMAKInt:
    
    TRACK1 = 0x01
    TRACK2 = 0x02
    TRACK3 = 0x04
    CHARB7 = 0x80
    
    def __init__(self, port = '/dev/ttyUSB0', deftracks = (TRACK1 | TRACK2 | TRACK3)):
        '''Open the default USB port and check reader version, tested on MSUSB CZ.090211'''
        self._portname = port
        self._defracks = deftracks
        try:
            self._serialobj = serial.Serial(port, 38400, timeout = 1)
        except serial.serialutil.SerialException:
            raise serial.SerialException('Error opening serial port')
        self._serialobj.write(b'?')
        self._rversion = self._serialobj.read(15)
        if self._rversion == b'':
            raise serial.SerialException('Reader not responding')
        if self._rversion[0:5] != b'MSUSB':
            raise serial.SerialException('Reader not valid')

    def __str__(self):
        print(self._rversion)

    def __iter__(self):
        return self
        
    def __next__(self):
        try:
            cdat = self.read_tracks_raw()
        except serial.SerialException as e:
            if str(e) == "Card read timeout occurred":
                raise StopIteration
        return cdat

    def read_tracks_raw(self, tracks = None, timeout = 30):
        '''Wait for a card swype and return the raw timing data'''
        tracks =  tracks if tracks else self._defracks
        if (tracks & ~(PyMAKInt.TRACK1 | PyMAKInt.TRACK2 | PyMAKInt.TRACK3)) != 0 or \
            (tracks & (PyMAKInt.TRACK1 | PyMAKInt.TRACK2 | PyMAKInt.TRACK3)) == 0:
            raise ValueError('Invalid track specified')
        self._serialobj.timeout = 1
        self._serialobj.write(b'R' + bytes([tracks]))
        readbytes = self._serialobj.read(5)
        if readbytes != b'Ready':
            raise serial.SerialException('Error initialising card read')
        self._serialobj.timeout = timeout
        readbytes = self._serialobj.read(3)
        if readbytes == b'':
            raise serial.SerialException('Card read timeout occurred')
        elif readbytes != b'RD ':
            raise serial.SerialException('Invalid data from reader')
        self._serialobj.timeout = 1
        readbytes = self._serialobj.read(2)
        tickcount = (readbytes[0] << 8) + readbytes[1]
        ticksbytes = (tickcount * 2) + (2 if (tickcount % 2) != 0 else 0)
        databytes = self._serialobj.read(ticksbytes)
        readbytes = self._serialobj.read(5)
        if readbytes != b'RD=OK':
            raise serial.SerialException('Error, data alignment problem')
        return PyMAKDat(list(databytes[0:tickcount*2]))
    
    #def read_into_buffer(self, tracks = TRACK1 | TRACK2 | TRACK3, timeout = 30)
    #    pass
    
    #def write_tracks_raw(self, data):
    #    pass
    
    #def reset_reader(self)
    #    pass
    
    def format_tracks(self, tracks = None, secs = 10):
        '''Format specific tracks to known state, ie, 10101..., not tested'''
        tracks = tracks if tracks else self._deftracks
        if (tracks & ~(PyMAKInt.TRACK1 | PyMAKInt.TRACK2 | PyMAKInt.TRACK3)) != 0 or \
            (tracks & (PyMAKInt.TRACK1 | PyMAKInt.TRACK2 | PyMAKInt.TRACK3)) == 0:
            raise ValueError('Invalid track specified')
        self._serialobj.write(b'F' + bytes([tracks] + bytes([secs * 8]) + b'\\'))
        self._serialobj.timeout = 1
        readbytes = self._serialobj.read(3)
        if readbytes != b'FM ':
            raise serial.SerialException('Error initializing card format')
        self._serialobj.timeout = 1 + (secs * 8)
        readbytes = self._serialobj.read(5)
        if readbytes != b'FM=OK':
            raise serial.SerialException('Error performing card format')
    
    def erase_tracks(self, tracks = None, secs = 10, reverse = False):
        '''Erase data on selected tracks in forward or reverse direction for secs seconds, not tested'''
        tracks =  tracks if tracks else self._deftracks
        if (tracks & ~(PyMAKInt.TRACK1 | PyMAKInt.TRACK2 | PyMAKInt.TRACK3)) != 0 or \
            (tracks & (PyMAKInt.TRACK1 | PyMAKInt.TRACK2 | PyMAKInt.TRACK3)) == 0:
            raise ValueError('Invalid track specified')
        self._serialobj.write((b'e' if reverse else b'E') + bytes([tracks]) + bytes([secs]))
        self._serialobj.timeout = 1
        readbytes = self._serialobj.read(3)
        if readbytes != (b'eR ' if reverse else b'Er '):
            raise serial.SerialException('Error initialising card erase')
        self._serialobj.timeout = 1 + secs    
        readbytes = self._serialobj.read(5)
        if readbytes != (b'eR=OK' if reverse else b'Er=OK'):
            raise serial.SerialException('Error card erase failure')
    
    def read_eeprom_single(self, savenum = 1):
        '''Read a single card entry from the EEPROM, not tested'''
        if savenum < 1 or savenum > 20:
            raise ValueError('Invalid EEPROM entry specified') 
        alltrackdata = []
        self._serialobj.write(b'I' + bytes([savenum]) + b'\01')
        self._serialobj.timeout = 2
        for tracknum in range(3):
            cline = self._serialobj.readline().decode()
            if len(cline) < 4 or cline[0] != '#':
                raise ValueError('Error reading track value')
            alltrackdata += [cline.split("'")[1]]
        return alltrackdata
    
    def read_eeprom_all(self):
        '''Read all 20 entries from the EEPROM, not tested'''
        eepromlist = []
        for tracknum in range(1, 21):
            eepromlist += self.read_eeprom_single(tracknum)
        return eepromlist
    
    def erase_eeprom(self):
        '''Erase the EEPROM, not tested'''
        self._serialobj.write(b'H')
        self._serialobj.timeout = 10
        erres = self._serialobj.read(5)
        if erres == b'':
            raise serial.SerialException('Error, timeout while erasing device')
        elif erres != b'EZ=OK':
            raise serial.SerialException('Error, invalid confirmation from device')


class PyMAKDat:
    
    def __init__(self, data = None):
        self._rawtracktiming = [[], [], []]
        if isinstance(data, str):
            self._load_file(data)
        elif isinstance(data, list):
            self._rawdata = data
        self._calc_raw_timing()
                    
    def __str__(self):
        retstr = str()
        for tracknum in range(3):
            for trackval in range(len(self._rawtracktiming[tracknum])):
                retstr += str(self._rawtracktiming[tracknum][trackval]) + " "
            retstr += "\n"
        return retstr
    
    def _calc_raw_timing(self):
        '''Calculate the interval between ticks for all tracks'''
        if self._rawdata != None:
            if len(self._rawdata) % 2 != 0:
                raise ValueError("Raw data length mismatch")
            tracktiming = [0, 0, 0]
            trackstate = [False, False, False]
            trackstate[0] = bool(self._rawdata[1] & PyMAKInt.TRACK1)
            trackstate[1] = bool(self._rawdata[1] & PyMAKInt.TRACK2)
            trackstate[2] = bool(self._rawdata[1] & PyMAKInt.TRACK3)
            for curtick in range(2, len(self._rawdata), 2):
                timingvalue = self._rawdata[curtick-2] + ((self._rawdata[curtick-1] & PyMAKInt.CHARB7) << 1)
                maskvalue = self._rawdata[curtick+1] & (PyMAKInt.TRACK1 | PyMAKInt.TRACK2 | PyMAKInt.TRACK3)
                if bool(self._rawdata[curtick+1] & ~(PyMAKInt.TRACK1 | PyMAKInt.TRACK2 | PyMAKInt.TRACK3 | PyMAKInt.CHARB7)):
                    raise ValueError("Error parsing tick transition")
                for i in range(3):
                    tracktiming[i] += timingvalue
                    if trackstate[i] != bool(maskvalue & pow(2, i)):
                        self._rawtracktiming[i] += [tracktiming[i]]
                        trackstate[i] = not trackstate[i]
                        tracktiming[i] = 0
            for i in range(3):
                if len(self._rawtracktiming[i]) < 10:
                    self._rawtracktiming[i] = []
        
    def _load_file(self, inputfile):
        '''Load the data from a .mag compatible file'''
        if inputfile[-4:] != ".mag":
            raise ValueError("Filename must end with a .mag extension")
        fileh = open(inputfile, "rb")
        tcount = struct.unpack("i", fileh.read(4))[0]
        if os.path.getsize(inputfile) != (4 + (tcount*2*4)):
            raise ValueError("Error parsing input file, length mismatch")
        self._rawdata = [0] * ((tcount * 2) + 2)
        lasttf = float(0)
        for curtick in range(0, tcount*2, 2):
            curmask = struct.unpack("i", fileh.read(4))[0] >> 4
            if (curmask & ~(PyMAKInt.TRACK1 | PyMAKInt.TRACK2 | PyMAKInt.TRACK3)) != 0:
                raise ValueError("Error parsing input file, transition mismatch")
            newtf = struct.unpack("f", fileh.read(4))[0]
            if newtf < lasttf:
                raise ValueError("Error parsing input file, timing mismatch")
            tdiff = int((newtf - lasttf) * 150)
            self._rawdata[curtick] += tdiff & 0xFF
            self._rawdata[curtick+1] += (tdiff >> 1) & PyMAKInt.CHARB7
            self._rawdata[curtick+3] += curmask
            lasttf = newtf
        del self._rawdata[-2:]
        #Change initial flags to neg of first file flags here?
        fileh.close()        
        
    def save_file(self, outputfile):
        '''Save the data in a .mag compatible file'''
        if outputfile[-4:] != ".mag":
            raise ValueError("Filename must end with a .mag extension")
        fileh = open(outputfile, "wb")
        tickcount = int(len(self._rawdata) / 2)
        self._rawdata += [0x00, 0x00]                                   
        fileh.write(struct.pack("i", tickcount))                        
        timetotick = float(0)
        for curtick in range(0, tickcount*2, 2):
            timingvalue = self._rawdata[curtick] + (((self._rawdata[curtick+1] & PyMAKInt.CHARB7)) << 1)
            maskvalue = self._rawdata[curtick+3] & (PyMAKInt.TRACK1 | PyMAKInt.TRACK2 | PyMAKInt.TRACK3)
            timetotick += (timingvalue / 150)
            maskvalue <<= 4
            fileh.write(struct.pack("i", maskvalue))
            fileh.write(struct.pack("f", timetotick))
        del self._rawdata[-2:]
        fileh.close()
        
    def get_raw_track_timing(self, track):
        '''Return the timing values for a given track'''
        if bin(track).count("1") != 1 or (track & ~(PyMAKInt.TRACK1 | PyMAKInt.TRACK2 | PyMAKInt.TRACK3)) != 0:
            raise ValueError('Invalid track specified')
        return self._rawtracktiming[int(math.log(track, 2))]
          
    def set_raw_track_timing(self, track, rawtiming):
        '''Calculate raw data from timing data'''  
        '''error checking for max length'''
        pass    
