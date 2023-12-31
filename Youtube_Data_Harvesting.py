from googleapiclient.discovery import build
import pymongo
import psycopg2
import streamlit as st
import pandas as pd
import isodate
from pymongo import collection

# Initialize YouTube API client
Api_key = "your Api Key"
youtube = build('youtube', 'v3', developerKey=Api_key)

# create a new client and connect to the server
client = pymongo.MongoClient("Enter your MongoDB server link")

# create database
db = client["Source_data"]

# Connect to Postgres
data = psycopg2.connect(host='localhost', user='postgres', password='your_password', database='enter new Db')
cursor = data.cursor()

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# channel details
def fetch_channel(youtube, channel_id):
    request = youtube.channels().list(
        part="snippet,contentDetails,statistics",
        id=channel_id)

    response = request.execute()

    for item in response['items']:
        data = {'channel_Name': item['snippet']['title'],
                'channel_Id': item['id'],
                'subscribers': item['statistics']['subscriberCount'],
                'views': item['statistics']['viewCount'],
                'total_Videos': item['statistics']['videoCount'],
                'playlist_Id': item['contentDetails']['relatedPlaylists']['uploads'],
                'channel_Description': item['snippet']['description']
                }

    return data


# playlist details
def get_playlist_details(youtube, channel_id):
    request = youtube.playlists().list(
        part="snippet,contentDetails",
        channelId=channel_id,
        maxResults=20)
    response = request.execute()
    all_data = []
    for item in response['items']:
        data = {'PlaylistId': item['id'],
                'Title': item['snippet']['title'],
                'ChannelId': item['snippet']['channelId'],
                'ChannelName': item['snippet']['channelTitle'],
                'PublishedAt': item['snippet']['publishedAt'],
                'VideoCount': item['contentDetails']['itemCount']
                }
        all_data.append(data)

        next_page_token = response.get('nextpagetoken')
        # more_pages = True

        while next_page_token is not None:

            request = youtube.playlists().list(
                part="snippet,contentDetails",
                channelId=channel_id,
                maxResults=20)
            response = request.execute()

            for item in response['items']:
                data = {'PlaylistId': item['id'],
                        'Title': item['snippet']['title'],
                        'ChannelId': item['snippet']['channelId'],
                        'ChannelName': item['snippet']['channelTitle'],
                        'PublishedAt': item['snippet']['publishedAt'],
                        'VideoCount': item['contentDetails']['itemCount']
                        }
                all_data.append(data)

            next_page_token = response.get('nextpagetoken')
    return all_data


# Video Id details:
def get_videoIds(youtube, upload_id):
    request = youtube.playlistItems().list(
        part="contentDetails",
        playlistId=upload_id,
        maxResults=20
    )
    response = request.execute()
    video_ids = []

    for i in range(len(response['items'])):
        video_ids.append(response['items'][i]['contentDetails']['videoId'])

    next_page_token = response.get('nextPageToken')
    more_pages = True

    while more_pages:
        if next_page_token is None:
            more_pages = False
        else:
            request = youtube.playlistItems().list(
                part="contentDetails",
                playlistId=upload_id,
                maxResults=20,
                pageToken=next_page_token
            )
            response = request.execute()

            for i in range(len(response['items'])):
                video_ids.append(response['items'][i]['contentDetails']['videoId'])

            next_page_token = response.get('nextPageToken')

    return video_ids

#duration format
def format_duration(duration):
    duration_obj = isodate.parse_duration(duration)
    hours = duration_obj.total_seconds() // 3600
    minutes = (duration_obj.total_seconds() % 3600) // 60
    seconds = duration_obj.total_seconds() % 60
    formatted_duration = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    return formatted_duration


