#!/usr/bin/env python3

#features
#null hardware write (ie save only?)

import pymakint
import pymagpar
import serial
import argparse
import sys
import glob

def parse_args():
    agp = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description="abc\ndef", epilog="ghi\njkl")
    #example for -r, -l with -e to save filename as csv param
    #description
    agp_mx1 = agp.add_mutually_exclusive_group(required=True)
    agp_mx1.add_argument("-r", "--read", help="Read data from card", action='store_true')
    agp_mx1.add_argument("-w", "--write", help="Write data to card", action='store_true')
    agp_mx1.add_argument("-f", "--format", help="Format track for n seconds", type=int)
    agp_mx1.add_argument("-er", "--eepromread", help="Read data item n from eeprom", type=int)
    agp_mx1.add_argument("-era" "--eepromreadall", help="Read all data from eeprom", action='store_true')
    agp_mx1.add_argument("-ee", "--eepromerase", help="Erase all data from eeprom", action='store_true')
    agp_mx1.add_argument("-E", "--Erase", help="Wipe card in one direction for n seconds", type=int)
    agp_mx1.add_argument("-R", "--eRase", help="Wipe card in reverse direction for n seconds", type=int)
    #copy command using buffers here?
    agp.add_argument("-t", "--track", help="Track number for enc/dec operation, defaults to 2", type=int, default=2)
    agp.add_argument("-p", "--port", help="Port reader is connected to, defaults to /dev/ttyUSB0", type=str)
    #read only
    agp.add_argument("-e", "--extended", help="Extended filename for csv data", type=str)
    #write only
    agp.add_argument("-v", "--verify", help="Verify data written to card (requires -ed)", action='store_true')
    #read/write only
    agp.add_argument("-ed", "--enc-dec", help="Encoder/Decoder to use for read/write\n"
                                              "NONE - r - do not use encoded/decoded data stream (default)\n"
                                              "RAW - r/w - use raw timing data\n"
                                              "F2FRAW - r/w - use raw F2F bitstream\n"
                                              "FHFRAW - r/w - use raw FHF bitstream\n"
                                              "F2FT1V - r/w - use F2F bitstream only on T1 LRC integrity check\n"
                                              "F2FT23V - r/w - use F2F bitstream on T2 or T3 LRC integrity check\n"
                                              "P1V - r/w - use F2F bitstream only on P1 integrity check\n"
                                              "P2V - r/w - use FHF bitstream only on P2 integrity check\n", type=str, default="NONE")    
    agp.add_argument("-d", "--data", help="File to load/save data streams, one per line (requires -ed)", type=str)
    agp_mx2 = agp.add_mutually_exclusive_group()
    agp_mx2.add_argument("-s", "--save", help="Save raw swipe data to SAVE-X.MAG, where X is incremental", type=str)
    agp_mx2.add_argument("-l", "--load", help="Load raw swipe data from .MAG file", nargs="*", type=str)
    ags = agp.parse_args()
    
    #*when reading, if -l is specified, port should not be used
    if ags.read and ags.load and ags.port != None:
        print("Error: when using load for reading port isn't allowed")
        sys.exit(1)
    #*when reading, if encoder is not specified, -s has to be
    if ags.read and ags.enc_dec == "NONE" and not ags.save:
        print("Error: when reading either a decoder or save is required")
        sys.exit(2)
    #*extended only allowed when reading
    if ags.extended and not ags.read:
        print("Error: extended only allowed when reading")
        sys.exit(3)
    #*verify only allowed when writing
    if ags.verify and not ags.write:
        print("Error: verify only allowed when writing")
        sys.exit(4)
    #*verify requires encoder/decoder
    if ags.verify and ags.enc_dec == "NONE":
        print("Error: verify requires encoder/decoder")
        sys.exit(5)
    #*data requires either read or write
    if ags.data and not ags.read and not ags.write:
        print("Error: data only allowing for read/write")
        sys.exit(6)
    #*data requires encoder/decoder
    if ags.data and ags.enc_dec == "NONE":
        print("Error: data requires encoder/decoder")
        sys.exit(7)
    #*load/save allowed only for read/write
    if (ags.load or ags.save) and (not ags.read and not ags.write):
        print("Error: load and save allowed only for read and write")
        sys.exit(8)
    #*when writing, can't have load and data
    if ags.write and ags.load and ags.data:
        print("Error: writing allows only load or data")
        sys.exit(9)
    #*when writing, either encoder or load is required
    if ags.write and not ags.load and ags.enc_dec == "NONE":
        print("Error: writing requires either encoder or load")
        sys.exit(11)
    #*when writing, only encoder or load is allowed
    if ags.write and ags.load and ags.enc_dec != "NONE":
        print("Error: writing allows only load or encoder")
        sys.exit(12)
    #*sanity check for track number
    if not 1 <= ags.track <= 3:
        print("Error: invalid track specified")
        sys.exit(13)
    #*encoder/decoder requires read or write
    if ags.enc_dec != "NONE" and (not ags.read and not ags.write):
        print("Error: encoder/decoder valid only for read and write")
        sys.exit(16)
    return ags

def init_reader(ags):
    try:
        ags.port = "/dev/ttyUSB0" if not ags.port else ags.port
        csource = pymakint.PyMAKInt(port = ags.port, deftracks = ags.track)
    except serial.SerialException as e:
        print(e)
        sys.exit(14)
    return csource

