import os
import io
from google.cloud import texttospeech

class PodcastGenerator:
    def __init__(self, storage_provider=None):
        """Initializes the TextToSpeech client."""
        self.storage = storage_provider
        # This relies on GOOGLE_APPLICATION_CREDENTIALS being set in env
        # or gcloud authed in local environment.
        try:
            self.client = texttospeech.TextToSpeechClient()
        except Exception as e:
            print(f"Warning: Failed to initialize TTS client. {e}")
            self.client = None

    def generate_audio(self, script_json: list) -> bytes:
        """
        Synthesizes audio for the given script JSON.
        Returns the combined MP3 bytes.
        """
        if not self.client:
            raise Exception("TTS Client not initialized. Check credentials.")

        combined_audio = io.BytesIO()

        # Voice Configuration
        # "Journey" voices are high quality, conversational neural voices.
        voices = {
            "A": texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Journey-D" # Male-sounding, conversational
            ),
            "B": texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Journey-F" # Female-sounding, conversational
            )
        }

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.1, # Slightly faster for podcast energy
            pitch=0.0
        )

        for line in script_json:
            speaker = line.get('speaker', 'A')
            text = line.get('text', '')

            if not text:
                continue

            voice = voices.get(speaker, voices['A'])
            
            synthesis_input = texttospeech.SynthesisInput(text=text)

            try:
                response = self.client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
                
                # Write audio content to the in-memory buffer
                combined_audio.write(response.audio_content)
                
                # Add a tiny pause between speakers? 
                # Ideally we'd synthesize whitespace/silence, but concatenating raw MP3 frames 
                # works okay-ish for simple demos, though imperfect. 
                # For better results, one would write wav headers or use pydub, 
                # but raw MP3 concat usually plays in browsers.
                
            except Exception as e:
                print(f"Error synthesizing line: {text}. Error: {e}")
                continue

        return combined_audio.getvalue()
        return combined_audio.getvalue()

    def generate_and_save(self, script_json: list, filename: str, folder: str = "podcasts") -> str:
        """
        Generates audio and saves it directly to storage.
        Returns the public URL.
        """
        audio_bytes = self.generate_audio(script_json)
        if self.storage:
            return self.storage.save(audio_bytes, filename, folder)
        else:
             raise Exception("Storage Provider not initialized in PodcastGenerator")