#video detalis
def get_videoDetails(youtube, video_id):
    request = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=video_id)
    response = request.execute()

    for video in response['items']:
        stats_needed = {'snippet': ['channelTitle', 'title', 'description', 'tags', 'publishedAt', 'channelId'],
                        'statistics': ['viewCount', 'likeCount', 'favouriteCount', 'commentCount'],
                        'contentDetails': ['duration', 'definition', 'caption']}
        video_info = {}
        video_info['video_id'] = video['id']

        for key in stats_needed.keys():
            for value in stats_needed[key]:
                try:
                    if key == 'contentDetails' and value == 'duration':
                        video_info[value] = format_duration(video[key][value])
                    else:
                        video_info[value] = video[key][value]
                except KeyError:
                    video_info[value] = None

    return video_info


# comment details:
def comment_details(youtube, video_id):
    all_comments = []
    try:
        request = youtube.commentThreads().list(
            part="snippet,replies",
            videoId=video_id
        )
        response = request.execute()

        for item in response['items']:
            data = {'comment_id': item['snippet']['topLevelComment']['id'],
                    'comment_txt': item['snippet']['topLevelComment']['snippet']['textOriginal'],
                    'videoId': item['snippet']['topLevelComment']["snippet"]['videoId'],
                    'author_name': item['snippet']['topLevelComment']['snippet']['authorDisplayName'],
                    'published_at': item['snippet']['topLevelComment']['snippet']['publishedAt'],
                    }

            all_comments.append(data)

    except:

        return 'Could not get comments for video '

    return all_comments

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

#CREATING DATABASE IN MONGODB:
collection = db["Youtube_Channels"]
@st.cache_data
#Storeing data
def channel_Details(channel_id):
    channel = fetch_channel(youtube, channel_id)
    collection = db["YoutubeChannels"]
    collection.insert_one(channel)

    playlist = get_playlist_details(youtube, channel_id)
    collection = db["Playlists"]
    for i in playlist:
        collection.insert_one(i)

    upload = channel.get('playlist_Id')
    videos = get_videoIds(youtube, upload)
    for i in videos:
        videoDetail = get_videoDetails(youtube, i)
        collection = db["Videos"]
        collection.insert_one(videoDetail)

        comment = comment_details(youtube, i)
        if comment != 'Could not get comments for video ':
            for i in comment:
                collection = db["Comments"]
                collection.insert_one(i)
    return ("Process " + channel_id + " Done")

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

#creating table:
def youtube_channel_table():
    try:
        cursor.execute('''create table if not exists youtube_channel(channel_Name varchar(80),
                          channel_Id varchar(80) primary key,
                          subscribers bigint,
                          views bigint,
                          total_Videos int,
                          playlist_Id varchar(80),
                          channel_Description text)''')
        data.commit()
    except:
        data.rollback()

    collection1 = db["YoutubeChannels"]
    documents1 = collection1.find()
    data1 = list(documents1)
    df1 = pd.DataFrame(data1)

    try:
        for _, row in df1.iterrows():
            insert_query = '''
                INSERT INTO youtube_channel (channel_Name, channel_Id, subscribers,
                       views, total_Videos, playlist_Id, channel_Description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)

            '''
            values = (
                row['channel_Name'],
                row['channel_Id'],
                row['subscribers'],
                row['views'],
                row['total_Videos'],
                row['playlist_Id'],
                row['channel_Description']
            )
            try:
                cursor.execute(insert_query, values)
                data.commit()
            except:
                data.rollback()
    except:
        st.write("Values already exists in the Youtube Channel table")


def playlist_table():
    try:
        cursor.execute('''create table if not exists playlists(PlaylistId varchar(80) primary key,
                          Title varchar(80),
                          ChannelId varchar(80),
                          ChannelName varchar(80),
                          PublishedAt timestamp,
                          VideoCount int )''')
        data.commit()
    except:
        data.rollback()

    collection2 = db["Playlists"]
    documents2 = collection2.find()
    data2 = list(documents2)
    df2 = pd.DataFrame(data2)

    try:
        for _, row in df2.iterrows():
            insert_query = '''
                INSERT INTO playlists (PlaylistId, Title, ChannelId, ChannelName,
                       PublishedAt, VideoCount)
                VALUES (%s, %s, %s, %s, %s, %s)

            '''
            values = (
                row['PlaylistId'],
                row['Title'],
                row['ChannelId'],
                row['ChannelName'],
                row['PublishedAt'],
                row['VideoCount']

            )
            try:
                cursor.execute(insert_query, values)
                data.commit()
            except:
                data.rollback()
    except:
        st.write("Values already exists in the Playlists table")


