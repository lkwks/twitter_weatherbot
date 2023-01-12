import tweepy, datetime, requests, pytz, re
from os import environ

now_date = datetime.datetime.now(pytz.timezone('Asia/Seoul'))
pty_str = {"1": "비가", "2": "비와 눈이", "3": "눈이", "4": "소나기가"}
pty_str_np = {"1": "비", "2": "비와 눈", "3": "눈", "4": "소나기"}
params: dict = \
        {'serviceKey' : environ["serviceKey"],
             'pageNo' : '1', 
          'numOfRows' : '1000', 
           'dataType' : 'JSON', 
                 'nx' : environ["fcst_x"], 
                 'ny' : environ["fcst_y"] }


def tweet_update(msg: str) -> None:
    if msg == "": return
    auth = tweepy.OAuthHandler(environ["consumer_key"], environ["consumer_secret"])
    auth.set_access_token(environ["access_token"], environ["access_token_secret"])
    api = tweepy.API(auth)
    try:
        api.update_status(status=msg)
    except Exception as e:
        print(e)

def day_difference(date1: str, date2: str) -> bool:
    strp_date1 = datetime.datetime.strptime(date1, "%Y%m%d")
    strp_date2 = datetime.datetime.strptime(date2, "%Y%m%d")
    day_diff = strp_date1 - strp_date2
    return day_diff.days

def is_now_before_than(base_time: str, comp_time: str) -> bool:
    strp_now = datetime.datetime.strptime(base_time, "%H%M")
    strp_comp = datetime.datetime.strptime(comp_time, "%H%M")
    return strp_now < strp_comp

def add_mm(pcp: str) -> str:
    return f"{pcp}mm" if all(c.isnumeric() for c in pcp) else pcp

def get_pty_str(day_str: str, tup: dict) -> str:
    if "PTY" not in tup: return ""
    if "PCP" not in tup: # 9시 이전에 비/눈 그치면 그냥 강수량 정보 생략. 그 시간에 밖에 있는 경우 없으니까 안궁..
        return f"{day_str} 새벽 {pty_str_np[tup['PTY']]} 올 수 있습니다(강수확률 {tup['POP']}%). 9시 이전 잦아들 것으로 예상됩니다. "
    
    if int(tup["POP"]) >= 70:
        result = f"{day_str} {pty_str[tup['PTY']]} 옵니다({tup['max_time']}시 기준 강수확률 {tup['POP']}%)."
    else:
        result = f"{day_str} {pty_str_np[tup['PTY']]} 올 수 있습니다({tup['max_time']}시 기준 강수확률 {tup['POP']}%)."
    
    result = f"{result} 예상 {'강수' if tup['PTY'] != '3' else '적설'}량은 최대 {add_mm(tup['PCP'])} "
    if "end_time" in tup:
        return f"{result}이며, {tup['end_time']}시경 잦아들 것으로 예상됩니다. "
    else:
        return f"{result}입니다. "

def get_json(uri: str, params: dict) -> list:
    try: 
        response = requests.get("http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/" + uri, params=params)
        res_json: dict = response.json()
        if res_json['response']['header']['resultCode'] != "00":
            raise Exception(res_json['response']['header']['resultMsg'])
        res_item = res_json['response']['body']['items']['item']
    except Exception as e:
        print(e)
        raise
    return res_item

def max_num(num1_str: str, num2_str: str) -> str:
    try:
        num1 = float(re.search(r'[+-]?\d+\.\d+|[+-]?\d+', num1_str).group())
        num2 = float(re.search(r'[+-]?\d+\.\d+|[+-]?\d+', num2_str).group())
        return num1_str if num1 > num2 else num2_str
    except Exception as e:
        print(f"Invailid string in API: {e}")
        return "0"

