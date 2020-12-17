# Version 1.6 of the PJB Sensor Code
# Including battery Voltage
# Peter Brammer. - 2020-12-13

from network import LoRa
import machine
import utime
import socket
import binascii
import struct
import ubinascii
import pycom

# READING_FREQ_IN_MIN = 5   # equals 20 mins
READING_FREQ_IN_MIN = 0.1   # equals 4 mins
# READING_FREQ_IN_MIN = 0.01   # 1  min
# package header, B: 1 byte for deviceID, I: 1 byte for int, 1 Byte for int
CODE_VERSION = 1.6
_LORA_PKG_FORMAT = "BII"
DEVICE_ID = 0x01
# Max Value from Sensor when 100% wet
SENSOR_100 = 720
# LoRa constants
APP_EUI_KEY = '70B3D57ED0039C31'
APP_KEY_VALUE = '84E5C11D9E3CD113A5E38AD6742F9C39'

def setup_adc():
    try:
        adc = machine.ADC()
        adc.init(bits=12)
        sensor = adc.channel(pin='P13', attn=machine.ADC.ATTN_11DB)
    except Exception as e:
        print(e)
    return sensor

def adc_battery():
    adc1 = machine.ADC()
    # Create an object to sample adc on pin 16 with attennuation of 11db
    adc_c = adc1.channel(attn=3, pin='P16')
    adc_samples = []
    # take 100 samples and append them into a list
    for count in range(100):
        adc_samples.append(int(adc_c()))

    adc_samples = sorted(adc_samples)
    # take the center list row value (median average)
    adc_median = adc_samples[int(len(adc_samples)/2)]
    # apply the function to scale to volts
    adc_median = adc_median * 2 / 4095 / 0.3275
    # Convert adc_median to an int and multiply by 100
    adc_median = int(adc_median * 100)
    # print(adc_samples)
    return adc_median

def setup_power_pin():
    power = machine.Pin('P19', machine.Pin.OUT)
    power.value(0)
    return power

def join_via_otaa(lora):
    app_eui = ubinascii.unhexlify(APP_EUI_KEY)
    app_key = ubinascii.unhexlify(APP_KEY_VALUE)
    # Join the network using OTAA Authentication
    lora.join(activation=LoRa.OTAA, auth=(app_eui, app_key), timeout=0)


def create_lora_socket():
    lora_socket = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    lora_socket.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)
    lora_socket.setblocking(True)
    lora_socket.settimeout(5)  # Set timeout to be 5 seconds
    return lora_socket

def send_message(sensor_reading, battery_voltage):
    print('sending message')
    lora_socket = create_lora_socket()
    pkt = struct.pack(_LORA_PKG_FORMAT, DEVICE_ID, sensor_reading, battery_voltage)
    try:

        lora_socket.send(pkt)
    except Exception as e:
        print(e)
    lora_socket.setblocking(False)
    return lora_socket

def receive_message(lora_sct):
    rx_pkt = lora_sct.recv(64)
    # Check if a downlink was received
    if len(rx_pkt) > 0:
        print("Downlink data on port 200: ", rx_pkt)
    else:
        print("Nothing Received")
    return

def read_sensor(sensor, power_pin):
    # take multiple readings and take the average to get a more reliable reading
    print('reading sensor')
    READING_DELAY_IN_S = 1
    NUM_READINGS = 10
    total = 0
    for i in range(0, NUM_READINGS):
        power_pin.value(1)
        utime.sleep(READING_DELAY_IN_S)
        sensor_reading = sensor.value()
        # print('Moisture value: {0}'.format(sensor.value()))
        total += sensor_reading
        power_pin.value(0)
    average_reading = int(total/NUM_READINGS)
    print('Average value: {0}'.format(average_reading))
    # convert to Percent - Max value set by SENSOR_100
    moisture_percent = int((average_reading/SENSOR_100) * 100)
    print('Moisture Percentage: {0}'.format(moisture_percent))
    return moisture_percent


def main():
    print('Code Version {0}'.format(CODE_VERSION))
    # setup lopy4 pins
    print('Sensor Set Up')
    sensor = setup_adc()
    power = setup_power_pin()
    #intialize lora object
    print('Establish LoRa')
    lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.AU915)
    # lora = setup_single_lora_channel(lora)
    lora.nvram_restore()

    # disable LED Heartbeat (so we can control the LED)
    pycom.heartbeat(False)
    # Set LED to RED
    pycom.rgbled(0x7f0000)

    if not lora.has_joined():
        #  join_via_abp(lora)
        join_via_otaa(lora)
        while not lora.has_joined():
            utime.sleep(2.5)
            print('Not yet joined...')
            if utime.time() > 150:
                print("Possible Timeout")
                machine.reset()
            pass
        # We are Online set LED to Green
        pycom.rgbled(0x007f00)
        print('Join successful Getting ready to send!')
    else:
        print('Lora already established')

    sensor_reading = read_sensor(sensor, power)
    lipo_voltage = adc_battery()
    print("Battery Voltage: ",lipo_voltage)
    lora_socket = send_message(sensor_reading, lipo_voltage)
    # receive_message(lora_socket)
    utime.sleep(1)
    lora.nvram_save()
    print('Entering Deep Sleep')
    machine.deepsleep(int(READING_FREQ_IN_MIN*60*1000))

if __name__ == '__main__':
    main()
