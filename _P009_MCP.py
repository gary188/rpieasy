#!/usr/bin/env python3
#############################################################################
################ MCP23017 port extender plugin for RPIEasy ##################
#############################################################################
#
#
# Available commands:
#  MCPGPIO,<pin>,<state>		 - digital GPIO output, state can be: 0/1
#  MCPPULSE,<pin>,<state>,<duration>	 - state can be 0/1, set gpio to <state> then after <duration> milliseconds reverses it's state
#
# Copyright (C) 2018-2019 by Alexander Nagy - https://bitekmindenhol.blog.hu/
#
import plugin
import webserver
import rpieGlobals
import rpieTime
import misc
import gpios
import time
import Settings
import lib.lib_mcprouter as lib_mcprouter

class Plugin(plugin.PluginProto):
 PLUGIN_ID = 9
 PLUGIN_NAME = "Extra IO - MCP23017/MCP23008"
 PLUGIN_VALUENAME1 = "State"

 def __init__(self,taskindex): # general init
  plugin.PluginProto.__init__(self,taskindex)
  self.dtype = rpieGlobals.DEVICE_TYPE_I2C
  self.vtype = rpieGlobals.SENSOR_TYPE_SWITCH
  self.ports = 0
  self.readinprogress = 0
  self.valuecount = 1
  self.senddataoption = True
  self.timeroption = True
  self.timeroptional = True
  self.inverselogicoption = True
  self.recdataoption = True
  self.mcp = None
  self.i2ca = 0
  self.rpin = -1
  self.i2cport = -1

 def plugin_init(self,enableplugin=None):
  plugin.PluginProto.plugin_init(self,enableplugin)
  self.decimals[0] = 0
  self.initialized = False
  if self.enabled:
   try:
     i2cl = self.i2c
   except:
     i2cl = -1
   try:
    i2cport = gpios.HWPorts.geti2clist()
    if i2cl==-1:
      i2cl = int(i2cport[0])
   except:
    i2cport = []
   if len(i2cport)>0 and i2cl>-1:
     try:
      pinnum = int(self.taskdevicepluginconfig[0])
     except:
      pinnum = 0
     try:
      tnum = int(self.taskdevicepluginconfig[2])
     except:
      tnum = 0
     if tnum<1:
      ctype = "MCP23017"
     else:
      ctype = "MCP23008"
     try:
      self.i2ca, self.rpin = lib_mcprouter.get_pin_address(pinnum)
      self.mcp = lib_mcprouter.request_mcp_device(int(i2cl),pinnum,ctype)
     except Exception as e:
      misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,"MCP device requesting failed: "+str(e))
      self.mcp = None
   if self.mcp and self.rpin>-1:
    try:
     if int(self.taskdevicepluginconfig[1])==0:
      pmode = "input"
      ppull = "disable"
     elif int(self.taskdevicepluginconfig[1])==1:
      pmode = "input"
      ppull = "enable"
     elif int(self.taskdevicepluginconfig[1])==2:
      pmode = "output"
      ppull = "disable"
     self.mcp.set_mode(self.rpin,pmode,ppull)
     self.set_value(1,self.mcp.input(self.rpin),True)
    except Exception as e:
     misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,"MCP pin configuration failed: "+str(e))
     self.mcp = None
   if self.mcp is None:
    self.enabled = False
    misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,"MCP can not be initialized! ")
   else:
    self.i2cport = int(i2cl)
    self.initialized = True
    if self.taskdevicepluginconfig[1] != 2:
     try:
      if self.mcp.externalintsetted>-1:
       self.taskdevicepin[0] = int(self.mcp.extinta)
      elif str(self.taskdevicepin[0]).strip() != "":
       self.mcp.setexternalint(0,int(self.taskdevicepin[0]),self.gettaskindex())
      if self.rpin>-1 and self.taskdevicepluginconfig[1]<2:
       self.mcp.add_interrupt(self.rpin,callbackFunctLow=self.p009_handler_low,callbackFunctHigh=self.p009_handler_high)
     except Exception as e:
      misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,"MCP interrupt configuration failed:"+str(e))
    try:
     self.ports = str(self.taskdevicepluginconfig[0])
    except:
     self.ports = 0
  else:
   self.ports = 0
   if self.rpin>-1 and int(self.taskdevicepluginconfig[1])<2:
      self.mcp.remove_interrupt(self.rpin)

 def plugin_exit(self):
    try:
     if self.rpin>-1 and int(self.taskdevicepluginconfig[1])<2:
      self.mcp.remove_interrupt(self.rpin)
    except:
     pass
    plugin.PluginProto.plugin_exit(self)

 def webform_load(self): # create html page for settings
  ownpin = -1
  try:
   if self.mcp:
    if self.mcp.externalintsetted>-1:
     ownpin=int(self.mcp.extinta)
   else:
    ownpin = ""
  except Exception as e:
   ownpin = -1
  webserver.addFormPinSelect("MCP interrupt","taskdevicepin0",ownpin)
  webserver.addFormNote("Add one RPI input pin to handle input changes immediately - not needed for interval input reading and output using only")
  webserver.addFormNumericBox("Port","p009_pnum",self.taskdevicepluginconfig[0],0,128)
  webserver.addFormNote("First extender 1-16, Second 17-32...")
  choice2 = self.taskdevicepluginconfig[1]
  options = ["Input","Input-Pullup","Output"]
  optionvalues = [0,1,2]
  webserver.addFormSelector("Type","p009_ptype",len(optionvalues),options,optionvalues,None,int(choice2))
  choice3 = self.taskdevicepluginconfig[2]
  options = ["MCP23017","MCP23008"]
  optionvalues = [0,1]
  webserver.addFormSelector("Chip","p009_chip",len(optionvalues),options,optionvalues,None,int(choice3))
  return True

 def webform_save(self,params): # process settings post reply
   par = webserver.arg("p009_pnum",params)
   if par == "":
    par = 0
   self.taskdevicepluginconfig[0] = int(par)
   par = webserver.arg("p009_ptype",params)
   try:
    self.taskdevicepluginconfig[1] = int(par)
   except:
    self.taskdevicepluginconfig[1] = 0
   par = webserver.arg("p009_chip",params)
   try:
    self.taskdevicepluginconfig[2] = int(par)
   except:
    self.taskdevicepluginconfig[2] = 0
   if self.taskdevicepluginconfig[1] != 2:
    try:
     par1 = webserver.arg("taskdevicepin0",params)
     self.mcp.setexternalint(0,int(par1),self.gettaskindex())
     self.taskdevicepin[0] = int(self.mcp.extinta)
    except Exception as e: 
     self.taskdevicepin[0]=-1
   else:
    self.interval = 0
   self.plugin_init()
   return True

 def p009_handler_low(self,pin):
  self.p009_handler(0)
  return

 def p009_handler_high(self,pin):
  self.p009_handler(1)
  return

 def p009_handler(self,value):
  if self.initialized and self.enabled:
   try:
    if float(value)!=float(self.uservar[0]):
     self.set_value(1,value,True)
     self._lastdataservetime = rpieTime.millis()
   except Exception as e:
     misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,str(e))
   return

 def plugin_read(self): # deal with data processing at specified time interval
  result = False
  if self.initialized and self.enabled and self.readinprogress==0:
    self.readinprogress = 1
    try:
     result = self.mcp.input(self.rpin)
     self.set_value(1,result,True)
     self._lastdataservetime = rpieTime.millis()
    except Exception as e:
     misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,str(e))
    self.readinprogress = 0
    result = True
  return result

 def plugin_write(self,cmd): # handle incoming commands
  res = False
  cmdarr = cmd.split(",")
  cmdarr[0] = cmdarr[0].strip().lower()
  if cmdarr[0] == "mcpgpio":
   pin = -1
   val = -1
   try:
    pin = int(cmdarr[1].strip())
    ti2ca, trpin = lib_mcprouter.get_pin_address(pin)
    val = int(cmdarr[2].strip())
   except:
    pin = -1
    trpin = -1
   if pin>-1 and val in [0,1] and trpin >-1:
    misc.addLog(rpieGlobals.LOG_LEVEL_DEBUG,"MCPGPIO"+str(pin)+" set to "+str(val))
    try:
     tmcp = lib_mcprouter.request_mcp_device(int(self.i2cport),int(pin))
     tmcp.set_mode(trpin, 'output')
     tmcp.output(trpin, val)
     self.syncvalue(pin,val)
    except Exception as e:
     misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,"MCPGPIO"+str(pin)+": "+str(e))
   return True
  elif cmdarr[0]=="mcppulse":
   pin = -1
   val = -1
   try:
    pin = int(cmdarr[1].strip())
    ti2ca, trpin = lib_mcprouter.get_pin_address(pin)
    val = int(cmdarr[2].strip())
   except:
    pin = -1
    trpin = -1
   dur = 100
   try:
    dur = float(cmdarr[3].strip())
   except:
    dur = 100
   if pin>-1 and val in [0,1] and trpin >-1:
    misc.addLog(rpieGlobals.LOG_LEVEL_DEBUG,"MCPGPIO"+str(pin)+": Pulse started")
    try:
     self.syncvalue(pin,val)
     tmcp = lib_mcprouter.request_mcp_device(int(self.i2cport),int(pin))
     tmcp.set_mode(trpin, 'output')
     tmcp.output(trpin, val)
     s = float(dur/1000)
     time.sleep(s)
     tmcp.output(trpin, (1-val))
     self.syncvalue(pin,(1-val))
    except Exception as e:
     misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,"MCPGPIO"+str(pin)+": "+str(e))
    misc.addLog(rpieGlobals.LOG_LEVEL_DEBUG,"MCPGPIO"+str(pin)+": Pulse ended")
   return True
  return res

 def syncvalue(self,epin,value):
  for x in range(0,len(Settings.Tasks)):
   if (Settings.Tasks[x]) and type(Settings.Tasks[x]) is not bool: # device exists
    if (Settings.Tasks[x].enabled):
     try:
      if (Settings.Tasks[x].pluginid==9) and (int(Settings.Tasks[x].taskdevicepluginconfig[0])==epin): # output on specific pin
       Settings.Tasks[x].uservar[0] = value
       if Settings.Tasks[x].valuenames[0]!= "":
        commands.rulesProcessing(Settings.Tasks[x].taskname+"#"+Settings.Tasks[x].valuenames[0]+"="+str(value),rpieGlobals.RULE_USER)
       Settings.Tasks[x].plugin_senddata()
       break
     except:
       pass

 def set_value(self,valuenum,value,publish=True,suserssi=-1,susebattery=-1): # Also reacting and handling Taskvalueset
  if self.initialized:
   if self.taskdevicepluginconfig[1] == 2:
    if 'on' in str(value).lower() or str(value)=="1":
     val = 1
    else:
     val = 0
    try:
     self.mcp.output(self.rpin, val)     # try to set gpio according to requested status
    except Exception as e:
     misc.addLog(rpieGlobals.LOG_LEVEL_ERROR,"MCP output error "+str(e))
  plugin.PluginProto.set_value(self,valuenum,value,publish,suserssi,susebattery)

 def plugin_receivedata(self,data):                        # set value based on mqtt input
  if (len(data)>0) and self.initialized and self.enabled:
   if 'on' in str(data[0]).lower() or str(data[0])=="1":
    val = 1
   else:
    val = 0
   self.set_value(1,val,False)
#  print("Data received:",data) # DEBUG
