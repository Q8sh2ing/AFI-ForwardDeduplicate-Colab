# MOVED TO [MultiPassDedup](https://github.com/routineLife1/MultiPassDedup)

# 📖AFI-ForwardDeduplicate

### Efficient Deduplicate for Anime Video Frame Interpolation
> When performing frame interpolation on anime footage, conventional de-duplicate approach such as locating duplicate frames and removal, time remapping, have many drawbacks, like losing textures of background, failure to correctly handle multiple characters drawn in different cadence in a single scene. Therefore, they cannot be applied in production effectively. 
However, with the advancement of video frame interpolation technology based on AI, it is proved feasible to repeatedly update the original frames to obtain high quality interpolated output of anime. 
This project proposes a novel anime deduplication method based on a decent VFI algorithm of GMFSS. It does not require additional procedure of processing the frame sequence or deep neural networks, and produces smooth, high quality output by removing duplicate frames in anime adequately.

![ezgif com-video-to-gif](https://github.com/hyw-dev/AFI-ForwardDeduplicate/assets/68835291/6f03dfd8-99f4-48ad-871e-91cbd704c1e5)

Online Colab demo for AFI-ForwardDeduplicate: [[Colab]](https://github.com/Q8sh2ing/AFI-ForwardDeduplicate-Colab/blob/main/forward_dedup_Colab.ipynb)

## 👀Demos Videos
### [Jujutsu Kaisen S2 NCOP](https://www.bilibili.com/video/BV16W421N7s5/?share_source=copy_web&vd_source=8a8926eb0f1d5f0f1cab7529c8f51282)
### [Houseki no Kuni NCOP](https://www.bilibili.com/video/BV1py4y1A7qj/?share_source=copy_web&vd_source=8a8926eb0f1d5f0f1cab7529c8f51282)

## 🔧Dependencies
- ffmpeg
- same as [GMFSS](https://github.com/98mxr/GMFSS_Fortuna)
- download the [weights](https://drive.google.com/file/d/157M4i1B9hjWs1K2AZVArSulkM9qV2sdH/view?usp=sharing) and unzip it, put them to ./weights/
 
## ⚡Usage 
- normalize the source video to 24000/1001 fps by following command using ffmpeg **(If the INPUT video framerate is around 23.976, skip this step.)**
  ```bash
  ffmpeg -i INPUT -crf 16 -r 24000/1001 -preset slow -c:v libx265 -x265-params profile=main10 -c:a copy OUTPUT
  ```
- open the video and check out it's max consistent deduplication counts, (3 -> on Three, 2 -> on Two, 0 -> AUTO) **(If the INPUT video framerate is around 23.976, skip this step.)**
- run the follwing command to finish interpolation
  (N_FORWARD = max_consistent_deduplication_counts - 1) **(Under the most circumstances, -nf 0 can automatically determine an appropriate n_forward value)**
  ```bash
  python interpolate_video_forward.py -i [VIDEO] -o [OUTPUTDIR] -nf [N_FORWARD] -t [TIMES] -m [MODEL_TYPE] -s -st 12 -scale [SCALE] -stf -c -half
  # or use the following command to export video at any frame rate
  python interpolate_video_forward_anyfps.py -i [VIDEO] -o [OUTPUTDIR] -nf [N_FORWARD] -fps [OUTPUT_FPS] -m [MODEL_TYPE] -s -st 12 -scale [SCALE] -stf -c
  ```
  
- run the follwing command or custom command to merge the output frames with the audio of source video
  ```bash
  ffmpeg -r [24000/1001 * TIMES] -i [OUTPUTDIR]/%09d.png -i [VIDEO] -map 0:v -map 1:a -crf 16 -preset slow -c:v libx265 -x265-params profile=main10 -c:a copy [FINAL_OUTPUT]
  # or use the following command to export video at any frame rate
  ffmpeg -r [OUTPUT_FPS] -i [OUTPUTDIR]/%09d.png -i [VIDEO] -map 0:v -map 1:a -crf 16 -preset slow -c:v libx265 -x265-params profile=main10 -c:a copy [FINAL_OUTPUT]
  ```
  
 **example(smooth a 23.976fps video with on three and interpolate it to 60fps):**

  ```bash
  ffmpeg -i E:/Myvideo/01_src.mkv -crf 16 -r 24000/1001 -preset slow -c:v libx265 -x265-params profile=main10 -c:a copy E:/Myvideo/01.mkv

  python interpolate_video_forward_anyfps.py -i E:/MyVideo/01.mkv -o E:/frame_seq_output -nf 2 -fps 60 -m gmfss -s -st 12 -scale 1.0 -stf -c

  ffmpeg -r 60 -i E:/frame_seq_output/%09d.png -i E:/MyVideo/01.mkv -map 0:v -map 1:a -crf 16 -preset slow -c:v libx265 -x265-params profile=main10 -c:a copy E:/final_output/01.mkv
  ```
  

## todo list
- [ ] ~~**Efficiency optimization**~~ (No significant efficiency gains and increased risk of vram overflow.)
- [ ] ~~**Attempt to accurately determine transition even in the queue_input**~~ (The implementation code is too complex, and it's effect is not obvious to improve)
- [x] **Improve the smoothness By reducing transition frames to one frame and allocate them to the end of the scene**
- [ ] **Explain why this method is effective and write a guidence on how to support other vfi algorithms**
- [x] **Implement any framerate support for ForwardDeduplicate (smooth interpolation method)**

## limitations
> The "n_forward" parameter acts like the number of times the algorithm performs Spatiotemporal TTA (Spatiotemporal Test Time Augmentation) operations.
> Performing too many TTA operations may further improve smoothness and interpolation performance but lead to blurriness.
> 
> This method will change the animation rhythm to a certain extent

## Projects that use AFI-ForwardDeduplicate
[SVFI(commercial software)](https://store.steampowered.com/app/1692080/SVFI/)

## 🤗 Acknowledgement

Thanks for [Q8sh2ing](https://github.com/Q8sh2ing) implement the Online Colab Demo.

## Reference
[SpatiotemporalResampling](https://github.com/hyw-dev/SpatiotemporalResampling) [GMFSS](https://github.com/98mxr/GMFSS_Fortuna) [Practical-RIFE](https://github.com/hzwer/Practical-RIFE)
