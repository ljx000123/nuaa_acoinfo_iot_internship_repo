#!/usr/bin/env python3



import json

import base64

import paho.mqtt.client as mqtt





# ==================================================

# MQTT配置

# ==================================================



MQTT_HOST = "127.0.0.1"

MQTT_PORT = 1883







# ChirpStack Application ID



APPLICATION_ID = (

    "3ed92fba-9e06-4b8e-ad41-54927a0fa89d"

)







# ==================================================

# 输入topic

# WiFi MQTT / 上层控制入口

# ==================================================



SOURCE_TOPIC = (

    "bridge/downlink/generic/+/cmd"

)







# ==================================================

# deviceName -> devEui

# 修改为实际S3设备

# ==================================================



DEVICE_MAP = {





    "eora_s3_400tb_001":

        "0000000000000925"





}











# ==================================================

# JSON命令转换成LoRa payload

#

# Byte0:

#   A5 固定

#

# Byte1:

#   01 LED

#   02 MOTOR

#

# Byte2:

#   00 OFF

#   01 ON

#

# ==================================================



def build_lora_command(

        cmd,

        value

):





    payload = bytearray()





    # 固定头



    payload.append(

        0xA5

    )







    # target



    if cmd == "led":





        payload.append(

            0x01

        )





    elif cmd in (

        "motor",

        "servo"

    ):





        payload.append(

            0x02

        )





    else:



        raise Exception(

            "Unknown command"

        )







    # value



    if value in (

        "on",

        "start",

        "1"

    ):





        payload.append(

            0x01

        )





    elif value in (

        "off",

        "stop",

        "0"

    ):





        payload.append(

            0x00

        )





    else:



        raise Exception(

            "Unknown value"

        )







    return bytes(payload)











# ==================================================

# MQTT消息处理

# ==================================================



def on_message(

        client,

        userdata,

        msg

):





    try:





        print()

        print("==========================")

        print("MQTT DOWNLINK REQUEST")







        print(

            "Topic:",

            msg.topic

        )







        data=json.loads(

            msg.payload.decode()

        )







        print(

            "JSON:",

            data

        )









        # topic:

        #

        # bridge/downlink/generic/eora_s3_400tb_001/cmd

        #



        parts=msg.topic.split("/")







        if len(parts) != 5:



            print(

                "Invalid topic"

            )



            return







        device_name=parts[3]







        if device_name not in DEVICE_MAP:





            print(

                "Unknown device:",

                device_name

            )





            return







        dev_eui=DEVICE_MAP[

            device_name

        ]







        cmd=data.get(

            "cmd"

        )





        value=data.get(

            "value"

        )







        if cmd is None or value is None:





            print(

                "Missing cmd/value"

            )





            return









        # JSON

        #

        # ->

        #

        # A5 01 01





        raw=build_lora_command(

            cmd.lower(),

            value.lower()

        )







        data_b64=base64.b64encode(

            raw

        ).decode()







        # ChirpStack标准downlink topic





        down_topic = (

            f"application/"

            f"{APPLICATION_ID}/"

            f"device/"

            f"{dev_eui}/"

            "command/down"

        )







        down_msg={





            "devEui":

                dev_eui,





            "confirmed":

                False,





            "fPort":

                2,





            "data":

                data_b64





        }









        client.publish(

            down_topic,

            json.dumps(down_msg),

            qos=1

        )







        print(

            "SEND LoRaWAN DOWNLINK"

        )





        print(

            "DeviceName:",

            device_name

        )





        print(

            "DevEUI:",

            dev_eui

        )





        print(

            "HEX:",

            raw.hex(" ")

        )





        print(

            "Base64:",

            data_b64

        )





        print(

            "Topic:",

            down_topic

        )







    except Exception as e:





        print(

            "ERROR:",

            e

        )











# ==================================================

# MQTT启动

# ==================================================



client=mqtt.Client(

    mqtt.CallbackAPIVersion.VERSION1

)







client.on_message=on_message







client.connect(

    MQTT_HOST,

    MQTT_PORT,

    60

)







client.subscribe(

    SOURCE_TOPIC,

    qos=1

)







print("==========================")

print("S3 LoRaWAN Downlink Converter")

print("==========================")



print(

    "Subscribe:",

    SOURCE_TOPIC

)







client.loop_forever()
