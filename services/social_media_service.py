
import os
import shutil
import uuid
import yt_dlp
import glob

class SocialMediaExtractor:
    TEMP_DIR = "temp_video"

    @classmethod
    def download_video(cls, url: str) -> dict:
        """
        Downloads a video from a social media URL using yt-dlp.
        Returns a dictionary with the local file path and the video caption/description.
        """
        if not os.path.exists(cls.TEMP_DIR):
            os.makedirs(cls.TEMP_DIR)

        # Generate a unique ID for this download to avoid collisions
        unique_id = str(uuid.uuid4())
        output_template = f"{cls.TEMP_DIR}/{unique_id}.%(ext)s"

        ydl_opts = {
            'format': 'best[ext=mp4]',  # Prefer MP4 for Gemini compatibility
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            # We want just the video + metadata
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Handling filename scenarios (sometimes yt-dlp might change extensions)
                # We look specifically for the file we asked for.
                # 'prepare_filename' computes the expected filename.
                expected_filename = ydl.prepare_filename(info)
                
                # Check if it exists exactly or if we need to find it
                if not os.path.exists(expected_filename):
                    # Fallback search if extension changed?
                    # Generally with 'best[ext=mp4]' it should be mp4. 
                    # If conversion failed, it might be mkv/webm.
                    # But let's verify what happened.
                    raise FileNotFoundError(f"Expected file {expected_filename} not found.")

                caption = info.get('description') or info.get('title') or "No caption provided."
                
                return {
                    "video_path": expected_filename,
                    "caption": caption
                }

        except Exception as e:
            # Cleanup if partially failed?
            raise ValueError(f"Failed to download video: {str(e)}")

    @classmethod
    def cleanup(cls, video_path: str):
        """Removes the temporary video file."""
        if os.path.exists(video_path):
            os.remove(video_path)
