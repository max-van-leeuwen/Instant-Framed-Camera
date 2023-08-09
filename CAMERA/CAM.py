# Instant Framed Camera - CAMERA MAIN SCRIPT
# by Max van Leeuwen

# requirements:
# to unlock wifi changes, run this once on the pi: sudo chmod a+w /etc/wpa_supplicant/wpa_supplicant.conf
# pip3 install pyzbar
# pip3 install opencv-python
# pip3 install numpy



# imports
import os
import time

from PIL import Image, ImageOps, ImageEnhance, ImageMath
from pyzbar.pyzbar import decode
from picamera2 import Picamera2
from libcamera import controls
import RPi.GPIO as GPIO

import ftplib
import logins



# params
keepTryingConnectionForever = True
size = 600, 448
captureName = 'captures/capture'
prepareName = 'captures/img'
captureExt = '.jpg'
prepareExt = '.jpg'
buttonPressCooldown = 0.5
newCaptureCooldown = 69
blinkingSpeed = 3
hostingHost = logins.HOSTNAME
hostingName = logins.USERNAME
hostingPass = logins.PASSWORD



# placeholders
scriptPath = os.path.realpath(__file__)
scriptDir = os.path.dirname(scriptPath)

cam = None
gpiopin = 21
gpioPrv = None
lastButtonPressTime = 0
lastCaptureTime = 0
blinkingStartTime = 0
isInCooldown = False
    
    
    
# setup camera
def initCam():
    global cam
    cam = Picamera2()
    cam.start()
    # cam.set_controls({"AfMode": controls.AfModeEnum.Auto, "AfSpeed": controls.AfSpeedEnum.Fast})
    cam.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": 0.4}) # set focus locked to 2.5m away (dioptres) - better for battery, and with glass disk in front the AF seems to be having some difficulties



def enableLight(v):
    ledPin = 18
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(ledPin, GPIO.OUT)
    GPIO.output(ledPin, 1 if v else 0)



# delete all files in local storage
def initLocal():
    try:
        capturePath = os.path.dirname(os.path.join(scriptDir, captureName))
        for root, dirs, files in os.walk(capturePath):
            for f in files:
                os.unlink(os.path.join(root, f))
                print('deleted ' + f)
    except Exception as e:
        print(f'error while cleaning up local folder: {e}')



# use camera
def captureImage():
    capturePath = os.path.join(scriptDir, captureName + captureExt)  
    cam.capture_file(capturePath)
    return capturePath



# add SSID and Password to Pi's wifi list
def addToWifiList(ssid, password):
    # this function overrides the wifi instead of adding to the list - can't read the wpa_supplicant without getting corrupt data or errors (some permissions issue)

    config_lines = [
        'ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev',
        'update_config=1',
        'country=NL',
        '\n',
        'network={',
        '\tssid="{}"'.format(ssid),
        '\tpsk="{}"'.format(password),
        '}'
        ]
    config = '\n'.join(config_lines)
    
    # give access and writing
    try:
        os.popen("sudo chmod a+w /etc/wpa_supplicant/wpa_supplicant.conf")
    except Exception as e:
        print(f"error setting rights to wpa_supplicant file: {e}")
    
    # writing to file
    try:
        with open("/etc/wpa_supplicant/wpa_supplicant.conf", "w") as wifi:
            wifi.write(config)

        # refresh configs
        os.popen("sudo wpa_cli -i wlan0 reconfigure")

    except Exception as e:
        print(f"error writing wifi supplicant: {e}")



# connect to wifi
def connectToWifiFromQR(capturePath):
    try:
        img = Image.open(capturePath)
        data = decode(img) # search for codes
        if len(data) > 0: # if qr found
            s = data[0].data.decode("utf-8").split(';')
            ssid = s[0][7:]
            pw = s[2][2:]
            print(f'found wifi! adding to list {ssid}:{pw}')
            addToWifiList(ssid, pw)
            doWifiBlink()
            return True
        return False
    
    except Exception as e:
        print(f'error while adding wifi from qr: {e}')
        return False
    


# 4x fast blinking when connected to wifi
def doWifiBlink():
    wifiBlinkDuration = .1
    for x in range(10):
        enableLight(True)
        time.sleep(wifiBlinkDuration)
        enableLight(False)
        time.sleep(wifiBlinkDuration)
    
    
    
# prepare any image for the display
def prepareImage(imagePath):
    # get image
    img = Image.open(imagePath)

    # correct resolution for display
    img = ImageOps.fit(img, size)

    # make RGB only
    img.convert('RGB')

    # initial overall saturation
    saturation = ImageEnhance.Color(img)
    img = saturation.enhance(3)


    # magenta is a problematic color on ink displays
    r, g, b = img.split()
    imgMask = ImageMath.eval("255*( (float(r)/255)**10*1.3 * (float(b)/255)**10*1.3 * (1-(float(g)/255)**10)*1.3 * 4 )", r=r, g=g, b=b) # (strong) mask magenta
    imgMask = imgMask.convert('L')

    # desaturated version to overlay
    saturation = ImageEnhance.Color(img)
    imgFixed = saturation.enhance(.3)
    brightness = ImageEnhance.Brightness(imgFixed)
    imgFixed = brightness.enhance(1.8)
    r, g, b = imgFixed.split()
    g = g.point(lambda i: i * .9) # slightly less green
    b = b.point(lambda i: i * .8) # less blue
    imgFixed = Image.merge('RGB', (r, g, b))

    # save
    preparedImagePath = os.path.join(scriptDir, prepareName + prepareExt)
    imgFixed.save(preparedImagePath)
    
    return preparedImagePath



