#!/usr/bin/env python3

import argparse
import sys
import re
import csv

def validate_params(ags):
    bindatlst = ags.file.read()
    if re.search("[^01\n]", bindatlst):
        print("Invalid character in input file")
        sys.exit(0)
    ags.file.seek(0)
    if not ags.extended and (ags.extended_filter or ags.extended_sort):
        print("Filter input file required")
        sys.exit(1)
    if ags.split:
        if re.search("[^0-9,]", ags.split):
            print("Invalid character in split list")
            sys.exit(2)
    if ags.repeat and not ags.split:
        print("Split list not specified")
        sys.exit(3)
    
def align_and_padd(ags, strlst):
    if ags.no_align == False:
        indlst = [ x.find("0" if ags.padding else "1") for x in strlst ]
        maxlst = max(indlst)
        for strind in range(len(strlst)):
            strlst[strind] = (("1" if ags.padding else "0") * (maxlst - indlst[strind])) + strlst[strind]
    indlen = [ len(x) for x in strlst ]
    for strind in range(len(strlst)):
        strlst[strind] = strlst[strind].ljust(max(indlen), "1" if ags.padding else "0")
        if ags.add_start:
            strlst[strind] = (("1" if ags.padding else "0") * ags.add_start) + strlst[strind]
        if ags.add_end:
            strlst[strind] = strlst[strind] + (("1" if ags.padding else "0") * ags.add_end)
        if ags.remove_start:
            strlst[strind] = strlst[strind][ags.remove_start:]
        if ags.remove_end:
            strlst[strind] = strlst[strind][:-ags.remove_end]
    if ags.invert_after:
        strlst = invert_bits(strlst)
    return strlst

def invert_bits(strlst):
    newlst = []
    for cline in strlst:
        tmp = list(cline)
        for curchar in range(len(tmp)):
            if tmp[curchar] == "0":
                tmp[curchar] = "1"
            else:
                tmp[curchar] = "0"
        newlst += [''.join(tmp)]
    return newlst

def calc_weight(ags, bindatlst):
    colweight = []
    for curcol in range(len(bindatlst[0])):
        wcount = {"0":0, "1":0}
        for currow in range(len(bindatlst)):
            wcount[bindatlst[currow][curcol]] += 1
        if wcount["0"] < wcount["1"]:
            wcount["CW"] = wcount["0"]
            wcount["CC"] = "0"
        else:
            wcount["CW"] = wcount["1"]
            wcount["CC"] = "1"
        colweight += [wcount]
    return colweight

def print_res(ags, bindatlst, colweight, splits):
    NC='\033[0m'
    COL='\033[0;34m'
    if ags.split:
        splitpos = [splits[0]]
        for cursplit in range(1, len(splits)):
            splitpos += [splitpos[cursplit-1] + splits[cursplit]]
    for currow in range(len(bindatlst)):
        for curcol in range(len(bindatlst[0])):
            if ags.split and curcol in splitpos:
                print(" ", end="")
            if colweight[curcol]["CW"]:
                if ags.no_color:
                    print(bindatlst[currow][curcol], end="")
                else:
                    print(COL + bindatlst[currow][curcol] + NC, end="")
            else:
                print(bindatlst[currow][curcol], end="")
        print()
        
def format_splits(ags, bindatlst):
    if not ags.split:
        return None
    splits = ags.split.split(",")
    for csplit in splits:
        if csplit == '':
            print("Invalid split list")
            sys.exit(4)
    splits = [ int(x) for x in splits ]
    splitsm = []
    maxlen = len(bindatlst[0])
    curlen = 0
    cursplit = 0
    while (curlen+splits[cursplit]) < maxlen:
        curlen += splits[cursplit]
        splitsm += [splits[cursplit]]
        cursplit += 1
        if cursplit == len(splits):
            if not ags.repeat:
                break
            cursplit = 0
    if len(splitsm) == 0:
        print("Error creating splits for length of data")
        sys.exit(5)
    return splitsm

def csv_filter(ags):
    if not ags.extended:
        return None
    extin = [ x for x in list(csv.reader(ags.extended)) if len(x) ]
    if len(extin) != len(bindatlst) + 1:
        print("Extended input file length mismatch")
        sys.exit(6)
    fcount = set([ len(x) for x in extin ])
    if len(fcount) != 1:
        print("Fields missing in extended input")
        sys.exit(7)
    return extin
    
def apply_filter(ags, bindatlst, fltdat):
    if not ags.extended_filter:
        return fltdat, bindatlst
    try:
        valind = fltdat[0].index(ags.extended_filter[0])
    except ValueError:
        print("Filter paramter not listed")
        sys.exit(8)
    newbindatlst = []
    newfltdat = [fltdat[0]] 
    for curline in range(len(bindatlst)):
        if fltdat[curline+1][valind] == ags.extended_filter[1]:
            newbindatlst += [bindatlst[curline]]
            newfltdat += [fltdat[curline+1]]
    if not newbindatlst:
        print("Filter yielded empty list")
        sys.exit(9)
    return newfltdat, newbindatlst

