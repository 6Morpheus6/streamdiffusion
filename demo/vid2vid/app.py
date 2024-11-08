import gradio as gr

import os
import sys
import random
from typing import Literal, Dict, Optional

import torch
from torchvision.io import read_video, write_video
from tqdm import tqdm
from fractions import Fraction
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from utils.wrapper import StreamDiffusionWrapper

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


def main(
    input: str,
    prompt: str = "",
    negative_prompt: str = "",
    seed: int = 2,
    num_inference_steps: int = 50,
    output: str = os.path.join(CURRENT_DIR, "..", "..", "images", "outputs", "output.mp4"),
    model_id: str = "KBlueLeaf/kohaku-v2.1",
    lora_dict: Optional[Dict[str, float]] = None,
    scale: float = 1.0,
    acceleration: Literal["none", "xformers", "tensorrt"] = "xformers",
    use_denoising_batch: bool = True,
    enable_similar_image_filter: bool = True,
):

    if seed == -1:
        seed = random.randint(1, 10000)

    """
    Process for generating images based on a prompt using a specified model.

    Parameters
    ----------
    input : str, optional
        The input video name to load images from.
    output : str, optional
        The output video name to save images to.
    model_id_or_path : str
        The name of the model to use for image generation.
    lora_dict : Optional[Dict[str, float]], optional
        The lora_dict to load, by default None.
        Keys are the LoRA names and values are the LoRA scales.
        Example: {'LoRA_1' : 0.5 , 'LoRA_2' : 0.7 ,...}
    prompt : str
        The prompt to generate images from.
    scale : float, optional
        The scale of the image, by default 1.0.
    acceleration : Literal["none", "xformers", "tensorrt"]
        The type of acceleration to use for image generation.
    use_denoising_batch : bool, optional
        Whether to use denoising batch or not, by default True.
    enable_similar_image_filter : bool, optional
        Whether to enable similar image filter or not,
        by default True.
    seed : int, optional
        The seed, by default 2. if -1, use random seed.
    """

    video_info = read_video(input)
    video = video_info[0] / 255
    fps = video_info[2]["video_fps"]
    height = int(video.shape[1] * scale)
    width = int(video.shape[2] * scale)

    stream = StreamDiffusionWrapper(
        model_id_or_path=model_id,
        lora_dict=lora_dict,
        t_index_list=[35, 45],
        frame_buffer_size=1,
        width=width,
        height=height,
        warmup=10,
        acceleration=acceleration,
        do_add_noise=False,
        mode="img2img",
        output_type="pt",
        enable_similar_image_filter=enable_similar_image_filter,
        similar_image_filter_threshold=0.98,
        use_denoising_batch=use_denoising_batch,
        seed=seed,
    )

    stream.prepare(
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=num_inference_steps,
    )

    o = stream(video[0].permute(2, 0, 1))
    height = int(o.shape[1])
    width = int(o.shape[2])
    video_result = torch.zeros(video.shape[0], height, width, 3)

    for _ in range(stream.batch_size):
        stream(image=video[0].permute(2, 0, 1))

    for i in tqdm(range(video.shape[0])):
        output_image = stream(video[i].permute(2, 0, 1))
        video_result[i] = output_image.permute(1, 2, 0)

    video_result = video_result * 255

    fps_fraction = Fraction(fps).limit_denominator()
    write_video(output, video_result[2:], fps=fps_fraction)
    return output

css = """
    .input-video video {
    height: 70vh; !Important
}
"""

with gr.Blocks(css=css) as demo:
    with gr.Row(equal_height=True):
        with gr.Column():
            input_video = gr.Video(sources=['upload', 'webcam'], elem_classes="input-video")
            prompt = gr.Textbox(label="Prompt", scale=0, value="1girl with cat ears, detailed, high quality, masterpiece, 8k, intricate, cinematic")
            neg_prompt = gr.Textbox(label="Negative Prompt", scale=0, value="black and white, blurry, low resolution, pixelated, pixel art, low quality, low fidelity")
        with gr.Column():     
            output_video = gr.Video("playable_video", elem_classes="input-video")
            with gr.Row():
                with gr.Column():
                    in_seed = gr.Slider(-1, 10000, value=-1, step=1, scale=0, label="Seed")
                    with gr.Row():
                        generate_btn = gr.Button(value="Generate")
    
        generate_btn.click(fn=main, inputs=[input_video, prompt, neg_prompt, in_seed], outputs=[output_video])

demo.launch()