# upload file path to hosting (overwrites old file, if any!)
def uploading(filepath):
    ftp = ftplib.FTP(hostingHost)
    ftp.login(hostingName, hostingPass)

    filename = os.path.basename(filepath)
    ftp.encoding = 'utf-8'
    with open(filepath, 'rb') as ftpup:
        ftp.storbinary('STOR ' + filename, ftpup)
    ftp.close()



# start upload
def uploadImageToHosting(filepath):
    try:
        uploading(filepath)
        return True

    except Exception as e1: # maybe something is wrong with the connection, try once more
        if(keepTryingConnectionForever):
            print(f'error while uploading to hosting, trying forever. error: {e1}')
            time.sleep(.6) # arbitrary wait time

            return uploadImageToHosting(filepath)
            
        else:
            print(f'error while uploading to hosting, trying again. error: {e1}')
            time.sleep(.6) # arbitrary wait time

            try:
                uploading(filepath)
                return True

            except Exception as e2: # not working, cancel, picture is lost
                print(f'error while uploading to hosting (again), cancelling. error: {e2}')
                return False



# delete from local storage
def deleteFiles(files):
    for f in files:
        os.remove(f)
        
        

# button checking loop
def startButton(callback):
    global gpioPrv
    global lastButtonPressTime
    global lastCaptureTime
    global isInCooldown
    
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(gpiopin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    gpioPrv = "null"
    
    while True:
        state = GPIO.input(gpiopin)
        thisTime = time.time()
        pressedSignal = False

        passedButtonCooldown = False
        passedCaptureCooldown = False

        # check if physical button is pressed signal
        if state == False and gpioPrv == "open" or state == False and gpioPrv == "null": # on button press
            pressedSignal = True
            gpioPrv = "closed"

        if(thisTime - lastButtonPressTime > buttonPressCooldown): # if passing the button cooldown time (compensating for hardware inaccuracy)
            passedButtonCooldown = True
            if(pressedSignal): # only actually update cooldown if button was pressed
                lastButtonPressTime = thisTime     

        if state != False and gpioPrv == "closed" or state != False and gpioPrv == "null": # on button release
            gpioPrv = "open"


        if(passedButtonCooldown): # when passed button cooldown time
            if(thisTime - lastCaptureTime > newCaptureCooldown): # if passing the capture cooldown time
                passedCaptureCooldown = True
                if(pressedSignal): # only actually update cooldown if button was pressed
                    lastCaptureTime = thisTime
            else:
                if(pressedSignal):
                    print('button press, only checking for QR because awaiting capture cooldown')
                    
                    # take capture
                    capturedImagePath = captureImage()

                    # connect to Wifi from QR (if any)
                    connectToWifiFromQR(capturedImagePath)

                    # delete from local storage
                    deleteFiles([capturedImagePath])

        if(passedCaptureCooldown): # if no more cooldowns
            if(isInCooldown): # switch once when cooldown stops
                isInCooldown = False
                print('cooldown done, listening for button press')
                enableLight(True) # stop blinking

            if(pressedSignal): # if button is pressed
                isInCooldown = True # start cooldown
                success = callback()
                if not success: # disable cooldown when not succeeded to send to display (also when scanning wifi qr)
                    print('skipping cooldown')
                    isInCooldown = False
                    lastCaptureTime -= newCaptureCooldown # offset to disable


        if isInCooldown:
            enableLight(getLightBlinking(thisTime)) # light blinking



def getLightBlinking(t):
    relativeTime = t - blinkingStartTime
    oddOrEven = (relativeTime * blinkingSpeed) % 2
    return True if oddOrEven > 0.5 else False
    
    

# if button was pressed
def buttonPressed():
    global blinkingStartTime

    print('- button pressed!')
    print('taking capture')

    # indicate power button pressed by disabling light
    enableLight(False)
    
    # take capture
    capturedImagePath = captureImage()
    
    print('checking if qr')

    # connect to Wifi from QR (if any)
    wifiFound = connectToWifiFromQR(capturedImagePath)
    if(wifiFound):
        enableLight(True)
        print("wifi qr code doesn't need to be processed")
        deleteFiles([capturedImagePath]) # delete from local storage
        return False
    
    # start blinking (arbitrary, based on processing steps, switches to time-based during countdown after)
    blinkingStartTime = time.time()
    
    print('preparing image')
    
    # prepare for display
    preparedImagePath = prepareImage(capturedImagePath)

    print('uploading to hosting')
    
    # uploading to hosting
    uploadSuccess = uploadImageToHosting(preparedImagePath)

    print('deleting local files')

    # delete from local storage
    deleteFiles([capturedImagePath, preparedImagePath])
    
    if not uploadSuccess:
        # if failed to upload, ignore
        enableLight(True)
        return False
    
    print('done! cooldown started')

    return True



# start
def start():
    initCam()
    startButton(buttonPressed)

enableLight(True)
time.sleep(1) # arbitrary wait time to initialize (camera module seemed to bug out sometimes without this)
start()