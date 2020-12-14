# Version 1.3 of the PJB Sensor Code
# Peter Brammer. - 2020-12-13

from network import LoRa
import machine
import utime
import socket
import binascii
import struct
import ubinascii

# package header, B: 1 byte for deviceID, I: 1 byte for int
_LORA_PKG_FORMAT = "BI"
DEVICE_ID = 0x01
# Max Value from Sensor when 100% wet
SENSOR_100 = 720

# LoRa constants
FREQ = 915000000
DEV_ADDR = '<DEVICE ADDRESS>'
NWK_SWKEY = '<NETWORK SESSION KEY>'
APP_SWKEY = '<APP SESSION KEY>'

APP_EUI_KEY = '70B3D57ED0039C31'
APP_KEY_VALUE = '84E5C11D9E3CD113A5E38AD6742F9C39'

READING_FREQ_IN_MIN = 0.5   # 16 Mins
# READING_FREQ_IN_MIN = 0.01   # 1  min

def setup_adc():
    try:
        adc = machine.ADC()
        adc.init(bits=12)
        sensor = adc.channel(pin='P13', attn=machine.ADC.ATTN_11DB)
    except Exception as e:
        print(e)
    return sensor

def setup_power_pin():
    power = machine.Pin('P19', machine.Pin.OUT)
    power.value(0)
    return power

def setup_single_lora_channel(lora):
    # remove all the channels
    for channel in range(0, 72):
        lora.remove_channel(channel)
    # set all channels to the same frequency
    for channel in range(0, 8):
        lora.add_channel(channel, frequency=FREQ, dr_min=0, dr_max=3)
    return lora

def join_via_abp(lora):
    # create an ABP authentication params
    dev_addr_in_bytes = struct.unpack(">l", binascii.unhexlify(DEV_ADDR))[0]
    nwk_swkey_in_bytes = binascii.unhexlify(NWK_SWKEY)
    app_swkey_in_bytes = binascii.unhexlify(APP_SWKEY)

    # join a network using ABP (Activation By Personalization)
    lora.join(activation=LoRa.ABP, auth=(dev_addr_in_bytes, nwk_swkey_in_bytes, app_swkey_in_bytes))

def join_via_otaa(lora):
    app_eui = ubinascii.unhexlify(APP_EUI_KEY)
    app_key = ubinascii.unhexlify(APP_KEY_VALUE)

    # Join the network using OTAA Authentication
    lora.join(activation=LoRa.OTAA, auth=(app_eui, app_key), timeout=0)


def create_lora_socket():
    lora_socket = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    lora_socket.setsockopt(socket.SOL_LORA, socket.SO_DR, 3)
    lora_socket.setblocking(False)
    return lora_socket

def send_message(sensor_reading):
    print('sending message')
    lora_socket = create_lora_socket()
    pkt = struct.pack(_LORA_PKG_FORMAT, DEVICE_ID, sensor_reading)
    try:
        lora_socket.send(pkt)
    except Exception as e:
        print(e)

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

    # setup lopy4 pins
    print('Sensor Set Up')
    sensor = setup_adc()
    power = setup_power_pin()

    #intialize lora object
    print('Establish LoRa')
    lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.AU915)
    # lora = setup_single_lora_channel(lora)
    lora.nvram_restore()

    if not lora.has_joined():
        #  join_via_abp(lora)
        join_via_otaa(lora)
        while not lora.has_joined():
            utime.sleep(2.5)
            print('Not yet joined...')
        print('Join successful Getting ready to send!')
    else:
        print('Lora already established')

    sensor_reading = read_sensor(sensor, power)
    send_message(sensor_reading)
    utime.sleep(1)
    lora.nvram_save()
    print('Entering Deep Sleep')
    machine.deepsleep(int(READING_FREQ_IN_MIN*60*1000))

if __name__ == '__main__':
    main()