def videos_table():
    try:
        cursor.execute('''create table if not exists videos(video_id varchar(80) primary key,
                          channelTitle varchar(200),
                          title text,
                          description text,
                          tags text,
                          publishedAt timestamp,
                          channelId varchar(80),
                          viewCount bigint,
                          likeCount bigint,
                          favouriteCount int,
                          commentCount int,
                          duration interval,
                          definition varchar(10),
                          caption varchar(10) )''')

        data.commit()
    except:
        data.rollback()

    collection3 = db["Videos"]
    documents3 = collection3.find()
    data3 = list(documents3)
    df3 = pd.DataFrame(data3)

    try:
        for _, row in df3.iterrows():
            insert_query = '''
                INSERT INTO videos (video_id, channelTitle, title, description, tags,
                       publishedAt, channelId, viewCount, likeCount, favouriteCount, commentCount, duration,
                       definition, caption)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)

            '''
            values = (
                row['video_id'],
                row['channelTitle'],
                row['title'],
                row['description'],
                row['tags'],
                row['publishedAt'],
                row['channelId'],
                row['viewCount'],
                row['likeCount'],
                row['favouriteCount'],
                row['commentCount'],
                row['duration'],
                row['definition'],
                row['caption']

            )
            try:
                cursor.execute(insert_query, values)
                data.commit()
            except:
                data.rollback()
    except:
        st.write("Values already exists in the Videos table")


def comment_table():
    try:
        cursor.execute('''create table if not exists comments(comment_id varchar(80) primary key,
                          comment_txt text,
                          videoId varchar(80),
                          published_at timestamp)''')
        data.commit()
    except:
        data.rollback()

    collection4 = db["Comments"]
    documents4 = collection4.find()
    data4 = list(documents4)
    df4 = pd.DataFrame(data4)

    try:
        for _, row in df4.iterrows():
            insert_query = '''
                INSERT INTO comments (comment_id, comment_txt, videoId,
                       published_at)
                VALUES (%s, %s, %s, %s)

            '''
            values = (
                row['comment_id'],
                row['comment_txt'],
                row['videoId'],
                row['published_at']

            )
            try:
                cursor.execute(insert_query, values)
                data.commit()
            except:
                data.rollback()
    except:
        st.write("Values already exists in the Comments table")

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def tables():
    youtube_channel_table()
    playlist_table()
    videos_table()
    comment_table()
    return ("Migration Done")

#Displaying method:
def display_youtube_channel():
    db = client["Source_data"]
    collection = db["YoutubeChannels"]
    a = list(collection.find())
    a = st.dataframe(a)
    return a

def display_playlist():
    db = client["Source_data"]
    collection = db["Playlists"]
    b = list(collection.find())
    b = st.dataframe(b)
    return b

def display_videos():
    db = client["Source_data"]
    collection = db["Videos"]
    c = list(collection.find())
    c = st.dataframe(c)
    return c

def display_comments():
    db = client["Source_data"]
    collection = db["Comments"]
    d = list(collection.find())
    d = st.dataframe(d)
    return d

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

#Questions
def one():
    cursor.execute('''select title, channeltitle from videos;''')
    data.commit()
    q1 = cursor.fetchall()
    st.write(pd.DataFrame(q1, columns=['Videos', 'Channel Name']))

def two():
    cursor.execute('''select channel_Name , total_Videos from youtube_channel order by total_Videos desc limit 1;''')
    data.commit()
    q2 = cursor.fetchall()
    st.write(pd.DataFrame(q2, columns=['Channel Name', 'Video Count']))

