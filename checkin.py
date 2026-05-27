#!/usr/bin/python3
# -*- coding: utf-8 -*-
import requests
import time
import datetime
import re
import rsa
import json
import base64
import hashlib
import os
import random
from urllib.parse import urljoin

BI_RM = list("0123456789abcdefghijklmnopqrstuvwxyz")

def int2char(a):
    return BI_RM[a]

b64map = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def b64tohex(a):
    d = ""
    e = 0
    c = 0
    for i in range(len(a)):
        if list(a)[i] != "=":
            v = b64map.index(list(a)[i])
            if 0 == e:
                e = 1
                d += int2char(v >> 2)
                c = 3 & v
            elif 1 == e:
                e = 2
                d += int2char(c << 2 | v >> 4)
                c = 15 & v
            elif 2 == e:
                e = 3
                d += int2char(c)
                d += int2char(v >> 2)
                c = 3 & v
            else:
                e = 0
                d += int2char(c << 2 | v >> 4)
                d += int2char(15 & v)
    if e == 1:
        d += int2char(c << 2)
    return d

def rsa_encode(j_rsakey, string):
    rsa_key = f"-----BEGIN PUBLIC KEY-----\n{j_rsakey}\n-----END PUBLIC KEY-----"
    pubkey = rsa.PublicKey.load_pkcs1_openssl_pem(rsa_key.encode())
    result = b64tohex(
        (base64.b64encode(rsa.encrypt(f'{string}'.encode(), pubkey))).decode())
    return result

def calculate_md5_sign(params):
    return hashlib.md5('&'.join(sorted(params.split('&'))).encode('utf-8')).hexdigest()

def mask_phone(phone):
    if len(phone) == 11:
        return f"{phone[:3]}****{phone[-4:]}"
    return phone

def login(session, username, password):
    print(f"🔄 账号 {mask_phone(username)} 开始登录...")
    try:
        urlToken = "https://m.cloud.189.cn/udb/udb_login.jsp?pageId=1&pageKey=default&clientType=wap&redirectURL=https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html"
        r = session.get(urlToken, timeout=15)

        match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', r.text)
        if not match:
            match = re.search(r'<meta http-equiv="refresh" content="0;url=([^"]+)"', r.text)
            if not match:
                print("❌ 登录入口获取失败，页面结构已变更")
                return False

        login_url = urljoin(r.url, match.group(1))
        r = session.get(login_url, timeout=15)

        captchaToken = re.findall(r"captchaToken' value='(.+?)'", r.text)[0]
        lt = re.findall(r'lt = "(.+?)"', r.text)[0]
        returnUrl = re.findall(r"returnUrl= '(.+?)'", r.text)[0]
        paramId = re.findall(r'paramId = "(.+?)"', r.text)[0]
        j_rsakey = re.findall(r'j_rsaKey" value="(\S+)"', r.text, re.M)[0]
        session.headers.update({"lt": lt})

        user_enc = rsa_encode(j_rsakey, username)
        pwd_enc = rsa_encode(j_rsakey, password)

        post_url = "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1',
            'Referer': 'https://open.e.189.cn/',
            'Origin': 'https://open.e.189.cn'
        }
        data = {
            "appKey": "cloud",
            "accountType": '01',
            "userName": f"{{RSA}}{user_enc}",
            "password": f"{{RSA}}{pwd_enc}",
            "validateCode": "",
            "captchaToken": captchaToken,
            "returnUrl": returnUrl,
            "mailSuffix": "@189.cn",
            "paramId": paramId
        }
        r = session.post(post_url, data=data, headers=headers, timeout=15)
        res = r.json()

        if res.get("result") != 0:
            print(f"❌ 登录失败：{res.get('msg')}")
            return False

        session.get(res["toUrl"], timeout=15)
        print(f"✅ {mask_phone(username)} 登录成功")
        return True

    except Exception as e:
        print(f"⚠️ 登录异常：{str(e)}")
        return False

def sign_and_draw(session):
    rand = str(round(time.time() * 1000))
    sign_url = f'https://api.cloud.189.cn/mkt/userSign.action?rand={rand}&clientType=TELEANDROID&version=8.6.3&model=SM-G930K'
    draw1 = f'https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?taskId=TASK_SIGNIN&activityId=ACT_SIGNIN'
    draw2 = f'https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?taskId=TASK_SIGNIN_PHOTOS&activityId=ACT_SIGNIN'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 5.1.1; SM-G930K Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/74.0.3729.136 Mobile Safari/537.36 Ecloud/8.6.3 Android/22 clientId/355325117317828 clientModel/SM-G930K imsi/460071114317824 clientChannelId/qq proVersion/1.0.6',
        "Referer": "https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1",
        "Host": "m.cloud.189.cn",
        "Accept-Encoding": "gzip, deflate",
    }

    sign_resp = session.get(sign_url, headers=headers, timeout=15).json()
    netdiskBonus = sign_resp.get("netdiskBonus", "0")
    if sign_resp.get("isSign") == "false":
        sign_str = f"未签到，签到获得{netdiskBonus}M空间"
    else:
        sign_str = f"已签到，本次获得{netdiskBonus}M空间"
    print(sign_str)

    cj1 = "抽奖失败/活动已过期"
    try:
        d1 = session.get(draw1, headers=headers, timeout=15).json()
        if "errorCode" not in d1:
            cj1 = f"抽奖获得：{d1.get('description','无')}"
    except:
        pass
    print(cj1)

    cj2 = "抽奖失败/活动已过期"
    try:
        d2 = session.get(draw2, headers=headers, timeout=15).json()
        if "errorCode" not in d2:
            cj2 = f"抽奖获得：{d2.get('description','无')}"
    except:
        pass
    print(cj2)

    return sign_str, cj1, cj2

def push_msg(sign_str, cj1, cj2):
    now_time = datetime.datetime.now()
    bj_time = now_time + datetime.timedelta(hours=8)
    time_str = bj_time.strftime("%Y-%m-%d %H:%M:%S %p")

    desp = f"""
------
### 🚁Now：
