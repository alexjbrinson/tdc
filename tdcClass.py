#!/usr/bin/env python3

"""
USB mini counter based on FPGA

Collection of functions to simplify the integration of the USB counter in
Python scripts.
"""

import os
import time
from os.path import expanduser
from typing import Optional, Tuple
import TDCutilities as tdcu
import numpy as np
import serial
import serial.tools.list_ports

import serial_connection
import threading
import sqlite3 as sl
import pickle
import matplotlib.pyplot as plt

READEVENTS_PROG = expanduser("~") + "/programs/usbcntfpga/apps/readevents4a"
TTL = "TTL"
NIM = "NIM"


def pattern_to_channel(pattern):
    if pattern == 4:
        return 3
    elif pattern == 8:
        return 4
    elif pattern == 1 or pattern == 2 or pattern == 0:
        return pattern


def channel_to_pattern(channel):
    return int(2 ** (channel - 1))

class TimeStampTDC1(object):
    """
    The usb counter is seen as an object through this class,
    inherited from the generic serial one.
    """

    DEVICE_IDENTIFIER = "TDC1"
    TTL_LEVELS = "TTL"
    NIM_LEVELS = "NIM"

    def __init__(
        self, device_path=None, integration_time=1, mode="singles", level="NIM"
    ):
        """
        Function to initialize the counter device.
        It requires the full path to the serial device as arguments,
        otherwise it will
        initialize the first counter found in the system
        """
        if device_path is None:
            device_path = (
                serial_connection.search_for_serial_devices(self.DEVICE_IDENTIFIER)
            )[0]
            print("Connected to", device_path)
        self._device_path = device_path
        # self._com = serial_connection.SerialConnection(device_path)
        self._com = serial.Serial(device_path, timeout=0.1)
        self._com.write(b"\r\n")
        self._com.readlines()
        self.mode = mode
        self.level = level
        self.int_time = integration_time
        self.accumulate_timestamps = False  # flag for timestamp accumulation service
        self.accumulated_timestamps_filename = (
            "timestamps.raw"  # binary file where timestamps are stored
        )
        self.remainder={"channel 2":[], "channel 3":[], "channel 4":[]}
        self.lastTrigger=0
        self.allTriggers=[]
        self.prev_Time=-1; self.pCount=0
        time.sleep(0.2)

    @property
    def int_time(self):
        """
        Controls the integration time set in the counter

        :getter: returns integration time in seconds
        :setter: Set integration
        :param value: integration time in seconds
        :type value: int
        :returns: integration time in seconds
        :rtype: int
        """
        self._com.write(b"time?\r\n")
        return int(self._com.readline())

    @int_time.setter
    def int_time(self, value: float):
        value *= 1000
        if value < 1:
            print("Invalid integration time.")
        else:
            self._com.write("time {:d};".format(int(value)).encode())
            self._com.readlines()

    def get_counts(self, duration_seconds: Optional[int] = None) -> Tuple:
        """[summary]

        Args:
            duration_seconds (int, optional): [description]. Defaults to None.

        Returns:
            List: [description]
        """
        self._com.timeout = 0.05
        if duration_seconds is None:
            duration_seconds = self.int_time
        else:
            self.int_time = duration_seconds
        self._com.timeout = duration_seconds

        self._com.write(b"singles;counts?\r\n")

        t_start = time.time()
        while True:
            if self._com.inWaiting() > 0:
                break
            if time.time() > (t_start + duration_seconds + 0.1):
                print(time.time() - t_start)
                raise serial.SerialTimeoutException("Command timeout")

        counts = self._com.readline()
        self._com.timeout = 0.05
        return tuple([int(i) for i in counts.split()])

    @property
    def mode(self):
        # mode = int(self._com.getresponse('MODE?'))
        self._com.write(b"mode?\r\n")
        mode = int(self._com.readline())
        if mode == 0:
            return "singles"
        if mode == 1:
            return "pairs"
        if mode == 3:
            return "timestamp"

    @mode.setter
    def mode(self, value):
        if value.lower() == "singles":
            self.write_only("singles")
        if value.lower() == "pairs":
            self.write_only("pairs")
        if value.lower() == "timestamp":
            self.write_only("timestamp")

    def write_only(self, cmd):
        self._com.write((cmd + "\r\n").encode())
        self._com.readlines()
        time.sleep(0.1)

    @property
    def level(self):
        """Set type of incoming pulses"""
        self._com.write(b"level?\r\n")
        return self._com.readline()
        # return self._com.getresponse('LEVEL?')

    @level.setter
    def level(self, value: str):
        if value.lower() == "nim":
            self.write_only("NIM")
        elif value.lower() == "ttl":
            self.write_only("TTL")
        else:
            print("Accepted input is a string and either 'TTL' or 'NIM'")
        # time.sleep(0.1)

    @property
    def threshold(self):
        """Returns the threshold level"""
        return self.level

    @threshold.setter
    def threshold(self, value: float):
        """Sets the the threshold the input pulse needs to exceed to trigger an event.

        Args:
            value (float): threshold value in volts can be negative or positive
        """
        if value < 0:
            self.write_only("NEG {}".format(value))
        else:
            self.write_only("POS {}".format(value))

    @property
    def clock(self) -> str:
        """Choice of clock"""
        self._com.write("REFCLK?\r\n".encode())
        return self._com.readline()

    @clock.setter
    def clock(self, value: str):
        """Set the clock source internel or external

        Args:
            value (str): 0 autoselect clock, 1 force external clock,
                         2 force internal clock reference
        """
        self.write_only("REFCLK {}".format(value))

    @property
    def eclock(self) -> str:
        """Check external clock availability."""
        self._com.write("ECLOCK?\r\n".encode())
        return self._com.readline()

    def _stream_response_into_buffer(self, cmd: str, acq_time: float) -> bytes:
        """Streams data from the timestamp unit into a buffer.

        Args:
            cmd (str): Executes the given command to start the stream.
            acq_time (float): Reads data for acq_time seconds.

        Returns:
            bytes: Returns the raw data.
        """
        # this function bypass the termination character
        # (since there is none for timestamp mode),
        # streams data from device for the integration time.

        # Stream data for acq_time seconds into a buffer
        ts_list = []
        time0 = time.time()
        self._com.write((cmd + "\r\n").encode())
        while (time.time() - time0) <= acq_time + 0.01:
            ts_list.append(self._com.read((1 << 20) * 4))
        # self._com.write(b"abort\r\n")
        self._com.readlines()
        return b"".join(ts_list)

    def get_counts_and_coincidences(self, t_acq: float = 1) -> Tuple[int, ...]:
        """Counts single events and coinciding events in channel pairs.

        Args:
            t_acq (float, optional): Time duration to count events in seperated
                channels and coinciding events in 2 channels. Defaults to 1.

        Returns:
            Tuple[int, int , int, int, int, int, int, int]: Events ch1, ch2, ch3, ch4;
                Coincidences: ch1-ch3, ch1-ch4, ch2-ch3, ch2-ch4
        """
        self._com.timeout = 0.05
        if t_acq is None:
            t_acq = self.int_time
        else:
            self.int_time = t_acq
        self._com.timeout = t_acq

        self._com.write(b"pairs;counts?\r\n")
        t_start = time.time()
        while True:
            if self._com.inWaiting() > 0:
                break
            if time.time() > (t_start + t_acq + 0.1):
                print(time.time() - t_start)
                raise serial.SerialTimeoutException("Command timeout")
        singlesAndPairs = self._com.readline()
        self._com.timeout = 0.05
        return tuple([int(i) for i in singlesAndPairs.split()])

    def get_timestamps(self, t_acq: float = 1):
        """Acquires timestamps and returns 2 lists. The first one containing
        the time and the second the event channel.

        Args:
            t_acq (float, optional):
                Duration of the the timestamp acquisition in seconds. Defaults to 1.

        Returns:
            Tuple[List[int], List[str]]:
                Returns the event times in ns and the corresponding event channel.
                The channel are returned as string where a 1 indicates the
                trigger channel.
                For example an event in channel 2 would correspond to "0010".
                Two coinciding events in channel 3 and 4 correspond to "1100"
        """
        self.mode = "singles"
        level = float(self.level.split()[0])
        level_str = "NEG" if level < 0 else "POS"
        self._com.readlines()  # empties buffer
        # t_acq_for_cmd = t_acq if t_acq < 65 else 0
        cmd_str = "INPKT;{} {};time {};timestamp;counts?;".format(
            level_str, level, (t_acq if t_acq < 65 else 0) * 1000
        )
        buffer = self._stream_response_into_buffer(cmd_str, t_acq + 0.1)
        # '*RST;INPKT;'+level+';time '+str(t_acq * 1000)+';timestamp;counts?',t_acq+0.1) # noqa

        # buffer contains the timestamp information in binary.
        # Now convert them into time and identify the event channel.
        # Each timestamp is 32 bits long.
        bytes_hex = buffer[::-1].hex()
        ts_word_list = [
            int(bytes_hex[i : i + 8], 16) for i in range(0, len(bytes_hex), 8)
        ][::-1]

        ts_list = []
        event_channel_list = []
        periode_count = 0
        periode_duration = 1 << 27
        prev_ts = -1
        for ts_word in ts_word_list:
            time_stamp = ts_word >> 5
            pattern = ts_word & 0x1F
            if prev_ts != -1 and time_stamp < prev_ts:
                periode_count += 1
                # print(periode_count)
            prev_ts = time_stamp
            if (pattern & 0x10) == 0:
                ts_list.append(time_stamp + periode_duration * periode_count)
                event_channel_list.append("{0:04b}".format(pattern & 0xF))

        ts_list = np.array(ts_list) * 2
        event_channel_list = event_channel_list

        return ts_list, event_channel_list

    def help(self):
        """
        Prints device help text
        """
        self._com.write(b"help\r\n")
        [print(k) for k in self._com.readlines()]

    def _continuous_stream_timestamps_to_file(self, filename: str, binRay=[]):
        """
        Indefinitely streams timestamps to a file
        WARNING: ensure there is sufficient disk space: 32 bits x total events required
        """
        self.mode = "singles"
        level = float(self.level.split()[0])
        level_str = "NEG" if level < 0 else "POS"
        self._com.readlines()  # empties buffer
        # t_acq_for_cmd = t_acq if t_acq < 65 else 0
        cmd_str = "INPKT;{} {};time {};timestamp;counts?;".format(level_str, level, 0)
        self._com.write((cmd_str + "\r\n").encode())
        while self.accumulate_timestamps:
            buffer = self._com.read((1 << 20) * 4)
            with open(filename, "ab+") as f:
                f.write(buffer); f.flush()
            f.close()
            if len(binRay)==3: self.toHist(buffer) #this will be a function to hopefully aid in efficient liveplotting

    def toHist(self, buffer):
      #(reads buffers as they come, and stores binned relative timestamps in a pickeled dictionary which can then be accessed by the live plotter).
      t0=time.time()
      print('ayyy')
      timestamps = {"channel 1":[], "channel 2":[], "channel 3":[], "channel 4":[]}
      for channel in self.remainder.keys():
          timestamps[channel] = self.remainder[channel] #appending events that appeared after final trigger time of previous buffer

      times, channels, self.prev_Time, self.pCount = self.read_timestamps_bin_modified(buffer, prev_Time=self.prev_Time, pCount=self.pCount)
      print("prev_Time=",self.prev_Time, "pCount=", self.pCount)
      for channel in range(1, 5, 1):  timestamps["channel {}".format(channel)] += list(times[[int(ch, 2) & channel_to_pattern(channel) != 0 for ch in channels]])
      for channel in range(1, 3, 1): print("channel %d read in %d timestamps this buffer cycle."%(channel, len(times[[int(ch, 2) & channel_to_pattern(channel) != 0 for ch in channels]])))
      self.allTriggers+=timestamps['channel 1']
      if len(timestamps['channel 1'])==0 and self.lastTrigger==0: print('wahuh fuk m8?'); return
      elif self.lastTrigger==0: triggers=timestamps['channel 1']
      elif len(timestamps['channel 1'])==0: triggers = [self.lastTrigger] #todo: allow for other channels to be trigger?
      elif timestamps['channel 1'][0]<self.lastTrigger: #this is confusing and obnoxious. For now I'm just going to reset everything whenever this happens. liveplot data will be slightly off, but probably not by much
        print("WHY TF? Are the values wrapping?");
        self.remainder={"channel 2":[], "channel 3":[], "channel 4":[]}; self.lastTrigger=0
        self.prev_Time = -1; self.pCount = 0
        return
      else: triggers = [self.lastTrigger]+timestamps['channel 1'] #todo: allow for other channels to be trigger?
      print("Trigger times:", triggers)
      if np.min(triggers)<0: #reset everything. We overflowed or something.
        print("GUH");
        self.remainder={"channel 2":[], "channel 3":[], "channel 4":[]}; self.lastTrigger=0
        self.prev_Time = -1; self.pCount = 0
        return
      try:
        #if len (triggers)==0: self.lastTrigger=0
        self.lastTrigger=triggers[-1]
        self.remainder={"channel 2":[], "channel 3":[], "channel 4":[]}
        for channel in self.remainder.keys():
          for j in range(len(timestamps[channel])):
            if timestamps[channel][j]>self.lastTrigger:
              print("for j = %d and beyond, timestamps will be stored in remainder dictionary"%j)
              self.remainder[channel]=timestamps[channel][j:]
              timestamps[channel]=timestamps[channel][:j]
              print(timestamps[channel][-10:])
              print(self.remainder[channel][:10])
              break
      except:
        print("except case reached for some reason")
        for channel in self.remainder.keys():
          self.remainder[channel]+=timestamps[channel]
      for channel in self.remainder.keys():
        eventTimes=timestamps[channel]
        if len(eventTimes)>0 and len(triggers)>0:
            print(len(eventTimes), len(self.remainder[channel]))
            goodTimeStamps, triggerGroups = tdcu.timeStampConverter(triggers, eventTimes)#, run=-1, t0=0)
            binIncrements, bins = np.histogram(goodTimeStamps, bins=self.histogramBins)
            print("len(binIncrements)=",len(binIncrements))
            self.dicForBinning[channel] += binIncrements
            #print("pls work:",self.dicForBinning[channel])
      with open(self.liveDataFile,'wb') as file:
        pickle.dump(self.dicForBinning, file)
        #goodTimestamps = dFrame["channel"==channel.strip("channel ")].tStamp
        #print(np.histogram(goodTimestamps, self.histogramBins))'''

      t1=time.time()
      print("this shit currently takes", t1-t0, "seconds per buffer")


    def start_continuous_stream_timestamps_to_file(self, filename: str, cleanDBname: str, run:int, binRay=[], pickleDic="iTurnedMyselfIntoAPickle.pkl"):
        """
        Starts the timestamp streaming service to file in the brackground
        """
        self.accumulated_timestamps_filename = filename
        self.cleanDBname = cleanDBname
        self.run=run
        if len(binRay)==3:
            self.liveDataFile = pickleDic
            self.histogramBins=np.linspace(binRay[0], binRay[1], binRay[2]+1)
            self.dicForBinning={"channel 2":np.zeros(binRay[2]), "channel 3":np.zeros(binRay[2]), "channel 4":np.zeros(binRay[2])}

        if os.path.exists(self.accumulated_timestamps_filename):
            os.remove(
                self.accumulated_timestamps_filename
            )  # remove previous accumulation file for a fresh start
        else:
            pass
        self.accumulate_timestamps = True
        self.proc = threading.Thread(
            target=self._continuous_stream_timestamps_to_file,
            args=(self.accumulated_timestamps_filename, binRay),
        )
        self.proc.daemon = True  # Daemonize thread
        self.startTime=time.time() #"Unix time" in seconds, since the "epoch"
        self.proc.start()  # Start the execution

    def stop_continuous_stream_timestamps_to_file(self):
        """
        Stops the timestamp streaming service to file in the brackground
        """
        self.accumulate_timestamps = False
        #self.proc.terminate()
        time.sleep(0.5)
        self.proc.join()
        self._com.write(b"abort\r\n")
        self._com.readlines()
        self.writeToDBs()


    def writeToDBs(self):
        '''self.rawDB = sl.connect(self.rawDBname)
        with self.rawDB:
            self.rawDB.execute("""
            CREATE TABLE IF NOT EXISTS rawTDC (
                tStamp INTEGER NOT NULL PRIMARY KEY,
                channel INTEGER,
                run INTEGER);""")
        
        rawFrame=pd.DataFrame()#TODO'''
        self.cleanDB = sl.connect(self.cleanDBname)
        timeStampsDic=self.read_timestamps_from_file_as_dict(self.accumulated_timestamps_filename)
        #print("wahatae", timeStampsDic)
        
        cleanFrame=tdcu.readAndParseScan(timeStampsDic, dropEnd=True, triggerChannel=1, run=self.run, t0=self.startTime)
        cleanFrame.to_sql('TDC', self.cleanDB, if_exists='append')
        
        
    def read_timestamps_bin(self, binary_stream):
        """
        Reads the timestamps accumulated in a binary sequence
        Returns:
            Tuple[List[float], List[str]]:
                Returns the event times in ns and the corresponding event channel.
                The channel are returned as string where a 1 indicates the
                trigger channel.
                For example an event in channel 2 would correspond to "0010".
                Two coinciding events in channel 3 and 4 correspond to "1100"
        """
        bytes_hex = binary_stream[::-1].hex()
        ts_word_list = [
            int(bytes_hex[i : i + 8], 16) for i in range(0, len(bytes_hex), 8)
        ][::-1]

        ts_list = []
        event_channel_list = []
        periode_count = 0
        periode_duration = 1 << 27
        prev_ts = -1
        for ts_word in ts_word_list:
            time_stamp = ts_word >> 5
            pattern = ts_word & 0x1F
            if prev_ts != -1 and time_stamp < prev_ts:
                periode_count += 1
            #         print(periode_count)
            prev_ts = time_stamp
            if (pattern & 0x10) == 0:
                ts_list.append(time_stamp + periode_duration * periode_count)
                event_channel_list.append("{0:04b}".format(pattern & 0xF))

        ts_list = np.array(ts_list) * 2
        event_channel_list = event_channel_list
        return ts_list, event_channel_list #returning these as well so I can keep track of and iterate them when I want to

    def read_timestamps_bin_modified(self, binary_stream, prev_Time=-1, pCount=0):
        """
        Reads the timestamps accumulated in a binary sequence
        Returns:
            Tuple[List[float], List[str]]:
                Returns the event times in ns and the corresponding event channel.
                The channel are returned as string where a 1 indicates the
                trigger channel.
                For example an event in channel 2 would correspond to "0010".
                Two coinciding events in channel 3 and 4 correspond to "1100"
        """
        bytes_hex = binary_stream[::-1].hex()
        ts_word_list = [
            int(bytes_hex[i : i + 8], 16) for i in range(0, len(bytes_hex), 8)
        ][::-1]

        ts_list = []
        event_channel_list = []
        periode_count = pCount
        periode_duration = 1 << 27
        prev_ts = prev_Time
        for ts_word in ts_word_list:
            time_stamp = ts_word >> 5
            pattern = ts_word & 0x1F
            if prev_ts != -1 and time_stamp < prev_ts:
                periode_count += 1
            #         print(periode_count)
            prev_ts = time_stamp
            if (pattern & 0x10) == 0:
                ts_list.append(time_stamp + periode_duration * periode_count)
                event_channel_list.append("{0:04b}".format(pattern & 0xF))

        ts_list = np.array(ts_list) * 2
        event_channel_list = event_channel_list
        return ts_list, event_channel_list, prev_ts, periode_count #returning these as well so I can keep track of and iterate them when I want to

    def read_timestamps_from_file(self, fname=None):
        """
        Reads the timestamps accumulated in a binary file
        """
        if fname==None: fname=self.accumulated_timestamps_filename
        with open(fname, "rb") as f:
            lines = f.read()
        f.close()
        
        return(self.read_timestamps_bin(lines))

    def read_timestamps_from_file_as_dict(self,fname=None):
        """
        Reads the timestamps accumulated in a binary file
        Returns dictionary where timestamps['channel i'] is the timestamp array
        in nsec for the ith channel
        """
        if fname==None: fname=self.accumulated_timestamps_filename
        timestamps = {}
        (
            times,
            channels,
        ) = (
            self.read_timestamps_from_file(fname=fname)
        )  # channels may involve coincidence signatures such as '0101'
        for channel in range(1, 5, 1):  # iterate through channel numbers 1, 2, 3, 4
            timestamps["channel {}".format(channel)] = times[
                [int(ch, 2) & channel_to_pattern(channel) != 0 for ch in channels]
            ]
        return timestamps

    def real_time_processing(self):
        """
        Real-time processes the timestamps that are saved in the background.
        Grabs a number of lines of timestamps to process (defined as a section):
        since reading from a file is time-consuming, we grab a couple at a go.
        """
        raise NotImplementedError()