def three():
    cursor.execute( '''select title , channelTitle , viewCount from videos where viewCount is not null order by viewCount desc limit 10;''')
    data.commit()
    q3 = cursor.fetchall()
    st.write(pd.DataFrame(q3, columns=['Video Title', 'Channel Name', 'Views Count']))

def four():
    cursor.execute('''select title , channelTitle , commentCount from videos where commentCount is not null;''')
    data.commit()
    q4 = cursor.fetchall()
    st.write(pd.DataFrame(q4, columns=['Video Title', 'Channel Name', 'Comments Count']))

def five():
    cursor.execute(
        '''select title , channelTitle , likeCount from videos where likeCount is not null order by likeCount desc;''')
    data.commit()
    q5 = cursor.fetchall()
    st.write(pd.DataFrame(q5, columns=['Video Title', 'Channel Name', 'Likes']))

def six():
    cursor.execute('''select title , channelTitle , likeCount from videos;''')
    data.commit()
    q6 = cursor.fetchall()
    st.write(pd.DataFrame(q6, columns=['Video Title', 'Channel Name', 'Likes']))

def seven():
    cursor.execute('''select channel_Name , views from youtube_channel;''')
    data.commit()
    q7 = cursor.fetchall()
    st.write(pd.DataFrame(q7, columns=['Channel Name', 'Channel Views']))

def eight():
    cursor.execute('''select channelTitle , title , publishedAt from videos where extract(year from publishedAt) = 2022;''')
    data.commit()
    q8 = cursor.fetchall()
    st.write(pd.DataFrame(q8, columns=['Channel Name', 'Video Title', 'Released On']))

def ten():
    cursor.execute('''select title , channelTitle , commentCount from videos where commentCount is not null order by commentCount desc;''')
    data.commit()
    q10 = cursor.fetchall()
    st.write(pd.DataFrame(q10, columns=['Video Title', 'Channel Name', 'Comments Count']))

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Using STREAMLIT:
st.title(':violet[Youtube Data Harvesting]:sparkles:')#title
st.subheader(':red[Get Data]:fire:')

channel_id = st.text_input("Enter channel id")
channels = channel_id.split(',')
channels = [ch.strip() for ch in channels if ch]

if st.button("Fetch and Store Data"):#using button format to get data
    for channel in channels:
        query = {'channel_Id': channel}
        document = collection.find_one(query)
        if document:
            st.write("Channel Details already exists")
        else:
            output = channel_Details(channel)
            st.write(output)

st.write("Click here to Migrate Data")
if st.button("Migrate"):
    display = tables()
    st.write(display)
frames = st.selectbox(
    "Select Table",
    ('None', 'Youtube Channels', 'Playlists', 'Videos', 'Comments'))

st.write('You selected: ', frames)

if frames == 'None':
    st.write("Select table")
elif frames == 'Youtube Channels':
    display_youtube_channel()
elif frames == 'Playlists':
    display_playlist()
elif frames == 'Videos':
    display_videos()
elif frames == 'Comments':
    display_comments()

query = st.selectbox(
    "Channel Analysis",
    ('None', 'Names of all the videos and their corresponding channels', 'Channel having the most number of videos',
     'Top 10 most viewed videos', 'Number of Comments in each video', 'Videos with Highest Likes',
     'Likes of all videos',
     'Total number of views for each channel', 'Names of the channels that have published videos in the year 2022',
     'Videos with highest number of comments'))

st.write('You selected: ', query)

if query == 'None':
    st.write("Select table")
elif query == 'Names of all the videos and their corresponding channels':
    one()
elif query == 'Channel having the most number of videos':
    two()
elif query == 'Top 10 most viewed videos':
    three()
elif query == 'Number of Comments in each video':
    four()
elif query == 'Videos with Highest Likes':
    five()
elif query == 'Likes of all videos':
    six()
elif query == 'Total number of views for each channel':
    seven()
elif query == 'Names of the channels that have published videos in the year 2022':
    eight()
elif query == 'Videos with highest number of comments':
    ten()


#================================================END==========================================================================================#
