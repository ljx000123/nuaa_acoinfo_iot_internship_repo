#!/usr/bin/env python3

import json
import paho.mqtt.client as mqtt


# ==================================================
# MQTT配置
# ==================================================

BROKER = "127.0.0.1"
PORT = 1883


APPLICATION_ID = (
    "3ed92fba-9e06-4b8e-ad41-54927a0fa89d"
)



# ==================================================
# 上行转换
#
# ChirpStack:
#
# application/+/device/+/event/up
#
#        |
#        v
#
# bridge/uplink/lora/{dev_eui}/data
#
# ==================================================

UPLINK_SOURCE_TOPIC = (
    "application/+/device/+/event/up"
)



# ==================================================
# HA ACK下行转换
#
# receiver:
#
# bridge/downlink/ha/{dev_eui}
#
#        |
#        v
#
# application/{app}/device/{dev_eui}/command/down
#
# ==================================================

HA_ACK_SOURCE_TOPIC = (
    "bridge/downlink/ha/+"
)





# ==================================================
# MQTT客户端
# ==================================================

publisher = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION1
)


publisher.connect(
    BROKER,
    PORT,
    60
)


publisher.loop_start()






# ==================================================
# 上行处理
# ==================================================

def handle_uplink(
        raw
):


    try:


        device_info = raw.get(
            "deviceInfo",
            {}
        )


        dev_eui = device_info.get(
            "devEui"
        )


        if dev_eui is None:

            print(
                "NO DEV EUI"
            )

            return



        output = {


            "deviceInfo":{


                "devEui":
                    dev_eui,


                "deviceName":
                    device_info.get(
                        "deviceName"
                    )

            },


            "data":
                raw.get(
                    "data"
                ),


            "time":
                raw.get(
                    "time"
                ),


            "devAddr":
                raw.get(
                    "devAddr"
                ),


            "fCnt":
                raw.get(
                    "fCnt"
                ),


            "fPort":
                raw.get(
                    "fPort"
                ),


            "rxInfo":
                raw.get(
                    "rxInfo"
                ),


            "txInfo":
                raw.get(
                    "txInfo"
                )

        }




        topic = (
            f"bridge/uplink/lora/"
            f"{dev_eui}/data"
        )



        publisher.publish(
            topic,
            json.dumps(output),
            qos=1
        )



        print(
            "[UPLINK]",
            topic
        )



    except Exception as e:


        print(
            "UPLINK ERROR:",
            e
        )









# ==================================================
# HA ACK处理
# ==================================================

def handle_ha_ack(
        dev_eui,
        raw
):


    try:



        data = raw.get(
            "data"
        )



        if data is None:

            print(
                "NO ACK DATA"
            )

            return



        topic = (

            f"application/"
            f"{APPLICATION_ID}/"
            f"device/"
            f"{dev_eui}/"
            "command/down"

        )



        downlink = {


            "devEui":

                dev_eui,


            "confirmed":

                False,


            "fPort":

                raw.get(
                    "fPort",
                    3
                ),


            "data":

                data

        }



        publisher.publish(
            topic,
            json.dumps(downlink),
            qos=1
        )



        print(
            "[HA ACK DOWN]",
            topic
        )


        print(
            "payload:",
            data
        )



    except Exception as e:


        print(
            "HA ACK ERROR:",
            e
        )









# ==================================================
# MQTT消息回调
# ==================================================

def on_message(
        client,
        userdata,
        msg
):


    try:


        raw=json.loads(
            msg.payload.decode()
        )



    except Exception as e:


        print(
            "JSON ERROR:",
            e
        )

        return





    # ----------------------------------
    # HUB图片上行
    # ----------------------------------

    if msg.topic.startswith(
        "application/"
    ):


        handle_uplink(
            raw
        )


        return






    # ----------------------------------
    # HA ACK下行
    # ----------------------------------

    if msg.topic.startswith(
        "bridge/downlink/ha/"
    ):



        dev_eui = (
            msg.topic
            .split("/")[-1]
        )



        handle_ha_ack(
            dev_eui,
            raw
        )



        return







# ==================================================
# 连接
# ==================================================

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION1
)



client.on_message = on_message



client.connect(
    BROKER,
    PORT,
    60
)




client.subscribe(
    UPLINK_SOURCE_TOPIC,
    qos=1
)


client.subscribe(
    HA_ACK_SOURCE_TOPIC,
    qos=1
)





print(
    "=============================="
)

print(
    "LoRa MQTT Topic Converter"
)

print(
    "=============================="
)


print(
    "Subscribe:"
)

print(
    UPLINK_SOURCE_TOPIC
)


print(
    HA_ACK_SOURCE_TOPIC
)




client.loop_forever()
