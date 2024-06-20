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
import pandas as pd

#import serial_connection
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
        self.timeStreamData=[]; self.timeStreamLength=100
        self.updateDB = False
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
        print('value=',value)
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

    def _continuous_stream_timestamps_to_file(self, filename: str, binRay=[], int_time=0):
        """
        Indefinitely streams timestamps to a file
        WARNING: ensure there is sufficient disk space: 32 bits x total events required
        """
        #self.int_time = int_time
        self.mode = "singles"
        level = float(self.level.split()[0])
        level_str = "NEG" if level < 0 else "POS"
        self._com.readlines()  # empties buffer
        # t_acq_for_cmd = t_acq if t_acq < 65 else 0
        cmd_str = "INPKT;{} {};time {};timestamp;counts?;".format(level_str, level, int_time)
        #if integration time is "0", device only needs to be written to once, and will output data every time the buffer fills up,
        #otherwise, TDC must be told to record once every intergration period. There is a non-negligible (0.2s?) dead time in this mode.
        self.lastTriggerGroup=0
        if int_time==0:
            print('test: zero mode successfully called')
            self.startTime=time.time() #"Unix time" in seconds, since the "epoch"
            self._com.write((cmd_str + "\r\n").encode())
            while self.accumulate_timestamps:
                buffer = self._com.read((1 << 20) * 4)
                with open(filename, "ab+") as f:
                    f.write(buffer); f.flush()
                f.close()
                if len(binRay)==3: self.toHist(buffer, int_time=int_time)
        else:
            while self.accumulate_timestamps:
                self.startTime=time.time() #"Unix time" in seconds, since the "epoch". If there's variable dead time between subsequent buffers, then we need to measure TDC times relative to updated start times
                buffer = self._stream_response_into_buffer(cmd_str, float(int_time)/1000)# + 0.1)
                #if buffer==b'': pass
                with open(filename, "ab+") as f:
                    f.write(buffer); f.flush()
                f.close()
                if len(binRay)==3: self.toHist(buffer, int_time=int_time) 

    def toHist(self, buffer, int_time=0):
      #this will be a function to hopefully aid in efficient liveplotting
      if buffer==b'': print('empty buffer');return
      vocalMode=False
      #(reads buffers as they come, and stores binned relative timestamps in a pickeled dictionary which can then be accessed by the live plotter).
      timingRay=[time.time()]
      if vocalMode: print('ayyy')
      timestamps = {"channel 1":[], "channel 2":[], "channel 3":[], "channel 4":[]}
      if int_time==0: #keeping track of remainders is only appropriate if there is no deadtime between the event times recorded in subsequent buffers
        for channel in self.remainder.keys(): timestamps[channel] = self.remainder[channel] #appending events that appeared after final trigger time of previous buffer
      timingRay+=[time.time()]
      times, channels, self.prev_Time, self.pCount = self.read_timestamps_bin_modified(buffer, prev_Time=self.prev_Time, pCount=self.pCount)
      #print("self.prev_Time, self.pCount = ",self.prev_Time, self.pCount)
      timingRay+=[time.time()]
      if vocalMode: print("prev_Time=",self.prev_Time, "pCount=", self.pCount);
      for channel in range(1, 5, 1):  timestamps["channel {}".format(channel)] += list(times[[int(ch, 2) & channel_to_pattern(channel) != 0 for ch in channels]])#this line is the bottle neck!
      #for channel in range(1, 5, 1): timestamps["channel {}".format(channel)] += list(times[channels==tdcu.channel_to_binString(channel)]) #factor of 10 time save B)
      timingRay+=[time.time()]
      self.allTriggers+=timestamps['channel 1']
      timingRay+=[time.time()]
      if len(timestamps['channel 1'])==0 and self.lastTrigger==0: print("wahuh fuk m8? I'm not even triggered m8");return#; print(buffer); return
      elif self.lastTrigger==0: triggers=timestamps['channel 1']
      elif len(timestamps['channel 1'])==0: triggers = [self.lastTrigger] #todo: allow for other channels to be trigger?
      elif timestamps['channel 1'][0]<self.lastTrigger: #this is confusing and obnoxious. For now I'm just going to reset everything whenever this happens. liveplot data will be slightly off, but probably not by much
        print("WHY TF? Are the values wrapping?");
        print("timestamps['channel 1'][0]=",timestamps['channel 1'][0],"self.lastTrigger=",self.lastTrigger)
        self.remainder={"channel 2":[], "channel 3":[], "channel 4":[]}; self.lastTrigger=0
        self.prev_Time = -1; self.pCount = 0
        return
      else: triggers = [self.lastTrigger]+timestamps['channel 1'] #todo: allow for other channels to be trigger?
      if vocalMode: print("Trigger times:", triggers)
      if np.min(triggers)<0: #reset everything. We overflowed or something.
        print("GUH");
        self.remainder={"channel 2":[], "channel 3":[], "channel 4":[]}; self.lastTrigger=0
        self.prev_Time = -1; self.pCount = 0
        return
      timingRay+=[time.time()]
      try:
        #if len (triggers)==0: self.lastTrigger=0
        self.lastTrigger=triggers[-1]
        self.remainder={"channel 2":[], "channel 3":[], "channel 4":[]}
        for channel in self.remainder.keys():
          for j in range(len(timestamps[channel])):
            if timestamps[channel][j]>self.lastTrigger:
              if vocalMode: print("for j = %d and beyond, timestamps will be stored in remainder dictionary"%j)
              self.remainder[channel]=timestamps[channel][j:]
              timestamps[channel]=timestamps[channel][:j]
              if vocalMode: print(timestamps[channel][-10:])
              if vocalMode: print(self.remainder[channel][:10])
              break
      except:
        print("except case reached for some reason")
        for channel in self.remainder.keys():
          self.remainder[channel]+=timestamps[channel]
      timingRay+=[time.time()]
      if len(triggers)>1:
        bufferFrame=pd.DataFrame()
        bufferIntegrationTime=len(triggers)-1 #the number of complete trigger windows included in the current buffer
        self.dicForToF_latest['triggerGroups'] = bufferIntegrationTime
        self.dicForToF_latest['timeStamp'] = time.time()
        print(len(triggers), 'triggers recorded in this buffer')
        for channel in self.remainder.keys():
          eventTimes=timestamps[channel]
          timeStreamData=self.dicForTimeStream[channel]
          if len(eventTimes)>0:
              if vocalMode: print(len(eventTimes), len(self.remainder[channel]))
              print(len(eventTimes), len(self.remainder[channel]))
              
              goodTimeStamps, triggerGroups = tdcu.timeStampConverter(triggers, eventTimes)#, run=-1, t0=0)
              bufferFrame=pd.concat([bufferFrame, pd.DataFrame({'tStamp':goodTimeStamps, 'channel':int(channel.strip('channel '))*np.ones_like(goodTimeStamps,dtype=int),
                                                               'run':self.run*np.ones_like(goodTimeStamps,dtype=int),'triggerGroup':np.array(triggerGroups)+self.lastTriggerGroup, 'globalTime':self.startTime+(np.array(eventTimes)*1E-9)})])
              self.lastTriggerGroup+=len(triggers)#TODO: Test empirically, to make sure this makes sense. want to increment tGroup offset after every buffer so that they always grow by an increment of 1
          else: goodTimeStamps=[]
          binIncrements, bins = np.histogram(goodTimeStamps, bins=self.histogramBins)
          totalCountsInWindow=np.sum(binIncrements); #print('totalCountsInWindow=',totalCountsInWindow)           
          countRate=totalCountsInWindow/bufferIntegrationTime; #print('count rate over current buffer = ',countRate)
          '''self.timeStreamData+=[countRate]
                                              while len(self.timeStreamData)>self.timeStreamLength: #should only ever pop one element per function call
                                                  del self.timeStreamData[0]'''
          timeStreamData+=[countRate]
          while len(timeStreamData)>self.timeStreamLength: del timeStreamData[0]#should only ever pop one element per function call
          self.dicForTimeStream[channel]=timeStreamData
          self.dicForToF_total[channel] += binIncrements
          self.dicForToF_latest[channel] = binIncrements
        with open(self.liveToFs_totals_File,'wb') as file: pickle.dump(self.dicForToF_total, file); file.close()
        with open(self.liveTimeStreamFile,'wb') as file: pickle.dump(self.dicForTimeStream, file); file.close()
        with open(self.liveToFs_latest_File,'wb') as file: pickle.dump(self.dicForToF_latest, file); file.close()
        self.cleanDB = sl.connect(self.cleanDBname)
        bufferFrame.to_sql('TDC', self.cleanDB, if_exists='append')
        #print(len(goodTimeStamps), 'event timestamps recorded in this buffer')
        print("We really out here", time.time())

      timingRay+=[time.time()]#t3=time.time();
      for i in range(len(timingRay)-1): pass#print('t%d - t%d = '%(i+1,i), timingRay[i+1]-timingRay[i])
      #print('in total, this function took',timingRay[-1]-timingRay[0],'s to run. On a separate note: self.lastTrigger=', self.lastTrigger)


    def start_continuous_stream_timestamps_to_file(self, filename: str, cleanDBname: str, run:int, binRay=[0,1E9,1E3], 
        totalToFs_targetFile="liveToFs_totals_File.pkl", latestToFs_targetFile="liveToFs_latest_File.pkl",
         timeStreamFile='timeStreamLiveData.pkl', tStreamLength=100, int_time=0):
        #Starts the timestamp streaming service to file in the brackground
        self.accumulated_timestamps_filename = filename
        self.cleanDBname = cleanDBname
        print('test:', self.cleanDBname)
        
        #with self.cleanDB: self.cleanDB.execute("""CREATE TABLE IF NOT EXISTS TDC""")
        self.run=run
        if len(binRay)==3:
            self.liveToFs_totals_File = totalToFs_targetFile
            self.liveToFs_latest_File = latestToFs_targetFile
            try: os.remove(self.liveToFs_totals_File); os.remove(self.liveToFs_latest_File)
            except: pass
            self.histogramBins=np.linspace(binRay[0], binRay[1], binRay[2]+1)
            self.dicForToF_total={"channel 2":np.zeros(binRay[2]), "channel 3":np.zeros(binRay[2]), "channel 4":np.zeros(binRay[2])}
            self.dicForToF_latest = {"channel 2":np.zeros(binRay[2]), "channel 3":np.zeros(binRay[2]), "channel 4":np.zeros(binRay[2]), 'triggerGroups':-1, 'timeStamp':time.time()}
            with open(self.liveToFs_totals_File,'wb') as file: pickle.dump(self.dicForToF_total, file); file.close()
        self.timeStreamData=[]
        self.timeStreamLength=tStreamLength
        self.liveTimeStreamFile = timeStreamFile;
        self.dicForTimeStream={"channel 2":tStreamLength*[0], "channel 3":tStreamLength*[0], "channel 4":tStreamLength*[0]}

        try: os.remove(self.liveTimeStreamFile)
        except: pass
        with open(self.liveTimeStreamFile,'wb') as file: pickle.dump(self.dicForTimeStream, file); file.close()
        if os.path.exists(self.accumulated_timestamps_filename):
            os.remove(
                self.accumulated_timestamps_filename
            )  # remove previous accumulation file for a fresh start
        else:
            pass
        self.accumulate_timestamps = True
        self.proc = threading.Thread(
            target=self._continuous_stream_timestamps_to_file,
            args=(self.accumulated_timestamps_filename, binRay, int_time),
        )
        self.proc.daemon = True  # Daemonize thread
        self.proc.start()  # Start the execution

    def stop_continuous_stream_timestamps_to_file(self):
        """
        Stops the timestamp streaming service to file in the brackground
        """
        self.accumulate_timestamps = False
        time.sleep(0.5)
        self.proc.join()
        self._com.write(b"abort\r\n")
        self._com.readlines()
        if self.updateDB: self.writeToDBs()

    def writeToDBs(self):
        self.cleanDB = sl.connect(self.cleanDBname)
        timeStampsDic=self.read_timestamps_from_file_as_dict(self.accumulated_timestamps_filename)
        for i in range(1,5):
            print("channel%d had %d timestamps"%(i, len(timeStampsDic['channel '+str(i)])) )
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

        ts_list2 = np.array(ts_list, dtype='int64') * 2
        event_channel_list = np.array(event_channel_list)
        return ts_list2, event_channel_list

    def tStampFixer(self, timeStamps, prev_Time=-1, pCount=0):
      periode_count = pCount
      periode_duration = 1<<27
      prev_ts = prev_Time
      timeStamps+=pCount*periode_duration #see shrugging comment in generateTimeAndChannelLists
      for i in range(len(timeStamps)):
        if prev_ts != -1 and timeStamps[i] < prev_ts:
          periode_count += 1
          #print(periode_count)
          timeStamps[i:]+=periode_duration
        prev_ts = timeStamps[i]
      return(np.array(timeStamps, dtype='int64'), prev_ts, periode_count)

    def generateTimeAndChannelLists(self, ts_word_list, prev_Time=-1, pCount=0):
      periode_duration = 1<<27
      time_stamp_list = ts_word_list >> 5# + pCount*periode_duration #it doesn't work here??? put it at beginning of tStampFixer, and now it behaves properly ¯\_(ツ)_/¯
      fixed_tStamps, prev_ts, periode_count=self.tStampFixer(time_stamp_list, prev_Time=prev_Time, pCount=pCount)
      pattern_list = np.array(ts_word_list & 0x1F); maskArray = pattern_list & 0x10 == 0
      ts_list2 = 2*time_stamp_list[maskArray]
      pattern_list=pattern_list[pattern_list & 0x10 == 0]
    
      event_channel_list=np.array(len(pattern_list)*['0001'])
      event_channel_list[pattern_list==1]="{0:04b}".format(1)
      event_channel_list[pattern_list==2]="{0:04b}".format(2)
      event_channel_list[pattern_list==3]="{0:04b}".format(3)
      event_channel_list[pattern_list==4]="{0:04b}".format(4)
    
      return ts_list2, event_channel_list, prev_ts, periode_count

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
            timingRay=[time.time()]
            bytes_hex = binary_stream[::-1].hex()
            ts_word_list = np.array([
                int(bytes_hex[i : i + 8], 16) for i in range(0, len(bytes_hex), 8)
            ][::-1], dtype='int64')
            timingRay+=[time.time()]
            #print('prev_Time, pCount:', prev_Time, pCount)
            ts_list2, event_channel_list, prev_ts, periode_count = self.generateTimeAndChannelLists(ts_word_list, prev_Time=prev_Time, pCount=pCount)
    
            timingRay+=[time.time()];
            #for i in range(len(timingRay)-1): print('T%d - T%d = '%(i+1,i), timingRay[i+1]-timingRay[i])
            #print('prev_ts, periode_count:', prev_ts, periode_count)
            return ts_list2, event_channel_list, prev_ts, periode_count #returning these as well so I can keep track of and iterate them when I want to

    def read_timestamps_from_file(self, fname=None):
        #Reads the timestamps accumulated in a binary file
        if fname==None: fname=self.accumulated_timestamps_filename
        with open(fname, "rb") as f: lines = f.read()
        f.close()      
        return(self.read_timestamps_bin(lines))

    def read_timestamps_from_file_as_dict(self,fname=None):
        #Returns dictionary where timestamps['channel i'] is the timestamp array in nsec for the ith channel
        if fname==None: fname=self.accumulated_timestamps_filename
        timestamps = {}
        (
            times,
            channels,
        ) = (
            self.read_timestamps_from_file(fname=fname)
        )  # channels may involve coincidence signatures such as '0101'
        '''for channel in range(1, 5, 1):  # iterate through channel numbers 1, 2, 3, 4
            timestamps["channel {}".format(channel)] = times[
                [int(ch, 2) & channel_to_pattern(channel) != 0 for ch in channels]
            ]'''
        for channel in range(1, 5, 1): timestamps["channel {}".format(channel)] = list(times[channels==tdcu.channel_to_binString(channel)])
        return timestamps

    def real_time_processing(self):
        """
        Real-time processes the timestamps that are saved in the background.
        Grabs a number of lines of timestamps to process (defined as a section):
        since reading from a file is time-consuming, we grab a couple at a go.
        """
        raise NotImplementedError()
