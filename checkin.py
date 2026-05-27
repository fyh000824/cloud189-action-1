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

BI_RM = list("0123456789abcdefghijklmnopqrstuvwxyz")
B64MAP = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def int2char(a):
    return BI_RM[a]

def b64tohex(a):
    d = ""
    e = 0
    c = 0
    for i in range(len(a)):
        if list(a)[i] != "=":
            v = B64MAP.index(list(a)[i])
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
    result = b64tohex((base64.b64encode(rsa.encrypt(f'{string}'.encode(), pubkey))).decode())
    return result

def mask_phone(phone):
    if len(phone) == 11:
        return phone[:3] + "****" + phone[-4:]
    return phone

def login(session, username, password):
    print(f"\n🔄 账号 {mask_phone(username)} 登录中...")
    try:
        # 新版登录页（V5）
        login_page_url = "https://open.e.189.cn/api/logbox/separate/wap/login.html"
        r = session.get(login_page, timeout=15)

        # 直接提取 j_rsaKey（新版唯一关键参数）
        j_rsaKey = re.search(r'id="j_rsaKey"\s+value="([^"]+)"', r.text)
        if not j_rsaKey:
            print("❌ 未找到 RSA 公钥，页面结构已变")
            return False
        j_rsaKey = j_rsaKey.group(1)

        # 加密账号密码
        user_enc = rsa_encode(j_rsaKey, username)
        pwd_enc = rsa_encode(j_rsaKey, password)

        # 新版登录接口
        post_url = "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1',
            'Referer': login_page_url,
            'Origin': 'https://open.e.189.cn'
        }
        data = {
            "appKey": "cloud",
            "accountType": "01",
            "userName": f"{{RSA}}{user_enc}",
            "password": f"{{RSA}}{pwd_enc}",
            "validateCode": "",
            "captchaToken": "",
            "returnUrl": "https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html",
            "mailSuffix": "@189.cn",
            "paramId": ""
        }

        r = session.post(post_url, data=data, headers=headers, timeout=15)
        res = r.json()

        if res.get("result") != 0:
            print(f"❌ 登录失败：{res.get('msg')}")
            return False

        # 登录成功跳转
        session.get(res["toUrl"], timeout=15)
        print(f"✅ {mask_phone(username)} 登录成功")
        return True

    except Exception as e:
        print(f"⚠️ 登录异常：{str(e)}")
        return False

def sign_and_draw(session):
    rand = str(round(time.time() * 1000))
    sign_url = f'https://api.cloud.189.cn/mkt/userSign.action?rand={rand}&clientType=TELEANDROID&version=8.6.3&model=SM-G930K'
    draw1 = 'https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?taskId=TASK_SIGNIN&activityId=ACT_SIGNIN'
    draw2 = 'https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?taskId=TASK_SIGNIN_PHOTOS&activityId=ACT_SIGNIN'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 5.1.1; SM-G930K Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/74.0.3729.136 Mobile Safari/537.36 Ecloud/8.6.3 Android/22',
        "Referer": "https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1",
        "Host": "m.cloud.189.cn"
    }

    # 签到
    try:
        resp = session.get(sign_url, headers=headers, timeout=15).json()
        bonus = resp.get("netdiskBonus", "0")
        if resp.get("isSign") == "false":
            sign_str = f"✅ 签到成功，获得{bonus}M"
        else:
            sign_str = f"⏳ 已签到，本次{bonus}M"
    except:
        sign_str = "❌ 签到失败"

    # 抽奖1
    try:
        d1 = session.get(draw1, headers=headers, timeout=15).json()
        cj1 = d1.get("description", "抽奖失效") if "errorCode" not in d1 else "抽奖失效"
    except:
        cj1 = "抽奖异常"

    # 抽奖2
    try:
        d2 = session.get(draw2, headers=headers, timeout=15).json()
        cj2 = d2.get("description", "抽奖失效") if "errorCode" not in d2 else "抽奖失效"
    except:
        cj2 = "抽奖异常"

    print(sign_str)
    print(f"🎁 {cj1}")
    print(f"🎁 {cj2}")
    return sign_str, cj1, cj2

def push_msg(sign_str, cj1, cj2):
    now = datetime.datetime.now()
    bj = now + datetime.timedelta(hours=8)
    t = bj.strftime("%Y-%m-%d %H:%M:%S")

    desp = "------\n"
    desp += "### 🚁天翼云盘签到\n"
    desp += f"时间：{t}\n"
    desp += f"签到：{sign_str}\n"
    desp += f"抽奖1：{cj1}\n"
    desp += f"抽奖2：{cj2}\n"

    try:
        requests.post(
            'https://sc.ftqq.com/SCU74663T20ed2886a458ab9e3be21f3de4e8fd965e0b13de3ff1b.send',
            data={"text": f"天翼云盘签到 {t}", "desp": desp},
            timeout=10
        )
        print("📩 推送成功")
    except:
        print("📩 推送失败")

def main():
    # 读取 # 分隔账号
    ty_username = os.getenv("TY_USERNAME", "")
    ty_password = os.getenv("TY_PASSWORD", "")

    if not ty_username or not ty_password:
        print("❌ 未配置账号密码")
        return

    users = ty_username.split("#")
    pws = ty_password.split("#")

    if len(users) != len(pws):
        print("❌ 账号密码数量不一致")
        return

    print(f"📦 共 {len(users)} 个账号")

    for i in range(len(users)):
        u = users[i].strip()
        p = pws[i].strip()
        if not u or not p:
            continue

        s = requests.Session()
        if login(s, u, p):
            sign_str, cj1, cj2 = sign_and_draw(s)
            if i == len(users) - 1:
                push_msg(sign_str, cj1, cj2)

        time.sleep(random.randint(8, 18))

if __name__ == "__main__":
    main()
