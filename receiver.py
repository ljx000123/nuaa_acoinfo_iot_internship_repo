#!/usr/bin/env python3

import json
import base64
import binascii
import time
import os
import paho.mqtt.client as mqtt


# ==================================================
# MQTT配置
# ==================================================

MQTT_HOST = "192.168.200.221"
MQTT_PORT = 1883


APPLICATION_ID = "3ed92fba-9e06-4b8e-ad41-54927a0fa89d"


# ==================================================
# 上行Topic
# ==================================================

UPLINK_TOPIC = (
    "bridge/uplink/lora/dc56b7d6a7dd94a1/data"
)


# ==================================================
# HA ACK独立Topic
# 不直接发送到ChirpStack command/down
# 由converter.py负责转换
# ==================================================

HA_ACK_TOPIC = (
    "bridge/downlink/ha/{}"
)


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


SAVE_PATH = os.path.join(
    BASE_DIR,
    "images"
)


os.makedirs(
    SAVE_PATH,
    exist_ok=True
)


print(
    "IMAGE SAVE PATH:",
    SAVE_PATH
)


# ==================================================
# 图片缓存
# ==================================================

# key:
# (device_id,image_seq)

image_cache = {}



# 超时时间

IMAGE_TIMEOUT = 60





# ==================================================
# CRC16 CCITT FALSE
# ==================================================

def crc16_ccitt_false(data):

    crc = 0xffff


    for b in data:

        crc ^= b << 8


        for _ in range(8):

            if crc & 0x8000:

                crc = (
                    crc << 1
                ) ^ 0x1021

            else:

                crc <<= 1


            crc &= 0xffff


    return crc





# ==================================================
# HCv3解析
# ==================================================

def parse_hub_camera(payload):


    if len(payload) < 24:

        return None



    if payload[0:2] != b"HC":

        return None



    if payload[2] != 3:

        return None



    header_len = payload[16]


    if header_len < 24:

        return None



    return {


        "flags":

            payload[3],



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



        "repeat_index":

            payload[14],



        "repeat_count":

            payload[15],



        "header_len":

            header_len,



        "codec":

            payload[17],



        "image_crc32":

            int.from_bytes(
                payload[18:22],
                "little"
            ),



        "chunk_crc16":

            int.from_bytes(
                payload[22:24],
                "little"
            ),



        "jpeg":

            payload[header_len:]

    }





# ==================================================
# 保存图片
# ==================================================

def save_image(
        device_id,
        image_seq,
        data
):


    filename = (
        f"{device_id}_{image_seq}.jpg"
    )


    path = os.path.join(
        SAVE_PATH,
        filename
    )


    with open(
        path,
        "wb"
    ) as f:

        f.write(data)



    print(
        "IMAGE SAVED:",
        path
    )






# ==================================================
# 接收chunk
# ==================================================

def process_chunk(
        device_id,
        chunk
):


    seq = chunk["image_seq"]


    key = (
        device_id,
        seq
    )



    now=time.time()



    if key not in image_cache:


        image_cache[key]={


            "image_len":

                chunk["image_len"],



            "chunk_count":

                chunk["chunk_count"],



            "image_crc32":

                chunk["image_crc32"],



            "chunks":{},



            "last":

                now

        }



    cache=image_cache[key]


    cache["last"]=now




    # --------------------------
    # CRC16检查
    # --------------------------

    crc = crc16_ccitt_false(
        chunk["jpeg"]
    )


    if crc != chunk["chunk_crc16"]:


        print(
            "CRC16 FAIL chunk",
            chunk["chunk_index"]
        )


        return False




    index=chunk["chunk_index"]



    # 去重

    if index not in cache["chunks"]:

        cache["chunks"][index]=(
            chunk["jpeg"]
        )



    print(
        "RECV:",
        "seq=",
        seq,
        "chunk=",
        index,
        "/",
        chunk["chunk_count"],
        "size=",
        len(chunk["jpeg"])
    )



    # 收齐

    if len(cache["chunks"]) == cache["chunk_count"]:


        print(
            "ALL CHUNKS RECEIVED"
        )


        return assemble_image(
            device_id,
            key
        )



    return False





# ==================================================
# 拼图
# ==================================================

def assemble_image(
        device_id,
        key
):


    cache=image_cache[key]


    seq=key[1]



    img=b""


    missing=[]



    for i in range(
        cache["chunk_count"]
    ):


        if i not in cache["chunks"]:

            missing.append(i)

        else:

            img += cache["chunks"][i]



    if missing:


        print(
            "MISSING:",
            missing
        )


        return {

            "ok":False,

            "missing":missing

        }

# ==================================================
# 拼图后处理
# ==================================================

def assemble_image(
        device_id,
        key
):


    cache = image_cache[key]


    seq = key[1]



    img = b""


    missing = []



    for i in range(
        cache["chunk_count"]
    ):


        if i not in cache["chunks"]:

            missing.append(i)

        else:

            img += cache["chunks"][i]



    if missing:


        print(
            "MISSING:",
            missing
        )


        return {

            "ok":False,

            "missing":missing

        }




    img = img[
        :cache["image_len"]
    ]



    crc32 = binascii.crc32(
        img
    ) & 0xffffffff



    print(
        "CRC32:",
        hex(crc32),
        "EXPECT:",
        hex(cache["image_crc32"])
    )



    if crc32 != cache["image_crc32"]:


        return {

            "ok":False,

            "crc_fail":True

        }




    if img[:2] != b"\xff\xd8":

        print(
            "JPEG HEAD ERROR"
        )



    if img[-2:] != b"\xff\xd9":

        print(
            "JPEG END ERROR"
        )



    save_image(
        device_id,
        seq,
        img
    )



    del image_cache[key]



    return {


        "ok":True

    }




