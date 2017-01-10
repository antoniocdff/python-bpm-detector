import os
import wave
import array
import argparse
import numpy
import pywt
from scipy import signal
import taglib


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def read_wav(filename):

    try:
        wf = wave.open(filename, 'rb')
    except IOError, e:
        print e
        return

    nsamps = wf.getnframes()
    assert(nsamps > 0)

    fs = wf.getframerate()
    assert(fs > 0)

    samps = list(array.array('i', wf.readframes(nsamps)))

    try:
        assert(nsamps == len(samps))
    except AssertionError, e:
        print nsamps, "not equal to", len(samps)

    return samps, fs


def no_audio_data():
    print bcolors.WARNING + "No audio data for sample, skipping..." + bcolors.ENDC
    return None, None


def peak_detect(data):
    max_val = numpy.amax(abs(data))
    peak_ndx = numpy.where(data == max_val)
    if len(peak_ndx[0]) == 0:
        peak_ndx = numpy.where(data == -max_val)
    return peak_ndx


def bpm_detector(data, fs):
    cA = []
    cD = []
    correl = []
    cD_sum = []
    levels = 4
    max_decimation = 2**(levels-1)
    min_ndx = 60. / 220 * (fs/max_decimation)
    max_ndx = 60. / 40 * (fs/max_decimation)

    for loop in range(0, levels):
        cD = []
        if loop == 0:
            [cA, cD] = pywt.dwt(data, 'db4')
            cD_minlen = len(cD)/max_decimation+1
            cD_sum = numpy.zeros(cD_minlen)
        else:
            [cA, cD] = pywt.dwt(cA, 'db4')
        cD = signal.lfilter([0.01], [1 - 0.99], cD)
        cD = abs(cD[::(2**(levels-loop-1))])
        cD = cD - numpy.mean(cD)
        cD_sum = cD[0:cD_minlen] + cD_sum

    if [b for b in cA if b != 0.0] == []:
        return no_audio_data()

    cA = signal.lfilter([0.01], [1 - 0.99], cA)
    cA = abs(cA)
    cA = cA - numpy.mean(cA)
    cD_sum = cA[0:cD_minlen] + cD_sum

    correl = numpy.correlate(cD_sum, cD_sum, 'full')

    midpoint = len(correl) / 2
    correl_midpoint_tmp = correl[midpoint:]
    peak_ndx = peak_detect(correl_midpoint_tmp[min_ndx:max_ndx])
    if len(peak_ndx) > 1:
        return no_audio_data()

    peak_ndx_adjusted = peak_ndx[0]+min_ndx
    bpm = 60. / peak_ndx_adjusted * (fs/max_decimation)
    return bpm, correl


def execute(afilename, awindow, around, arename, atag):
    try:
        samps, fs = read_wav(afilename)
    except:
        print bcolors.FAIL + '[Error] ' + file + bcolors.ENDC

    data = []
    correl = []
    bpm = 0
    n = 0
    nsamps = len(samps)
    window_samps = int(awindow*fs)
    samps_ndx = 0
    max_window_ndx = nsamps / window_samps
    bpms = numpy.zeros(max_window_ndx)

    for window_ndx in xrange(0, max_window_ndx):
        data = samps[samps_ndx:samps_ndx+window_samps]
        if not ((len(data) % window_samps) == 0):
            raise AssertionError(str(len(data)))

        bpm, correl_temp = bpm_detector(data, fs)
        if not bpm:
            continue
        bpms[window_ndx] = bpm
        correl = correl_temp

        samps_ndx = samps_ndx+window_samps
        n = n+1

    bpm = numpy.median(bpms)
    bpm = round(bpm, around)

    if around == 0:
        bpm = int(bpm)
    if bpm > 0:
        print bcolors.OKBLUE + '[Detected]' + str(afilename) + ': ' + bcolors.ENDC + bcolors.OKGREEN + str(bpm) + bcolors.ENDC
    if atag:
        try:
            song = taglib.File(afilename)
            song.tags["BPM"] = [str(bpm)]
            song.save()
            print bcolors.OKBLUE + '[Tagged]' + str(afilename) + bcolors.ENDC
        except OSError, e:
            print bcolors.WARNING + '[Error tagg]' + str(afilename) + bcolors.ENDC
    if arename:
        filename_array = afilename.split('.wav')
        new_filename = filename_array[0]+' ('+str(bpm)+') .wav'
        try:
            os.rename(afilename, new_filename)
            print bcolors.OKBLUE + '[Renamed]' + str(afilename) + bcolors.ENDC
        except:
            print bcolors.WARNING + '[Error rename]' + str(afilename) + bcolors.ENDC


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process .wav file to determine the Beats Per Minute.')
    parser.add_argument('--filename', required=False,
                        help='.wav file for processing')
    parser.add_argument('--folder', required=False,
                        help='folder with .wav files for processing')
    parser.add_argument('--round', type=int, default=0,
                        help='Digits after the decimal point')
    parser.add_argument('--rename', type=bool, default=False,
                        help='Set true if want rename file')
    parser.add_argument('--tag', type=bool, default=False,
                        help='Set true if want tag bpm in file')
    parser.add_argument('--window', type=float, default=3,
                        help='size of the the window (seconds) that will be scanned to determine the bpm.  Typically less than 10 seconds. [3]')

    args = parser.parse_args()

    if args.folder:
        mypath = args.folder
        f = []
        for (dirpath, dirnames, filenames) in os.walk(mypath):
            f.extend(filenames)
            break
        for file in f:
            filearray = file.split('.wav')
            if len(filearray) > 1:
                execute(args.folder+'/'+file, args.window, args.round, args.rename, args.tag)
    elif args.filename:
        execute(args.file, args.window, args.round, args.rename, args.tag)
    else:
        print bcolors.WARNING + 'You must set filename or folder params' + bcolors.ENDC
