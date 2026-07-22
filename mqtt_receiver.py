#!/usr/bin/env python3

import json
import base64
import paho.mqtt.client as mqtt


# ==================================================
# MQTT配置
# ==================================================

MQTT_HOST = "192.168.200.221"
MQTT_PORT = 1883


# ==================================================
# MQTT Topic
# ==================================================

MQTT_TOPICS = [

    (
        "bridge/uplink/lora/+/data",
        1
    ),

    (
        "bridge/uplink/generic/eora_s3_400tb_001/data",
        1
    )

]



# ==================================================
# S3 LoRaWAN V2
# ==================================================

def parse_s3_lora_v2(payload):


    if len(payload) != 37:
        return None


    if payload[0] != 2:
        return None



    flags = payload[1]


    return {


        "version":2,


        "joined":
            bool(flags & 0x01),


        "motor_running":
            bool(flags & 0x02),


        "led_on":
            bool(flags & 0x04),


        "application_retry":
            bool(flags & 0x08),



        "seq":
            int.from_bytes(
                payload[2:4],
                "big"
            ),



        "boot_id":
            hex(
                int.from_bytes(
                    payload[4:8],
                    "big"
                )
            ),



        "temperature":
            int.from_bytes(
                payload[21:23],
                "big",
                signed=True
            ) / 10,



        "humidity":
            int.from_bytes(
                payload[23:25],
                "big"
            ) / 10,



        "soil":
            int.from_bytes(
                payload[25:27],
                "big"
            ) / 10,



        "rain":
            int.from_bytes(
                payload[27:29],
                "big"
            ) / 10,



        "motor":
            payload[33],


        "servo":
            payload[34],


        "led":
            payload[35],



        "signal":
            int.from_bytes(
                payload[36:37],
                "big",
                signed=True
            )

    }





# ==================================================
# HUB Camera HCv2
# ==================================================

def parse_hub_camera(payload):


    if len(payload) < 14:
        return None


    if payload[0:2] != b"HC":
        return None


    if payload[2] != 2:
        return None



    flags = payload[3]



    return {


        "version":
            payload[2],



        "camera_ok":
            bool(flags & 0x01),



        "mqtt_ok":
            bool(flags & 0x02),



        "pc_ok":
            bool(flags & 0x04),



        "image_seq":
            int.from_bytes(
                payload[4:8],
                "little"
            ),



        "image_len":
            int.from_bytes(
                payload[8:11],
                "little"
            ),



        "chunk_index":
            payload[11],



        "chunk_count":
            payload[12],



        "chunk_len":
            payload[13],



        "jpeg":
            payload[14:]

    }




# ==================================================
# WiFi S3
# ==================================================

def parse_wifi(data):


    print(
        "\n========== WiFi S3数据 =========="
    )


    print(
        "Device:",
        data.get("device_id")
    )


    print(
        "Temperature:",
        data.get("temperature"),
        "℃"
    )


    print(
        "Humidity:",
        data.get("humidity"),
        "%"
    )


    print(
        "Soil:",
        data.get("soil_moisture"),
        "%"
    )


    print(
        "Rain:",
        data.get("rain_level"),
        "%"
    )


    print(
        "Motor:",
        data.get("motor_status")
    )


    print(
        "Servo:",
        data.get("servo_angle")
    )


    print(
        "LED:",
        data.get("led_status")
    )


    print(
        "Signal:",
        data.get("signal")
    )


    print(
        "============================"
    )





# ==================================================
# LoRa解析
# ==================================================

def parse_lora(data,topic):


    device_id = topic.split("/")[3]


    print(
        "\nDevice:",
        device_id
    )


    payload_b64 = data.get(
        "data"
    )


    if not payload_b64:

        print(
            "无Payload"
        )

        return



    payload = base64.b64decode(
        payload_b64
    )



    print(
        "HEX:",
        payload.hex()
    )



    # ----------------------
    # HUB Camera
    # ----------------------

    hub = parse_hub_camera(
        payload
    )


    if hub:


        print(
            "\n======= HUB Camera HC ======="
        )


        print(
            "Version:",
            hub["version"]
        )


        print(
            "Camera:",
            hub["camera_ok"]
        )


        print(
            "MQTT:",
            hub["mqtt_ok"]
        )


        print(
            "PC:",
            hub["pc_ok"]
        )


        print(
            "Image Seq:",
            hub["image_seq"]
        )


        print(
            "Image Length:",
            hub["image_len"]
        )


        print(
            "Chunk:",
            hub["chunk_index"],
            "/",
            hub["chunk_count"]
        )


        print(
            "Chunk Length:",
            hub["chunk_len"]
        )


        print(
            "JPEG:",
            len(hub["jpeg"]),
            "bytes"
        )


        if len(hub["jpeg"]) >= 2:


            print(
                "JPEG HEAD:",
                hub["jpeg"][:10].hex()
            )


        print(
            "=============================="
        )


        return





    # ----------------------
    # S3 LoRa
    # ----------------------

    s3 = parse_s3_lora_v2(
        payload
    )


    if s3:


        print(
            "\n======= S3 LoRa ======="
        )


        print(
            "Temperature:",
            s3["temperature"],
            "℃"
        )


        print(
            "Humidity:",
            s3["humidity"],
            "%"
        )


        print(
            "Soil:",
            s3["soil"],
            "%"
        )


        print(
            "Rain:",
            s3["rain"],
            "%"
        )


        print(
            "Seq:",
            s3["seq"]
        )


        print(
            "Boot:",
            s3["boot_id"]
        )


        print(
            "Motor:",
            "running"
            if s3["motor_running"]
            else
            "stopped"
        )


        print(
            "Servo:",
            s3["servo"]
        )


        print(
            "LED:",
            "on"
            if s3["led_on"]
            else
            "off"
        )


        print(
            "Signal:",
            s3["signal"]
        )


        print(
            "Joined:",
            s3["joined"]
        )


        print(
            "========================"
        )


        return



    print(
        "未知LoRa Payload"
    )





# ==================================================
# MQTT
# ==================================================

def on_connect(client,userdata,flags,rc):


    if rc==0:


        print(
            "MQTT连接成功"
        )


        client.subscribe(
            MQTT_TOPICS
        )


        print(
            "订阅Topic:"
        )


        for t,q in MQTT_TOPICS:

            print(
                " ",
                t
            )




def on_message(client,userdata,msg):


    print(
        "\n========================"
    )


    print(
        "Topic:",
        msg.topic
    )



    try:

        data=json.loads(
            msg.payload.decode()
        )


    except Exception as e:


        print(
            "JSON错误:",
            e
        )

        return




    if msg.topic.startswith(
        "bridge/uplink/generic/"
    ):


        parse_wifi(
            data
        )


    elif msg.topic.startswith(
        "bridge/uplink/lora/"
    ):


        parse_lora(
            data,
            msg.topic
        )





# ==================================================
# Main
# ==================================================

client=mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION1
)


client.on_connect=on_connect

client.on_message=on_message



print(
    "正在连接MQTT..."
)



client.connect(
    MQTT_HOST,
    MQTT_PORT,
    60
)



client.loop_forever()