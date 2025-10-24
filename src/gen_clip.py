from openai import OpenAI
from moviepy import VideoFileClip
import os
import json
import time
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor
from settings import config, API_KEY


model_name = config.get(
    "clipception.llm", "model_name", fallback="deepseek/deepseek-chat"
)
temperature = config.getfloat("clipception.llm", "temperature", fallback=0.5)
max_tokens = config.getint("clipception.llm", "max_tokens", fallback=4000)


def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """Split a list into chunks of specified size."""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def load_clips(json_path: str) -> list[dict]:
    try:
        with open(json_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Clips file not found: {json_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in file: {json_path}")


def process_chunk(chunk_data: tuple[list[dict], int]) -> list[dict]:
    """Process a single chunk of clips using GPU acceleration."""
    clips, chunk_id = chunk_data

    try:
        ranked_results = rank_clips_chunk(clips)
        if ranked_results:
            parsed_chunk = parse_clip_data(ranked_results)
            return parsed_chunk
        return []
    except Exception as e:
        print(f"Warning: Failed to process chunk {chunk_id}: {str(e)}")
        return []


def rank_clips_chunk(clips: list[dict]) -> str:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY,
        default_headers={"HTTP-Referer": "http://localhost", "X-Title": "Py-AutoVod"},
    )

    audio_weight = 40
    content_weight = 60
    max_retries = 4
    retry_delay = 2  # seconds

    prompt = f"""
    You are an expert content analyzer focusing on viral clip potential. 
    You can combine clips together to form a longer clip. Analyze these clips:

    {json.dumps(clips, indent=2)}

    For each clip, evaluate using:

    1. Audio Engagement ({audio_weight}% weight):
    - Volume patterns and variations
    - Voice intensity and emotional charge 
    - Acoustic characteristics

    2. Content Analysis ({content_weight}% weight):
    - Topic relevance and timeliness
    - Controversial or debate-sparking elements
    - "Quotable" phrases
    - Discussion potential

    For each clip, return ONLY valid JSON following this exact structure:
    {{\"clips\": [{{\"name\": \"[TITLE]\", \"start\": \"[START]\", \"end\": \"[END]\", \"score\": [1-10], \"factors\": \"[Key viral factors]\", \"platforms\": \"[Recommended platforms]\"}}]}}

    Rank clips by viral potential. Focus on measurable features in the data. No commentary. No markdown. Pure JSON only.
    """

    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that ranks video clips. Keep explanations brief and focused on virality potential. Follow the format exactly.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )

            if completion and completion.choices:
                return completion.choices[0].message.content

        except Exception as e:
            if attempt < max_retries - 1:
                print(
                    f"Attempt {attempt + 1} failed. Retrying in {retry_delay} seconds..."
                )
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise Exception(
                    f"Failed to rank clips after {max_retries} attempts: {str(e)}"
                )
    return None


def rank_all_clips_parallel(
    clips: list[dict], chunk_size: int = 5, num_processes: int | None = None
) -> list[dict]:
    """Rank clips in parallel using multiple processes."""
    if num_processes is None:
        num_processes = mp.cpu_count()

    chunks = chunk_list(clips, chunk_size)
    chunk_data = [(chunk, i) for i, chunk in enumerate(chunks)]

    all_ranked_clips = []

    # Setup progress bar
    # pbar = tqdm(total=len(chunks), desc="Processing chunks")

    # Use ThreadPoolExecutor for parallel API calls
    with ThreadPoolExecutor(max_workers=num_processes) as executor:
        futures = [executor.submit(process_chunk, data) for data in chunk_data]

        for future in futures:
            try:
                result = future.result()
                all_ranked_clips.extend(result)
                # pbar.update(1)
            except Exception as e:
                print(f"Warning: Chunk processing failed: {str(e)}")

    # pbar.close()

    return sorted(all_ranked_clips, key=lambda x: x.get("score", 0), reverse=True)


def parse_clip_data(input_string: str) -> list[dict]:
    if not input_string:
        return []
    cleaned_str = input_string.replace("```json", "").replace("```", "").strip()
    try:
        # Parse the JSON string into a Python list of dictionaries
        clips = json.loads(cleaned_str)["clips"]

        # Filter out invalid clip structures
        clips = [
            clip
            for clip in clips
            if all(
                key in clip
                for key in ("name", "start", "end", "score", "factors", "platforms")
            )
        ]

        return clips
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing clip data: {e}")
        return []


def save_top_clips_json(
    clips: list[dict], output_file: str, num_clips: int = 20
) -> None:
    top_clips = clips[:num_clips]
    output_data = {
        "top_clips": top_clips,
        "total_clips": len(clips),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)
    except Exception as e:
        raise RuntimeError(f"Failed to save JSON file: {str(e)}")


def generate_clips(
    clips_json_path: str,
    output_file: str,
    num_clips: int = 20,
    chunk_size: int = 10,
    num_processes=None,
):
    start_time = time.time()
    clips: list[dict] = load_clips(clips_json_path)

    try:
        ranked_clips = rank_all_clips_parallel(clips, chunk_size, num_processes)

        save_top_clips_json(ranked_clips, output_file, num_clips)

        print(f"\nSuccessfully saved top {num_clips} clips to {output_file}")
        print(f"Total processing time: {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"Error: {str(e)}")


def extract_clip(input_file, output_dir, clip_data):
    """Extract a single clip based on the provided clip data"""
    try:
        # Create sanitized filename from clip name
        safe_name = "".join(
            c for c in clip_data["name"] if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        output_file = os.path.join(output_dir, f"{safe_name}.mp4")

        # Load the video file
        video = VideoFileClip(input_file)

        # Extract the clip using start and end times from JSON
        clip = video.subclipped(clip_data["start"], clip_data["end"])

        # Write the clip to a new file
        clip.write_videofile(output_file, codec="libx264")

        # Clean up
        clip.close()
        video.close()

        return True, output_file

    except Exception as e:
        return False, str(e)


def process_clips(input_file, output_dir, json_file, min_score=0):
    """Process all clips from the JSON file that meet the minimum score requirement"""

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Read and parse JSON data
    with open(json_file, "r") as f:
        data = json.load(f)
        print(data)

    # Process each clip that meets the score threshold
    successful_clips = []
    failed_clips = []

    for clip in data["top_clips"]:
        if clip["score"] >= min_score:
            success, result = extract_clip(input_file, output_dir, clip)
            if success:
                successful_clips.append((clip["name"], result))
            else:
                failed_clips.append((clip["name"], result))  # keyerror name

    # Print summary
    print(f"\nExtraction Summary:")
    print(f"Total clips processed: {len(successful_clips) + len(failed_clips)}")
    print(f"Successfully extracted: {len(successful_clips)}")
    print(f"Failed extractions: {len(failed_clips)}")

    if successful_clips:
        print("\nSuccessful clips:")
        for name, path in successful_clips:
            print(f"- {name}: {path}")

    if failed_clips:
        print("\nFailed clips:")
        for name, error in failed_clips:
            print(f"- {name}: {error}")