def select_decoder(ags):
    if ags.enc_dec == "NONE":
        return None
    elif ags.enc_dec.upper() == "RAW":
        return pymagpar.raw_decode
    elif ags.enc_dec.upper() == "F2FRAW":
        return pymagpar.f2f_raw_decode
    elif ags.enc_dec.upper() == "P1V":
        return pymagpar.p1v_decode
    else:
        print("Error: invalid decoder specified")
        sys.exit(15)

def init_extended(ags):
    if not ags.extended:
        return
    try:
        inpfile = open(ags.extended, "r+")
    except FileNotFoundError:
        inpfile = open(ags.extended, "w+")
    extdat = {}
    extdat["handle"] = inpfile
    extdata = inpfile.read()
    extlst = extdata.split()
    if not len(extlst):
        extdat["fields"] = query_extended_init()
        extdat["linecount"] = 0
        extdat["handle"].write(",".join(extdat["fields"]) + "\n")
    else:
        extdat["fields"] = extlst[0].split(",")
        extdat["linecount"] = len(extlst) - 1
    return extdat
    
def query_extended_init():
    allinp = []
    print("No extxended parameters found, enter a couple followed with a blank input")
    while True:
        usrinp = input("Paramater name: ")
        if usrinp == "":
            break
        allinp += [usrinp]
    return allinp
    
def query_extended_val(ags, extdat):
    if not ags.extended:
        return
    parvals = []
    for parname in extdat["fields"]:
        parval = input("Value for " + parname + ":")
        if parval == "":
            parvals += ["NONE"]
        else:
            parvals += [parval]
    return parvals
    
def save_data(ags, curcard, str_rep, datdat, str_ext, extdat):
    if ags.data:
        datdat["handle"].write(str_rep + "\n")
    if ags.extended:
        extsav = ",".join(str_ext) + "\n"
        extdat["handle"].write(extsav)
    #-l with -e to save filename as csv param
    #add something that allows -l with -e to prompt/parse when only one card is given for -l
    if ags.save:
        curcard.save_file(ags.save + "-" + str(save_data.savecount).zfill(3) + '.mag')
        save_data.savecount += 1
    
def init_data(ags):
    if not ags.data:
        return
    try:
        inpfile = open(ags.data, "r+")
    except FileNotFoundError:
        inpfile = open(ags.data, "w+")
    datdat = {}
    datdat["handle"] =  inpfile
    readdat = inpfile.read()
    readdat = readdat.split("\n")
    readdat = [ x for x in filter(None, readdat) ]
    datdat["linecount"] = len(readdat)
    return datdat

def save_count_init(ags):
    if not ags.save:
        return
    flist = glob.glob(ags.save + "-*.mag")
    if not flist:
        save_data.savecount = 1
    else:
        flist.sort(reverse=True)
        save_data.savecount = int(flist[0][-7:-4:]) + 1
        print("Continuing save from: " + str(save_data.savecount))

def command_read(ags):

    if ags.load:
        try:
            csource = []
            for inpfile in ags.load:
                csource += [pymakint.PyMAKDat(inpfile)]
        except ValueError as e:
            print(e)
            sys.exit(17)
    else:
        csource = init_reader(ags)
    
    extdat = None
    datdat = None
    str_rep = None
    str_ext = None
    
    try:
        extdat = init_extended(ags)
        datdat = init_data(ags)
        save_count_init(ags)
    
        if ags.data and ags.extended:
            if extdat["linecount"] != datdat["linecount"]:
                print("Error: data and extended files have different number of item lines")
                print(extdat["linecount"])
                print(datdat["linecount"])
                sys.exit(18)
    
        decode_func = select_decoder(ags)
    
        print("Reading cards, press CTRL-D/C to quit")
        
        cursave = 0
        for curcard in csource:
            print("Swype next card")
            if decode_func:
                try:
                    str_rep = decode_func(curcard, ags.track)
                except TypeError as e:
                    print(e)
                    continue
                print(str_rep)
            str_ext = query_extended_val(ags, extdat)
            save_data(ags, curcard, str_rep, datdat, str_ext, extdat)
    except (KeyboardInterrupt, EOFError):
        pass
    if extdat:
        extdat["handle"].close()
    if datdat:
        datdat["handle"].close()        
    
def command_write(ags):
    pass

def command_format(ags):
    init_reader(ags)
    print("Formatting track " + str(ags.track) + " for " + str(ags.format) + "seconds")
    format_tracks(secs = ags.format)

def command_eepromread(ags):
    init_reader(ags)
    sineeprom = read_eeprom_single(savenum = ags.eepromread)
    print("Slot " + ags.eeprom + " data: ")
    for track in sineeprom:
        print(track)

def command_eepromreadall(ags):
    init_reader(ags)
    alleeprom = read_eeprom_all()
    print("All eeprom data:")
    for slot in alleeprom:
        for track in slot:
            print(track)

def command_eepromerase(ags):
    init_reader(ags)
    print("Erasing eeprom")
    erase_eeprom()

def command_erase(ags):
    init_reader(ags)
    if ags.Erase:
        print("Erasing data for " + ags.Erase + "seconds")
        erase_tracks(secs = ags.Erase, reverse = False)
    else:
        print("eRasing data for " + ags.eRase + "seconds")
        erase_tracks(secs = ags.eRase, reverse = True)

if __name__ == '__main__':
    ags = parse_args()

    #print(ags)

    if ags.read:
        command_read(ags)
    elif ags.write:
        command_write(ags)
    elif ags.format != None:
        command_format(ags)
    elif ags.eepromread != None:
        command_eepromread(ags)
    elif ags.era__eepromreadall:
        command_eepromreadall(ags)
    elif ags.eepromerase:
        command_eepromerase(ags)
    elif ags.Erase != None or ags.eRase != None:
        command_erase(ags)