# ==================================================
# HA ACK协议
# ==================================================

def build_ack(
        image_seq,
        status,
        missing=None
):


    """
    HA v1

    byte0-1:
        HA

    byte2:
        version=1

    byte3:
        cmd
        0 ACK_OK
        1 RETX_REQUEST


    byte4-7:
        image_seq little endian


    byte8:
        status
        0 ok
        1 missing
        2 crc_fail


    byte9:
        missing_count


    byte10:
        missing chunk index list

    """



    if missing is None:

        missing=[]



    if status == 0:

        cmd = 0

    else:

        cmd = 1




    payload = bytearray()



    # HA magic

    payload += b"HA"



    # version

    payload.append(
        1
    )



    # cmd

    payload.append(
        cmd
    )



    # image_seq

    payload += int(
        image_seq
    ).to_bytes(
        4,
        "little"
    )



    # status

    payload.append(
        status
    )



    # missing count

    payload.append(
        len(missing)
    )



    # missing list

    for index in missing:

        payload.append(
            index
        )



    return bytes(payload)





# ==================================================
# 发送HA ACK
# 注意：
# 不发送到command/down
# 使用独立topic
# ==================================================

def send_ha_ack(
        client,
        dev_eui,
        payload
):


    topic = HA_ACK_TOPIC.format(
        dev_eui
    )



    data_b64 = base64.b64encode(
        payload
    ).decode()



    msg = {


        "devEui":

            dev_eui,


        "confirmed":

            False,


        "fPort":

            3,


        "data":

            data_b64

    }



    client.publish(
        topic,
        json.dumps(msg),
        qos=1
    )



    print(
        "\n========== HA ACK =========="
    )


    print(
        "Topic:",
        topic
    )


    print(
        "Payload:",
        payload.hex()
    )





# ==================================================
# 超时检查
# 生成 RETX_REQUEST
# ==================================================

def clean_timeout(
        client
):


    now=time.time()



    remove=[]



    for key,value in image_cache.items():



        if now-value["last"] > IMAGE_TIMEOUT:


            device_id = key[0]


            image_seq = key[1]



            missing=[]



            for i in range(
                value["chunk_count"]
            ):


                if i not in value["chunks"]:

                    missing.append(i)



            print(
                "IMAGE TIMEOUT:",
                key
            )


            print(
                "REQUEST RETX:",
                missing
            )



            ack = build_ack(
                image_seq,
                1,
                missing
            )



            send_ha_ack(
                client,
                device_id,
                ack
            )



            remove.append(
                key
            )




    for key in remove:


        del image_cache[key]







# ==================================================
# MQTT连接
# ==================================================

def on_connect(
        client,
        userdata,
        flags,
        rc
):


    if rc == 0:


        print(
            "MQTT connected"
        )


        client.subscribe(
            UPLINK_TOPIC,
            qos=1
        )


        print(
            "Subscribe:",
            UPLINK_TOPIC
        )



    else:


        print(
            "MQTT ERROR:",
            rc
        )







# ==================================================
# MQTT消息处理
# ==================================================

def on_message(
        client,
        userdata,
        msg
):


    try:


        data=json.loads(
            msg.payload.decode()
        )


    except Exception as e:


        print(
            "JSON ERROR:",
            e
        )

        return


    dev_eui=data.get(
        "deviceInfo",
        {}
    ).get(
        "devEui"
    )


    if not msg.topic.startswith(
            "bridge/uplink/lora/"
    ):
        return


    if not dev_eui:

        return




    payload_b64=data.get(
        "data"
    )



    if not payload_b64:

        return




    payload=base64.b64decode(
        payload_b64
    )



    chunk=parse_hub_camera(
        payload
    )



    if not chunk:

        return




    print(
        "\n=============================="
    )


    print(
        "DEVICE:",
        dev_eui
    )


    print(
        "SEQ:",
        chunk["image_seq"],
        "CHUNK:",
        chunk["chunk_index"]
    )



    result=process_chunk(
        dev_eui,
        chunk
    )




    if isinstance(
        result,
        dict
    ):



        if result.get(
            "ok"
        ):



            ack=build_ack(
                chunk["image_seq"],
                0
            )



            send_ha_ack(
                client,
                dev_eui,
                ack
            )




        elif result.get(
            "missing"
        ):



            ack=build_ack(
                chunk["image_seq"],
                1,
                result["missing"]
            )



            send_ha_ack(
                client,
                dev_eui,
                ack
            )




        elif result.get(
            "crc_fail"
        ):



            ack=build_ack(
                chunk["image_seq"],
                2
            )



            send_ha_ack(
                client,
                dev_eui,
                ack
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
    "Connecting MQTT..."
)



client.connect(
    MQTT_HOST,
    MQTT_PORT,
    60
)




while True:


    client.loop(
        timeout=1
    )


    clean_timeout(
        client
    )