import tweepy, datetime, requests, pytz, re
from os import environ

fcst_x: str = environ["fcst_x"]
fcst_y: str = environ["fcst_y"]
serviceKey: str = environ["serviceKey"]


def weather_update(weather_msg: str) -> None:
    auth = tweepy.OAuthHandler(environ["consumer_key"], environ["consumer_secret"])
    auth.set_access_token(environ["access_token"], environ["access_token_secret"])
    api = tweepy.API(auth)
    api.update_status(status=weather_msg)

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
    if tup[0] == 0: return ""
    pty_str = {1: "비가", 2: "비와 눈이", 3: "눈이", 4: "소나기가"}
    return f"{day_str}은 {pty_str[tup[0]]} 옵니다. 강수확률은 {tup[1]}%이며, 강수량은 최대 {tup[2]}mm 입니다. "

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
     num1 = float(re.search(r'\d+\.\d+', num1_str).group())
     num2 = float(re.search(r'\d+\.\d+', num2_str).group())
     return num1_str if num1 > num2 else num2_str

def get_weather_msg() -> str:
    now_date = datetime.datetime.now(pytz.timezone('Asia/Seoul'))
    base_date: str = now_date.strftime('%Y%m%d')
    basedatetime: str = now_date.strftime('%Y%m%d%H%M')
            
    params_ver: dict = {'serviceKey': serviceKey, 
                        'numOfRows': '10', 
                        'pageNo': '1', 
                        'dataType': 'JSON', 
                        'ftype': 'SHRT', 
                        'basedatetime': basedatetime}

    version_list: list = get_json("getFcstVersion", params_ver)
    base_time: str = version_list[0]['version'][8:12]

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

    pour_info = [[0, 0, 0], [0, 0, 0]]
    temp_9 = [0, 0]
    temp_max = [0, 0]
    
    for item in get_json("getVilageFcst", params):

        day_diff = day_difference(item['fcstDate'], base_date)
        if day_diff == 2 or (is_now_before_than(base_time, "1200") and day_diff == 1): break

        if item['category'] == "PTY" and item['fcstValue'] != "0": # 오늘/내일 중 한번이라도 눈/비 소식이 있다면 무조건 그 정보를 기록한다.
            pour_info[day_diff][0] = item['fcstValue']

        if item['category'] == "POP" and item['fcstValue'] != "0": 
            pour_info[day_diff][1] = max_num(pour_info[day_diff][1], item['fcstValue'])

        if item['category'] == "PCP" and item['fcstValue'] != "강수없음": 
            pour_info[day_diff][2] = max_num(pour_info[day_diff][2], item['fcstValue'])

        if item['category'] == "SNO" and item['fcstValue'] != "적설없음": 
            pour_info[day_diff][2] = max_num(pour_info[day_diff][2], item['fcstValue'])

        if item['category'] == "TMX": 
            temp_max[day_diff] = item['fcstValue'] 

        if item['category'] == "TMP" and item['fcstTime'] == "0900":
            temp_9[day_diff] = item['fctValue']

    result = ["", ""]

    for i, day_str in enumerate(["오늘", "내일"]):
        if (i == 0 and is_now_before_than(base_time, "0900")) or i == 1:
            result[i] = f"{get_pty_str(day_str, pour_info[i])}{day_str}의 아침기온은 {temp_9[i]}℃이며, {day_str}의 낮 최고기온은 {temp_max[i]}℃ 입니다."
        else:
            result[i] = f"{get_pty_str(day_str, pour_info[i])}{day_str}의 낮 최고기온은 {temp_max[i]}℃ 입니다."

    if is_now_before_than(base_time, "1200"):
        return result[0]
    elif is_now_before_than(base_time, "1800") == False:
        return result[1]
    else:
        return ' '.join(result)

weather_msg = get_weather_msg()
weather_update(weather_msg)
