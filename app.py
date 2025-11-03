from flask import Flask, render_template, request, jsonify,Response,stream_with_context
from datetime import datetime, timedelta
import requests
import wikipedia
import urllib.parse
import pandas as pd
import folium
from folium import IFrame

app = Flask(__name__)
# 获取鸟类图片的函数
def get_bird_image_wikipedia(bird_name):
    """
    使用 python-wikipedia 库获取鸟类的主图片。
    返回 (image_url, is_free)：
      - image_url: 图片 URL，如果找不到返回占位图
      - is_free: 是否是自由版权图片
    """
    placeholder = "https://via.placeholder.com/300x200.png?text=No+Image"
    
    try:
        wikipedia.set_lang("en")
        search_results = wikipedia.search(bird_name)
        if not search_results:
            return placeholder, False
        
        page_title = search_results[0]
        page = wikipedia.page(page_title)
        
        if page.images:
            img_url = page.images[0]
            is_free = True
            return img_url, is_free

    except wikipedia.exceptions.DisambiguationError as e:
        try:
            page = wikipedia.page(e.options[0])
            if page.images:
                return page.images[0], True
        except:
            pass
    except wikipedia.exceptions.PageError:
        return placeholder, False
    except Exception as e:
        print(f"[{bird_name}] 获取 Wikipedia 图片失败: {e}")
        return placeholder, False
    
    return placeholder, False

@app.route('/birdsound')
def bird_sound():
    species = request.args.get('name')
    print(f"[birdsound] 收到请求: {species}")  # ✅ 打印日志

    if not species:
        print("❌ 缺少物种名")
        return jsonify({'error': 'missing name'}), 400

    import urllib.parse
    q = urllib.parse.quote(species)
    url = f"https://xeno-canto.org/api/2/recordings?query={q}"
    print(f"[birdsound] 请求 URL: {url}")

    import requests
    try:
        r = requests.get(url, timeout=8)
        print(f"[birdsound] 状态码: {r.status_code}")
        data = r.json().get('recordings', [])
        print(f"[birdsound] 找到录音数: {len(data)}")

        if not data:
            return jsonify({'url': None})
        audio_url = data[0].get('file')
        if audio_url.startswith('//'):
            audio_url = 'https:' + audio_url
        print(f"[birdsound] 音频链接: {audio_url}")
        return jsonify({'url': f"/proxy_audio?url={urllib.parse.quote_plus(audio_url)}"})
    except Exception as e:
        print("⚠️ 出错：", e)
        return jsonify({'url': None})


@app.route('/proxy_audio')
def proxy_audio():
    """代理音频流，避免跨域"""
    url = request.args.get('url')
    if not url or 'xeno-canto.org' not in url:
        return "forbidden", 403
    remote = requests.get(url, stream=True, timeout=10)
    return Response(stream_with_context(remote.iter_content(1024)),
                    content_type=remote.headers.get('content-type', 'audio/mpeg'))
# 获取鸟类录音的函数
def get_bird_sound(species_name):
    """用 xeno-canto API 查找鸟类的录音 URL"""
    try:
        query = urllib.parse.quote(species_name)
        url = f"https://xeno-canto.org/api/2/recordings?query={query}"
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data.get("recordings"):
            return None
        # 取第一条录音
        file_url = data["recordings"][0].get("file")
        if file_url and file_url.startswith("//"):
            file_url = "https:" + file_url
        return file_url
    except Exception as e:
        print("获取录音出错:", e)
        return None

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
    days_back = int(request.form.get('days_back', 1))  # 用户选择查看哪一天的夜晚，默认昨天

    # 目标日期（UTC时间）
    target_date = datetime.utcnow().date() - timedelta(days=days_back)

    # 时间转换
    start_time = datetime.strptime(sleep_start, "%H:%M").replace(
        year=target_date.year, month=target_date.month, day=target_date.day
    )
    end_time = datetime.strptime(sleep_end, "%H:%M").replace(
        year=target_date.year, month=target_date.month, day=target_date.day
    )
    if end_time <= start_time:
        end_time += timedelta(days=1)  # 跨天

    # -------- eBird 数据请求 --------
    API_KEY = "sgqiqntt0ema"
    REGION = "US-NY"
    BACK_DAYS = days_back + 1  # 请求过去几天，确保获取目标日期
    MAX_RESULTS = 500

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
    # 过滤在 start_time 和 end_time 之间的数据
    df = df[(df['obsDt'] >= start_time) & (df['obsDt'] <= end_time)]

    if df.empty:
        return "When you sleep, the birds are resting too 💤"

    # -------- 地图绘制 --------
    df['howMany'] = df['howMany'].fillna(1)
    m = folium.Map(tiles='CartoDB dark_matter')

    from flask import render_template_string

    for _, row in df.iterrows():
        species = row['comName']
        species_id = species.replace(" ", "_").replace("'", "")
        img_url, is_free = get_bird_image_wikipedia(species)
        species_js = species.replace("'", "\\'")  # JS 转义

        # 读取模板并渲染
        with open("templates/bird_card.html") as f:
            template = f.read()
        popup_html = render_template_string(template,
                                        img_url=img_url,
                                        species=species,
                                        locName=row['locName'],
                                        howMany=row['howMany'],
                                        obsDt=row['obsDt'],
                                        species_js=species_js)

        iframe = IFrame(popup_html, width=250, height=320)  # 高度调整为卡片高度
        popup = folium.Popup(iframe, max_width=250)

        folium.CircleMarker(
            location=[row['lat'], row['lng']],
            radius=4,
            color='orange',
            fill=True,
            fill_opacity=0.7,
            popup=popup
        ).add_to(m)

    # 自动调整地图视野
    if not df.empty:
        lats_lngs = df[['lat', 'lng']].values.tolist()
        m.fit_bounds(lats_lngs)

    map_html = m._repr_html_()
    return render_template('index.html', map_html=map_html)


if __name__ == '__main__':
    app.run(debug=True)