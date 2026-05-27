#!/usr/bin/python3
# -*- coding: utf-8 -*-
import requests
import time
import datetime
import re
import rsa
import json
import base64
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
    max_retry = 2  # 失败自动重试2次
    for retry in range(max_retry):
        try:
            # 1. 先访问主页初始化会话，避免被重定向到免密页
            session.get("https://m.cloud.189.cn/", timeout=15, allow_redirects=True)
            time.sleep(random.uniform(1, 2))

            # 2. 访问目标登录页，关闭重定向自动跟随，精准抓参数
            login_url = (
                "https://m.cloud.189.cn/udb/udb_login.jsp"
                "?pageId=1&pageKey=default&clientType=wap"
                "&redirectURL=https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html"
            )
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
                "Referer": "https://m.cloud.189.cn/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip, deflate, br"
            }
            r = session.get(login_url, headers=headers, timeout=15, allow_redirects=True)
            time.sleep(random.uniform(0.8, 1.5))

            # 3. 新版正则：从JS全局变量里抓paramId和j_rsaKey（核心修复！）
            paramId = re.search(r'paramId\s*=\s*"([^"]+)"', r.text)
            j_rsaKey = re.search(r'j_rsaKey\s*=\s*"([^"]+)"', r.text)

            if not paramId or not j_rsaKey:
                print(f"⚠️ 第{retry+1}次重试：未找到参数，页面内容长度：{len(r.text)}")
                if retry == max_retry - 1:
                    print("❌ 最终失败：未找到paramId/j_rsaKey")
                    return False
                time.sleep(3)
                continue

            paramId = paramId.group(1)
            j_rsaKey = j_rsaKey.group(1)
            print(f"✅ 成功抓取参数：paramId={paramId[:10]}...")

            # 4. 加密账号密码
            user_enc = rsa_encode(j_rsaKey, username)
            pwd_enc = rsa_encode(j_rsaKey, password)

            # 5. 提交登录请求
            post_url = "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do"
            post_headers = {
                "User-Agent": headers["User-Agent"],
                "Referer": login_url,
                "Origin": "https://open.e.189.cn",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
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
                "paramId": paramId
            }

            r = session.post(post_url, data=data, headers=post_headers, timeout=15)
            res = r.json()

            if res.get("result") != 0:
                print(f"❌ 登录失败：{res.get('msg')}")
                return False

            # 6. 完成登录态跳转
            session.get(res["toUrl"], timeout=15)
            print(f"✅ {mask_phone(username)} 登录成功")
            return True

        except Exception as e:
            print(f"⚠️ 第{retry+1}次登录异常：{str(e)}")
            if retry == max_retry - 1:
                print("❌ 最终登录异常")
                return False
            time.sleep(3)
            continue

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
        sign_str = f"✅ 签到成功，获得{bonus}M" if resp.get("isSign") == "false" else f"⏳ 已签到，本次{bonus}M"
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
        cj2 = d2.get("description", "抽奖失效") if "errorCode" not in d2 else "抽奖异常"
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

        time.sleep(random.randint(10, 20))

if __name__ == "__main__":
    main()
