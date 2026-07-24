#!/usr/bin/env python3

import json
import base64
import binascii
import time
import os
import shutil
import paho.mqtt.client as mqtt


# ==================================================
# MQTT
# ==================================================

MQTT_HOST = "192.168.200.221"
MQTT_PORT = 1883


UPLINK_TOPIC = (
    "bridge/uplink/lora/dc56b7d6a7dd94a1/data"
)


# ==================================================
# 图片保存
# ==================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


IMAGE_DIR = os.path.join(
    BASE_DIR,
    "images"
)


os.makedirs(
    IMAGE_DIR,
    exist_ok=True
)


LATEST_IMAGE = os.path.join(
    IMAGE_DIR,
    "latest.jpg"
)


print(
    "IMAGE DIR:",
    IMAGE_DIR
)



# ==================================================
# 缓存参数
# ==================================================

IMAGE_TIMEOUT = 60

MAX_CACHE_IMAGES = 5


# key:
# (devEui,image_seq)

image_cache = {}



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

def parse_hc_v3(payload):


    if len(payload) < 24:

        return None



    # magic

    if payload[0:2] != b"HC":

        return None



    # version

    if payload[2] != 0x03:

        return None



    header_len = payload[16]



    chunk_count = payload[12]

    chunk_len = payload[13]

    chunk_index = payload[11]

    codec = payload[17]



    # 严格检查

    if chunk_count == 0:

        return None


    if chunk_len == 0:

        return None


    if header_len != 24:

        return None


    if codec != 1:

        return None


    if chunk_index >= chunk_count:

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
            chunk_index,


        "chunk_count":
            chunk_count,


        "chunk_len":
            chunk_len,


        "repeat_index":
            payload[14],


        "repeat_count":
            payload[15],


        "header_len":
            header_len,


        "codec":
            codec,


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
            payload[24:]

    }



# ==================================================
# 保存图片
# ==================================================

def save_image(
        dev_eui,
        seq,
        data
):


    filename = (
        f"{dev_eui}_{seq}.jpg"
    )


    path = os.path.join(
        IMAGE_DIR,
        filename
    )



    with open(
        path,
        "wb"
    ) as f:

        f.write(data)



    # 更新最新图片

    shutil.copyfile(
        path,
        LATEST_IMAGE
    )



    print(
        "IMAGE SAVED:",
        path
    )


    print(
        "LATEST UPDATED:",
        LATEST_IMAGE
    )



# ==================================================
# 缓存清理
# ==================================================

def maintain_cache():


    now = time.time()



    remove=[]



    for key,value in image_cache.items():


        if now - value["last"] > IMAGE_TIMEOUT:

            remove.append(key)



    for key in remove:

        print(
            "TIMEOUT REMOVE:",
            key
        )

        del image_cache[key]



    # 最大缓存数量

    if len(image_cache) > MAX_CACHE_IMAGES:


        old = sorted(
            image_cache.items(),
            key=lambda x:x[1]["last"]
        )


        while len(image_cache) > MAX_CACHE_IMAGES:

            key,_ = old.pop(0)

            print(
                "CACHE LIMIT REMOVE:",
                key
            )

            del image_cache[key]



# ==================================================
# 接收chunk
# ==================================================

def process_chunk(
        dev_eui,
        chunk
):


    seq = chunk["image_seq"]


    key = (
        dev_eui,
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
    # chunk CRC16
    # --------------------------

    crc = crc16_ccitt_false(
        chunk["jpeg"]
    )


    if crc != chunk["chunk_crc16"]:


        print(
            "CRC16 FAIL:",
            chunk["chunk_index"]
        )


        return



    index = chunk["chunk_index"]



    # 去重

    if index not in cache["chunks"]:

        cache["chunks"][index]=chunk["jpeg"]



    print(
        "RECV:",
        "seq=",
        seq,
        "chunk=",
        index,
        "/",
        chunk["chunk_count"],
        "round=",
        chunk["repeat_index"],
        "/",
        chunk["repeat_count"]
    )



    # 是否收齐

    if len(cache["chunks"]) == cache["chunk_count"]:


        assemble_image(
            dev_eui,
            key
        )



# ==================================================
# 拼接图片
# ==================================================

def assemble_image(
        dev_eui,
        key
):


    cache=image_cache[key]


    seq=key[1]


    image=b""


    for i in range(
        cache["chunk_count"]
    ):


        if i not in cache["chunks"]:


            print(
                "WAIT MISSING:",
                i
            )

            return



        image += cache["chunks"][i]



    # 长度检查

    image=image[
        :cache["image_len"]
    ]



    if len(image) != cache["image_len"]:


        print(
            "IMAGE LENGTH ERROR"
        )

        return



    # CRC32

    crc32 = (
        binascii.crc32(image)
        &
        0xffffffff
    )



    print(
        "CRC32:",
        hex(crc32)
    )


    print(
        "EXPECT:",
        hex(cache["image_crc32"])
    )



    if crc32 != cache["image_crc32"]:


        print(
            "CRC32 FAIL"
        )

        return



    if image[:2] != b"\xff\xd8":


        print(
            "JPEG HEADER ERROR"
        )


    if image[-2:] != b"\xff\xd9":


        print(
            "JPEG END ERROR"
        )



    print(
        "IMAGE COMPLETE:",
        seq
    )



    save_image(
        dev_eui,
        seq,
        image
    )



    # 成功后删除该缓存

    del image_cache[key]



# ==================================================
# MQTT
# ==================================================

def on_connect(
        client,
        userdata,
        flags,
        rc
):


    if rc == 0:


        print(
            "MQTT CONNECTED"
        )


        client.subscribe(
            UPLINK_TOPIC,
            qos=1
        )


        print(
            "SUB:",
            UPLINK_TOPIC
        )


    else:


        print(
            "MQTT ERROR",
            rc
        )



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



    # FPort必须2

    if data.get("fPort") != 2:

        return



    dev_eui=data.get(
        "deviceInfo",
        {}
    ).get(
        "devEui"
    )


    if not dev_eui:

        return



    payload_b64=data.get(
        "data"
    )


    if not payload_b64:

        return



    try:

        payload=base64.b64decode(
            payload_b64
        )

    except:

        return



    chunk=parse_hc_v3(
        payload
    )


    if not chunk:

        return



    print(
        "\n===================="
    )


    print(
        "DEVICE:",
        dev_eui
    )


    print(
        "SEQ:",
        chunk["image_seq"]
    )


    process_chunk(
        dev_eui,
        chunk
    )



# ==================================================
# MAIN
# ==================================================

client=mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION1
)


client.on_connect=on_connect

client.on_message=on_message



print(
    "CONNECT MQTT..."
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


    maintain_cache()