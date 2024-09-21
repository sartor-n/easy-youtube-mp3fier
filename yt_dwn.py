import streamlit as st
from pytube import YouTube, Playlist
from moviepy.editor import AudioFileClip
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, ID3NoHeaderError
import os
import concurrent.futures
import zipfile
import tempfile
from io import BytesIO

# Function to download audio and set metadata
def download_audio(url, output_folder):
    try:
        # Create a YouTube object
        yt = YouTube(url)

        # Get the highest quality audio stream
        audio_stream = yt.streams.get_audio_only()

        if not audio_stream:
            raise Exception("No audio stream available for this video")

        temp_folder = os.path.join(output_folder, "temp")

        # Download the audio file
        audio_file_path = audio_stream.download(output_path=temp_folder, filename=f"{yt.title}.mp4", skip_existing=True)

        # Convert the downloaded file to mp3 and set metadata
        audio_clip = AudioFileClip(audio_file_path)
        mp3_file_path = os.path.join(output_folder, f"{yt.title}.mp3")
        audio_clip.write_audiofile(mp3_file_path, codec="mp3")

        # Remove the original .mp4 file to save space
        os.remove(audio_file_path)

        # Set MP3 metadata using mutagen
        try:
            audio = MP3(mp3_file_path, ID3=ID3)
        except ID3NoHeaderError:
            audio = MP3(mp3_file_path)
            audio.add_tags()

        audio.tags.add(TIT2(encoding=3, text=yt.title))
        audio.tags.add(TPE1(encoding=3, text=yt.author))
        audio.save()

        return f"Downloaded and converted: {yt.title} by {yt.author}, Bitrate: {audio_stream.abr}"
    except Exception as e:
        return f"Failed to download {url}: {e}"

# Function to get all video URLs from a list of playlist/video URLs
def get_all_video_urls(urls_or_playlists):
    video_urls = []
    for url in urls_or_playlists:
        if "playlist" in url:
            try:
                playlist = Playlist(url)
                video_urls.extend(playlist.video_urls)
            except Exception as e:
                st.error(f"Failed to process playlist {url}: {e}")
        else:
            video_urls.append(url)
    return video_urls

# Function to download and process videos
def process_videos(urls_or_playlists):
    output_folder = tempfile.mkdtemp()
    video_urls = get_all_video_urls(urls_or_playlists)
    total_videos = len(video_urls)
    progress_bar = st.progress(0)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(download_audio, url, output_folder): url for url in video_urls}
        for idx, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            results.append(result)
            progress_bar.progress((idx + 1) / total_videos)

    # Create a zip file of the output folder
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for foldername, subfolders, filenames in os.walk(output_folder):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                zip_file.write(file_path, os.path.relpath(file_path, output_folder))

    return results, zip_buffer.getvalue()

# Streamlit UI
st.title("YouTube to MP3 Downloader")
st.write("Enter a list of YouTube URLs (videos or playlists), separated by new lines, commas, or tabs.")

urls_input = st.text_area("YouTube URLs", height=150)
start_download = st.button("Start Download")

st.text

if start_download and urls_input:
    urls_or_playlists = [url.strip() for url in urls_input.split() if url.strip()]
    with st.spinner("Downloading and processing videos..."):
        download_results, zip_data = process_videos(urls_or_playlists)

    # Show the results of each download
    for result in download_results:
        st.write(result)

    # Provide a link to download the zip file
    st.success("Download completed!")
    st.download_button(
        label="Download All MP3s",
        data=zip_data,
        file_name="youtube_mp3s.zip",
        mime="application/zip"
    )
