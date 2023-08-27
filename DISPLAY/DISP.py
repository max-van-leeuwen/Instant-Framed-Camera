# Instant Framed Camera - DISPLAY MAIN SCRIPT
# by Max van Leeuwen

# requirements:
# sudo pip3 install RPi.GPIO
# sudo pip3 install spidev
# sudo pip3 install Jetson.GPIO



# imports
from __future__ import print_function

import os
import ftplib
import logins
import json
import sys

from PIL import Image

from datetime import datetime
import time

import RPi.GPIO as GPIO

libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_epd import epd5in65f

import logging
logging.basicConfig(level=logging.DEBUG)



# params
configName = 'config.dat'
captureFolderName = 'capture/'
fileName = 'img.jpg'
prepareName = "img.bmp"
prepareExt = ".bmp"
hostingDownloadInterval = 5 # seconds



# placeholders
scriptPath = os.path.realpath(__file__)
scriptDir = os.path.dirname(scriptPath)

config = {'imageDate': 0}
configPath = os.path.join(scriptDir, configName)

hostingHost = logins.HOSTNAME
hostingName = logins.USERNAME
hostingPass = logins.PASSWORD

filePath = os.path.join(scriptDir, captureFolderName + fileName)

epd = epd5in65f.EPD()



# GPIO setup
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
buttonIndex = 16 # BOARD number 10
GPIO.setup(buttonIndex, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)



# setup config file
def initConfig(forceWrite):
    global config

    # read existing config
    if(os.path.isfile(configPath) and not forceWrite):
        with open(configPath) as f:
            config = json.load(f)

    # write new config
    else:
        with open(configPath, 'w') as f:
            json.dump(config, f)



# stay in sync with hosting
def checkHost():
    global config

    print('- start sync')

    # create ftp connection
    try:
        print('logging in ftp')

        # log in and check file date of image (if any)
        ftp = ftplib.FTP(hostingHost)
        ftp.login(hostingName, hostingPass)
        ftp.encoding = 'utf-8'

        newFileDate = None

        try:
            print('ftp file date check')

            t = ftp.voidcmd("MDTM " + fileName)[4:].strip()
            d = datetime.strptime(t, "%Y%m%d%H%M%S")

            newFileDate = (d - datetime(1970, 1, 1)).total_seconds()
        except:
            print('no file, or no success in retrieving file date')

        # if file date found
        if newFileDate is not None:
            # date difference check before downloading
            curFileDate = float(config['imageDate'])
            if(newFileDate >= curFileDate): # if file is newer
                print('ftp file is newer')

                downloadSucces = False

                try:
                    print(f'ftp download file to: {filePath}')
                    with open(filePath, 'wb') as f:
                        ftp.retrbinary('RETR ' + fileName, f.write)

                    downloadSucces = True

                    print('deleting file from hosting')
                    ftp.delete(fileName)
                        
                except Exception as e:
                    print(f'error while downloading/deleting from hosting: {e}')
                    pass


                if downloadSucces:
                    print('preparing image')

                    # prepare (most work has already been done by CAM)
                    preparePath = prepareImage(filePath)

                    print('starting image display')

                    # send to display
                    displayImage(preparePath)

                    print('clearing local storage')

                    # clear local storage
                    deleteFiles([filePath, preparePath])

                    print('updating config')

                    # update config
                    config['imageDate'] = newFileDate
                    initConfig(True)
            
            else:
                print('ftp file is older! not updating frame')

        print('logging out ftp')
        ftp.close()

    except:
        # connection might not be stable, ignore
        print('failed, ignoring (might be no wifi)')
        pass

    # loop hosting check at interval, check for button press inbetween
    t_end = time.time() + hostingDownloadInterval
    while time.time() < t_end:
        if GPIO.input(buttonIndex) == GPIO.HIGH:
            buttonPressed()
    checkHost()



# reset the image on the display
def clearDisplay():
    epd.init()
    print("clearing display")
    epd.Clear()



# prepare any image for the display
def prepareImage(imagePath):
    # get image
    img = Image.open(imagePath)

    # save
    preparedImagePath = os.path.join(scriptDir, captureFolderName + prepareName)
    print(f'saving prepared image to {preparedImagePath}')
    img.save(preparedImagePath)
    
    return preparedImagePath



# show a bmp (prepared) on the display
def displayImage(imagePath):
    try:
        clearDisplay()

        print("displaying new image")
        Himage = Image.open(imagePath)
        epd.display(epd.getbuffer(Himage))
        epd.sleep()
        
    except IOError as e:
        print(f'error while displaying image: {e}')
        
    except KeyboardInterrupt:    
        print("interrupted using keyboard (ctrl + c)")
        epd5in65f.epdconfig.module_exit()
        exit()



# delete from local storage
def deleteFiles(files):
    for f in files:
        os.remove(f)



# if button is pressed in interval inbetween hosting checks
def buttonPressed():
    print('button pressed')
    clearDisplay()



# start DISP
def start():
    print('- started')

    initConfig(False)
    checkHost()

start()