from flask import Flask, render_template, request
from datetime import datetime, timedelta
import requests
import pandas as pd
import folium

app = Flask(__name__)

@app.route('/')
def show_map():
    # -------- eBird 用户配置 --------      
    API_KEY = "sgqiqntt0ema"
    REGION = "US-NY"          # 美国纽约州
    BACK_DAYS = 7             # 最近 7 天的观测
    MAX_RESULTS = 200         # 最多显示 200 条

    url = f"https://api.ebird.org/v2/data/obs/{REGION}/recent"
    params = {"back": BACK_DAYS, "maxResults": MAX_RESULTS}
    headers = {"x-ebirdapitoken": API_KEY}

    # -------- 请求数据 --------
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        return f"下载失败，状态码: {response.status_code}"

    data = response.json()
    df = pd.DataFrame(data)
    if df.empty:
        return "未获取到观测数据。"

    # -------- 数据整理 --------
    df['howMany'] = df['howMany'].fillna(1)
    df['comName'] = df['comName'].fillna('Unknown species')

    # -------- 绘制地图 --------
    center_lat = df['lat'].mean()
    center_lon = df['lng'].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles='CartoDB dark_matter')

    # 在地图上绘制每个观测点
    for _, row in df.iterrows():
        popup_text = f"""
        <b>{row['comName']}</b><br>
        {row['locName']}<br>
        数量: {row['howMany']}<br>
        时间: {row['obsDt']}
        """
        folium.CircleMarker(
            location=[row['lat'], row['lng']],
            radius=4,
            color='lightblue',
            fill=True,
            fill_opacity=0.7,
            popup=popup_text
        ).add_to(m)

    # -------- 地图转 HTML --------
    map_html = m._repr_html_()

    # -------- 渲染模板 --------
    return render_template('index.html', map_html=map_html)


@app.route('/sleep', methods=['POST'])
def sleep_birds():
    # 获取表单数据
    sleep_start = request.form['sleep_start']
    sleep_end = request.form['sleep_end']

    # 时间格式转换
    now = datetime.utcnow()
    start_time = datetime.strptime(sleep_start, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
    end_time = datetime.strptime(sleep_end, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
    if end_time < start_time:
        end_time += timedelta(days=1)

    # -------- eBird 数据请求 --------
    API_KEY = "sgqiqntt0ema"
    REGION = "US-NY"
    BACK_DAYS = 1
    MAX_RESULTS = 300

    url = f"https://api.ebird.org/v2/data/obs/{REGION}/recent"
    params = {"back": BACK_DAYS, "maxResults": MAX_RESULTS}
    headers = {"x-ebirdapitoken": API_KEY}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        return f"下载失败，状态码: {response.status_code}"

    data = response.json()
    df = pd.DataFrame(data)
    if df.empty:
        return "没有找到任何观测数据。"

    # -------- 时间过滤 --------
    df['obsDt'] = pd.to_datetime(df['obsDt'])
    df = df[(df['obsDt'].dt.time >= start_time.time()) | (df['obsDt'].dt.time <= end_time.time())]

    if df.empty:
        return "你睡觉时，鸟儿们也在休息 💤"

    # -------- 地图绘制 --------
    df['howMany'] = df['howMany'].fillna(1)
    m = folium.Map(location=[df['lat'].mean(), df['lng'].mean()], zoom_start=6, tiles='CartoDB dark_matter')

    for _, row in df.iterrows():
        popup_text = f"<b>{row['comName']}</b><br>{row['locName']}<br>数量: {row['howMany']}<br>时间: {row['obsDt']}"
        folium.CircleMarker(
            location=[row['lat'], row['lng']],
            radius=4,
            color='orange',
            fill=True,
            fill_opacity=0.7,
            popup=popup_text
        ).add_to(m)

    map_html = m._repr_html_()
    return render_template('index.html', map_html=map_html)


if __name__ == '__main__':
    app.run(debug=True)