def get_forecast_msg() -> str:
    
    params['base_date'] = now_date.strftime('%Y%m%d')
    
    time_num = ((now_date.hour * 60 + now_date.minute - 130)//180)*180+130 # API가 생성돼 있는 가장 최근 시간을 구하는 
    if time_num < 0: 
        time_num = 1390
        params['base_date'] = (now_date - datetime.timedelta(days=1)).strftime('%Y%m%d')

    base_hour, base_minute = divmod(time_num, 60)
    params['base_time'] = f"{base_hour:02d}{base_minute:02d}"
    
    json_list = get_json("getVilageFcst", params)
    
    # 오늘/내일 비눈소식, 강수확률, 강수량, 내일 아침기온, 내일 낮최고기온 정도만 추출하면 됨.
    # 현재 시간이 낮 12시 이전이라면 오늘꺼만 출력해도 됨. 
    # 현재 시간이 낮 12시부터 저녁 6시 사이라면 오늘, 내일 모두 출력해야.
    # 현재 시간이 저녁 6시 이후라면 내일꺼만 출력해야.
    # 강수형태: PTY. 비1, 비/눈2, 눈3, 소나기4
    # 강수확률: POP
    # 강수량: PCP, SNO
    # 낮최고기온: TMX

    pour_info = [{}, {}]
    temp_9 = ["-99", "-99"]
    temp_max = ["-99", "-99"]
    base_date = now_date.strftime('%Y%m%d')
    base_time = now_date.strftime('%H%M')
    
    for item in json_list:

        day_diff = day_difference(item['fcstDate'], base_date)
        if day_diff == 2 or (is_now_before_than(base_time, "1200") and day_diff == 1): break
            
        icat, ival, itime = item['category'], item['fcstValue'], int(item['fcstTime'][:2])
        
        if icat == "PTY" and ival != "0": # 오늘/내일 중 한번이라도 눈/비 소식이 있다면 무조건 그 정보를 기록한다.
            pour_info[day_diff]["PTY"] = ival if "PTY" not in pour_info[day_diff] else max_num(pour_info[day_diff]["PTY"], ival)

        if icat == "POP": # 강수확률
            if ("POP" not in pour_info[day_diff] or (int(ival) > pour_info[day_diff]["POP"] and pour_info[day_diff]["POP"] < 70)) and ival != "0":
                pour_info[day_diff]["POP"] = int(ival)
                pour_info[day_diff]["max_time"] = itime
                # pour_info[day_diff]["POP"]값이 70 미만이라면 그 중 최댓값을 갖는 시간대를 기록. 70이라면 그때 비/눈 오기 시작한다고 보고 더 이상 이 값을 갱신하지 않음.
            
        if (icat == "PCP" or icat == "SNO") and any(c.isnumeric() for c in ival): 
            if ("PCP" not in pour_info[day_diff] or ival == max_num(pour_info[day_diff]["PCP"], ival)) and itime >= 9: # 9시 이후 최대 강수 시간대
                pour_info[day_diff]["PCP"] = ival

        if icat == "TMP" and itime == 15: # 낮 최고기온
            temp_max[day_diff] = max_num(temp_max[day_diff], ival)

        if icat == "TMP" and itime == 9: # 아침기온
            temp_9[day_diff] = ival

            
    for item in json_list: # 비/눈이 오는 경우, 그치는 시간 정보를 찾 for loop를 추가로 수행
        day_diff = day_difference(item['fcstDate'], base_date)
        if day_diff == 2 or (is_now_before_than(base_time, "1200") and day_diff == 1): break
        if "end_time" in pour_info[day_diff] or "max_time" not in pour_info[day_diff]: continue
        
        icat, ival, itime = item['category'], item['fcstValue'], int(item['fcstTime'][:2])
        if icat == "POP" and itime > pour_info[day_diff]["max_time"] and int(ival) <= 30:
            pour_info[day_diff]["end_time"] = itime
            
            
    result = ["", ""]

    for i, day_str in enumerate(["오늘", "내일"]):
        if i == 0 and is_now_before_than(base_time, "0900") == False:
            result[i] = f"{get_pty_str(day_str, pour_info[i])}{day_str} 낮 최고기온은 {temp_max[i]}℃ 입니다."
        else:
            result[i] = f"{get_pty_str(day_str, pour_info[i])}{day_str}의 아침기온은 {temp_9[i]}℃이며, {day_str} 낮 최고기온은 {temp_max[i]}℃ 입니다."

    if is_now_before_than(base_time, "1200"):
        tweet_update(result[0])
    elif is_now_before_than(base_time, "1800") == False:
        tweet_update(result[1])
    else:
        tweet_update(' '.join(result))

    

def get_now_msg() -> None: # 현재 눈/비 오면 그 내용을 트윗으로 업데이트
    
    # 현재 분이 40분 넘으면 현재 시간 + 40분꺼 api 호출하면 됨.
    # 현재 분이 40분 안넘으면 바로 전 시간 + 40분꺼 api 호출하면 됨. 
    
    params['base_date'] = now_date.strftime('%Y%m%d')
    if now_date.minute >= 40:
        params['base_time'] = f"{now_date.hour:02d}00"
    elif now_date.hour > 0:
        params['base_time'] = f"{(now_date.hour-1):02d}00"
    else:
        params['base_time'] = "2300"
        params['base_date'] = (now_date - datetime.timedelta(days=1)).strftime('%Y%m%d')

    result = {}
    for item in get_json("getUltraSrtNcst", params):
        icat, ival = item['category'], item['obsrValue']
        if icat == "PTY" and int(ival) >= 1 and int(ival) <= 4: # 현재날씨
            result["PTY"] = ival
        if icat == "RN1":
            result["RN1"] = ival
    
    if "PTY" in result:
        tweet_update(f"현재 {pty_str[result['PTY']]} 옵니다. {'강수' if result['PTY'] != '3' else '적설'}량은 {add_mm(result['RN1'])} 입니다.")

        
def get_mart_msg() -> None: # 마트 휴일 정보를 트윗으로 업데이트
    date_obj = [now_date, now_date+datetime.timedelta(days=1)]
    womonth = [[False, "둘", False, "넷", False][(date_obj[i].day - 1) // 7] for i in range(2)]
    for i, day_str in enumerate(["오늘", "내일"]):
        if date_obj[i].weekday() == 6 and womonth[i]:
            tweet_update(f"{day_str}은 대형마트 휴무일인 이달 {womonth[i]}째주 일요일 입니다.")
        
        
get_now_msg()
get_forecast_msg()
get_mart_msg()
