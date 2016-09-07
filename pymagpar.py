def raw_decode(cdata, track):
    '''Decode stream into raw timing values'''
    retstr = ""
    tdata = cdata.get_raw_track_timing(track)
    for ctdata in tdata:
        retstr += str(ctdata) + " "
    return retstr

def f2f_raw_decode(cdata, track):
    '''Decode F2F bitstream represented by timing values into binary string'''
    tvalues = cdata.get_raw_track_timing(track)
    tloop = 10
    pstr = "0" * tloop
    zerotime = sum(tvalues[1:tloop])/len(tvalues[1:tloop])
    while tloop < len(tvalues)-2:
        if tvalues[tloop] < ((zerotime*3)/4) and tvalues[tloop+1] > (zerotime/4):
            zerotime = tvalues[tloop] + tvalues[tloop+1]
            tloop += 2
            pstr += "1"
        elif tvalues[tloop] < (zerotime*1.25) and tvalues[tloop] > (zerotime*0.75):
            zerotime = tvalues[tloop]
            tloop += 1
            pstr += "0"
        else:
            raise TypeError("F2F parse error")
    return pstr

#def f2ft1v_decode():
#    rbstream = f2f_raw_decode(cdata, track)
#    sind = rbstream.find("11111110")
    
#def f2ft23v_decode():
#    rbstream = f2f_raw_decode(cdata, track)
#    sind = rbstream.find("11111110")

def p1v_decode(cdata, track):
    '''Decode and check data from type 1 parking cards'''
    rbstream = f2f_raw_decode(cdata, track)
    sind = rbstream.find("11111110")
    if sind == -1:
        raise TypeError("Start sentinel not found")
    if (len(rbstream)-sind) < (25*8):
        raise TypeError("Incomplete data stream")
    symx = [None] * 25
    for symi in range(25):
        symid = sind + (symi*8)
        symx[symi] = rbstream[symid:symid+8]
    if symx[0] != symx[24][::-1]:
        raise TypeError("End sentinel mismatch")
    for symi in range(1, 13):
        if symx[symi] != symx[24-symi]:
            raise TypeError("Repeat value mismatch")
    xorcheck = 0xFF
    for symi in range(1, 11):
        xorcheck ^= int(symx[symi], 2)
    if(xorcheck != int(symx[13], 2)):
        raise TypeError("Checksum mismatch")
    for symi in range(25):
        tmplst = list(symx[symi])
        for curbit in range(len(tmplst)):
            if tmplst[curbit] == '0':
                tmplst[curbit] = '1'
            else:
                tmplst[curbit] = '0'
        symx[symi] = ''.join(tmplst)
    return ''.join(symx[:])

'''
def _parking1_decode(nblob):
    if len(nblob) % 2 != 0:
        raise TypeError("Failed to decode card")
    pnblob = ""    
    for hbcount in range(0, len(nblob), 2):
        if nblob[hbcount] < nblob[hbcount+1]:
            pnblob += "1"
        else:
            pnblob += "0"
    return pnblob
    
def _parking1_nstart(tvalues, index, avgt):
    avgec = 0
    for tloop in range(index, len(tvalues)):
        if tvalues[tloop] > (avgt*2):
            avgec += 1
        else:
            avgec = 0
        if avgec == 3:
            return tloop+1
    if tloop == len(tvalues)-1:
        return 0

def parking1_raw(tvalues):
    avgt = sum(tvalues)/len(tvalues)
    index1 = PyMAGPar._parking_nstart(tvalues, 0, avgt)
    index2 = PyMAGPar._parking_nstart(tvalues, index1, avgt)
    index3 = PyMAGPar._parking_nstart(tvalues, index2, avgt)
    if index1 == 0 or index2 == 0 or index3 == 0:
        raise TypeError("Failed to decode card")
    db1 = tvalues[index1: index2-3]
    db2 = tvalues[index2: index3-3]
    if len(db1) != len(db2):
        raise TypeError("Failed to decode card")
    if len(db1) != 224:
        raise TypeError("Failed to decode card")
    pdb1 = PyMAGPar._parking_decode(db1)
    pdb2 = PyMAGPar._parking_decode(db2)
    if pdb1 != pdb2:
        raise TypeError("Failed to decode card")
    return pdb1
'''
