import os
import wave
import array
import argparse
import numpy
import pywt
from scipy import signal
import taglib


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
    print "No audio data for sample, skipping..."
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process .wav file to determine the Beats Per Minute.')
    parser.add_argument('--filename', required=True,
                        help='.wav file for processing')
    parser.add_argument('--round', type=int, default=0,
                        help='Digits after the decimal point')
    parser.add_argument('--rename', type=bool, default=False,
                        help='Set true if want rename file')
    parser.add_argument('--tag', type=bool, default=False,
                        help='Set true if want tag bpm in file')
    parser.add_argument('--window', type=float, default=3,
                        help='size of the the window (seconds) that will be scanned to determine the bpm.  Typically less than 10 seconds. [3]')

    args = parser.parse_args()
    samps, fs = read_wav(args.filename)

    data = []
    correl = []
    bpm = 0
    n = 0
    nsamps = len(samps)
    window_samps = int(args.window*fs)
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
    bpm = round(bpm, args.round)

    if args.round == 0:
        bpm = int(bpm)
    print 'Completed.  Estimated Beats Per Minute:', bpm
    if args.rename:
        filename_array = args.filename.split('.wav')
        new_filename = filename_array[0]+' ('+str(bpm)+') .wav'
        os.rename(args.filename, new_filename)
    if args.tag:
        song = taglib.File(args.filename)
        song.tags["BPM"] = [str(bpm)]
        song.save()