def sort_filter(ags, bindatlst, fltdat):
    if not ags.extended_sort:
        return bindatlst
    try:
        valind = fltdat[0].index(ags.extended_sort)
    except ValueError:
        print("Sort paramter not listed")
        sys.exit(8)
    #print("Sort filter index: " + str(valind) + " - " + fltdat[0][valind])
    #print(fltdat)
    cvals = [ x[valind] for x in fltdat ]
    del cvals[0]
    cvals, newbindatlst = zip(*sorted(zip(cvals, bindatlst)))
    #print(cvals)
    return newbindatlst

if __name__ == '__main__':

    agp = argparse.ArgumentParser()
    agp.add_argument("-f", "--file", help="Input file for binary strings", required=True, type=argparse.FileType('r'))
    agp.add_argument("-d", "--no-align", help="Do not auto align strings", action='store_true')
    agp.add_argument("-p", "--padding", help="Padd with 1 instead of 0", action='store_true')
    agp.add_argument("-s", "--split", help="Comma seperated list of token bit lengths", type=str)
    agp.add_argument("-r", "--repeat", help="Repeat the token sequence given by -s (requires -s)", action='store_true')
    #agp.add_argument("-tm", "--token-match", help="Match all lines that have n in the specified token field (requires -s)", nargs=2, type=str)
    #agp.add_argument("-xl", "--xor-list", help="Comma seperated list of tokens to use in XOR check", type=str)
    #agp.add_argument("-xc", "--xor-check", help="Comma seperated list of tokens to check, followed by a token number for xor field", nargs=2, type=str)
    #agp.add_argument("-xr", "--xor-remove", help="Remove all lines that fail xor check (requires -xc)", action='store_true')
    agp.add_argument("-nc", "--no-color", help="Don't print changing columns in color", action='store_true')
    agp.add_argument("-e", "--extended", help="Path to a CSV file with extended attributes", type=argparse.FileType('r'))
    agp.add_argument("-ef", "--extended-filter", help="Filter lines by field values specified in CSV file (requires -e)", nargs=2, type=str)
    agp.add_argument("-es", "--extended-sort", help="Sort lines by field values specified in CSV file (requires -e)", type=str)
    #agp.add_argument("-ep", "--extended-print", help="For each line print the field value specified in the CSV file (requires -e)", type=str)
    agp_mx1 = agp.add_mutually_exclusive_group()
    agp_mx1.add_argument("-ae", "--add-end", help="Number of padding bits to add to the end of each line", type=int, default=0)
    agp_mx1.add_argument("-re", "--remove-end", help="Number of padding bits to remove from end of each line", type=int, default=0)
    agp_mx2 = agp.add_mutually_exclusive_group()
    agp_mx2.add_argument("-as", "--add-start", help="Number of padding bits to add to the start of each line", type=int, default=0)
    agp_mx2.add_argument("-rs", "--remove-start", help="Number of padding bits to remove from the start of each line", type=int, default=0)
    #agp_mx3 = agp.add_mutually_exclusive_group()
    #agp_mx3.add_argument("-m", "--min-count", help="Highlight rows where the weight for any given changing column is n or less", type=int, default=0)
    #agp_mx3.add_argument("-mr", "--min-remove", help="Remove rows where the weight for any given changing column is n or less", type=int, default=0)
    agp_mx4 = agp.add_mutually_exclusive_group()
    #agp_mx4.add_argument("-ib", "--invert-before", help="Invert all bits before alignment", action='store_true')
    agp_mx4.add_argument("-ia", "--invert-after", help="Invert all bits after alignment", action='store_true')
    
    #name splits and give them different colors
    #verbose output that names all colums
    #complex filters
    #complex token matches
    #token sort
    #blank tokens
    #blank by weight
    #blank character
    #count number of unique entries in tokens
    #count number of unique entires in on extended match
    #display uniqie entries in tokens
    #extended print (including shortcut for all fields)
    #not just for binary
    #character to align on
    #translate to different character sets (removes the need for invert)
    #number of different predefined values for symbol
    
    ags = agp.parse_args()

    validate_params(ags)
    bindatlst = ags.file.read().split()
    bindatlst = align_and_padd(ags, bindatlst)
    splits = format_splits(ags, bindatlst)
    fltdat = csv_filter(ags)
    fltdat, bindatlst = apply_filter(ags, bindatlst, fltdat)
    bindatlst = sort_filter(ags, bindatlst, fltdat)
    #bindatlst = xor_filter(ags, bindatlst)
    colweight = calc_weight(ags, bindatlst)
    #bindatlst = weight_filter(ags, bindatlst)
    colweight = calc_weight(ags, bindatlst)
    print_res(ags, bindatlst, colweight, splits)

# CNUM,GNUM,ENTH,ENTM,PAYH,PAYM
