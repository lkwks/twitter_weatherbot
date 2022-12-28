import tweepy, datetime, requests, pytz, re
from os import environ

fcst_x: str = environ["fcst_x"]
fcst_y: str = environ["fcst_y"]
serviceKey: str = environ["serviceKey"]

now_date = datetime.datetime.now(pytz.timezone('Asia/Seoul'))
pty_str = {"1": "비가", "2": "비와 눈이", "3": "눈이", "4": "소나기가"}
pty_str_np = {"1": "비", "2": "비와 눈", "3": "눈", "4": "소나기"}


def weather_update(weather_msg: str) -> None:
    if weather_msg == "": return
    auth = tweepy.OAuthHandler(environ["consumer_key"], environ["consumer_secret"])
    auth.set_access_token(environ["access_token"], environ["access_token_secret"])
    api = tweepy.API(auth)
    try:
        api.update_status(status=weather_msg)
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

def get_pty_str(day_str: str, tup: list) -> str:
    if tup[0] == "0": return ""
    
    if int(tup[1]) >= 70:
        result = f"{day_str}은 {pty_str[tup[0]]} 옵니다({tup[3]}시 기준 강수확률 {tup[1]}%)."
    else:
        result = f"{day_str} 강수확률({pty_str_np[tup[0]]}) 있습니다({tup[3]}시 기준 {tup[1]}%)."
        
    return f"{result} 예상 {'강수' if tup[0] != '3' else '적설'}량은 최대 {tup[2]} 이며, {tup[4]}시경 잦아들 것으로 예상됩니다. "

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

def get_msg() -> str:
    
    base_date: str = now_date.strftime('%Y%m%d')

    n_hour, n_min = now_date.hour, now_date.minute
    time_num = ((n_hour * 60 + n_min - 130)//180)*180+130

    if time_num < 0: 
        time_num = 1390
        base_date = (now_date - datetime.timedelta(days=1)).strftime('%Y%m%d')

    base_hour, base_minute = divmod(time_num, 60)
    base_time = f"{base_hour:02d}{base_minute:02d}"

    params: dict = {'serviceKey' : serviceKey,
             'pageNo' : '1', 
          'numOfRows' : '1000', 
           'dataType' : 'JSON', 
          'base_date' : base_date,
          'base_time' : base_time,
                 'nx' : fcst_x, 
                 'ny' : fcst_y }
    
    # 오늘/내일 비눈소식, 강수확률, 강수량, 내일 아침기온, 내일 낮최고기온 정도만 추출하면 됨.
    # 현재 시간이 낮 12시 이전이라면 오늘꺼만 출력해도 됨. 
    # 현재 시간이 낮 12시부터 저녁 6시 사이라면 오늘, 내일 모두 출력해야.
    # 현재 시간이 저녁 6시 이후라면 내일꺼만 출력해야.
    # 강수형태: PTY. 비1, 비/눈2, 눈3, 소나기4
    # 강수확률: POP
    # 강수량: PCP, SNO
    # 낮최고기온: TMX

    pour_info = [["0", "-99", "-99", "", ""], ["0", "-99", "-99", "", ""]]
    temp_9 = ["-99", "-99"]
    temp_max = ["-99", "-99"]
    base_date = now_date.strftime('%Y%m%d')
    base_time = now_date.strftime('%H%M')
    now_weather_msg = ""
    now_weather_checked = False
    
    for item in get_json("getVilageFcst", params):

        day_diff = day_difference(item['fcstDate'], base_date)
        if day_diff == 2 or (is_now_before_than(base_time, "1200") and day_diff == 1): break

        if item['category'] == "PTY" and item['fcstValue'] != "0": # 오늘/내일 중 한번이라도 눈/비 소식이 있다면 무조건 그 정보를 기록한다.
            pour_info[day_diff][0] = max_num(pour_info[day_diff][0], item['fcstValue'])

        if item['category'] == "POP" and item['fcstValue'] != "0": 
            pour_info[day_diff][1] = max_num(pour_info[day_diff][1], item['fcstValue'])
            if pour_info[day_diff][3] != "" and int(item['fcstTime'][:2]) > int(pour_info[day_diff][3]) and pour_info[day_diff][4] == "" and int(item['fcstValue']) < 30:
                pour_info[day_diff][4] = item['fcstTime'][:2]

        if (item['category'] == "PCP" and item['fcstValue'] != "강수없음") or (item['category'] == "SNO" and item['fcstValue'] != "적설없음"): 
            if item['fcstValue'] == max_num(pour_info[day_diff][2], item['fcstValue']) and int(item['fcstTime'][:2]) >= 9:
                pour_info[day_diff][2] = item['fcstValue']
                pour_info[day_diff][3] = item['fcstTime'][:2]

        if item['category'] == "PTY" and now_weather_checked == False:
            if item['fcstValue'] != "0":
                now_weather_msg = f"현재 {pty_str[item['fcstValue']]} 옵니다."
            now_weather_checked = True 

        if item['category'] == "TMP" and item['fcstTime'] == "1500":
            temp_max[day_diff] = max_num(temp_max[day_diff], item['fcstValue'])

        if item['category'] == "TMP" and item['fcstTime'] == "0900":
            temp_9[day_diff] = item['fcstValue']

    result = ["", ""]

    for i, day_str in enumerate(["오늘", "내일"]):
        if (i == 0 and is_now_before_than(base_time, "0900")) or i == 1:
            result[i] = f"{get_pty_str(day_str, pour_info[i])}{day_str}의 아침기온은 {temp_9[i]}℃이며, {day_str} 낮 최고기온은 {temp_max[i]}℃ 입니다."
        else:
            result[i] = f"{get_pty_str(day_str, pour_info[i])}{day_str}의 낮 최고기온은 {temp_max[i]}℃ 입니다."

    forecast_msg = ""
    if is_now_before_than(base_time, "1200"):
        forecast_msg = result[0]
    elif is_now_before_than(base_time, "1800") == False:
        forecast_msg = result[1]
    else:
        forecast_msg = ' '.join(result)

    weather_update(now_weather_msg)
    weather_update(forecast_msg)


get_msg()
