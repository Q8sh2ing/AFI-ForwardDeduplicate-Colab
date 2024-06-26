import os
import cv2
import torch
from tqdm import tqdm
import warnings
import _thread
import argparse
import time
import math
import numpy as np
from queue import Queue
from models.model_pg104.RIFE import Model
from models.IFNet_HDv3 import IFNet
from Utils_scdet.scdet import SvfiTransitionDetection

warnings.filterwarnings("ignore")
torch.set_grad_enabled(False)

parser = argparse.ArgumentParser(description='Interpolation a video with AFI-ForwardDeduplicate')
parser.add_argument('-i', '--video', dest='video', type=str, default='1.mp4', help='input the path of input video')
parser.add_argument('-o', '--output_dir', dest='output_dir', type=str, default='output',
                    help='the folder path where save output frames')
parser.add_argument('-nf', '--n_forward', dest='n_forward', type=int, default=2,
                    help='the value of parameter n_forward')
parser.add_argument('-t', '--times', dest='times', type=int, default=2, help='the interpolation ratio')
parser.add_argument('-m', '--model_type', dest='model_type', type=str, default='gmfss',
                    help='the interpolation model to use (gmfss/rife)')
parser.add_argument('-s', '--enable_scdet', dest='enable_scdet', type=bool, default=False,
                    help='enable scene change detection')
parser.add_argument('-st', '--scdet_threshold', dest='scdet_threshold', type=int, default=14,
                    help='scene detection threshold, same setting as SVFI')
parser.add_argument('-stf', '--shrink_transition_frames', dest='shrink', type=bool, default=True,
                    help='shrink the copy frames in transition to improve the smoothness')
parser.add_argument('-scale', '--scale', dest='scale', type=float, default=1.0,
                    help='flow scale, generally use 1.0 with 1080P and 0.5 with 4K resolution')
args = parser.parse_args()

model_type = args.model_type
n_forward = args.n_forward  # max_consistent_deduplication_counts - 1
times = args.times  # interpolation ratio >= 2
enable_scdet = args.enable_scdet  # enable scene change detection
scdet_threshold = args.scdet_threshold  # scene change detection threshold
shrink_transition_frames = args.shrink  # shrink the frames of transition
video = args.video  # input video path
save = args.output_dir  # output img dir
scale = args.scale  # flow scale

assert model_type in ['gmfss', 'rife'], f"not implement the model {model_type}"
assert n_forward > 0, "the parameter n_forward must larger then zero"
assert times >= 2, "at least interpolate two times"

if not os.path.exists(video):
    raise FileNotFoundError(f"can't find the file {video}")
if not os.path.isdir(save):
    raise TypeError("the value of param output_dir isn't a path of folder")
if not os.path.exists(save):
    os.mkdir(save)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
torch.set_grad_enabled(False)
if torch.cuda.is_available():
    torch.backends.cudnn.enabled = True
    torch.backends.cudnn.benchmark = True

# scene detection from SVFI
scene_detection = SvfiTransitionDetection(save, 4,
                                          scdet_threshold=scdet_threshold,
                                          pure_scene_threshold=10,
                                          no_scdet=not enable_scdet,
                                          use_fixed_scdet=False,
                                          fixed_max_scdet=50,
                                          scdet_output=False)


def convert(param):
    return {
        k.replace("module.", ""): v
        for k, v in param.items()
        if "module." in k
    }


if model_type == 'rife':
    model = IFNet()
    model.load_state_dict(convert(torch.load('weights/rife48.pkl')))
else:
    model = Model()
    model.load_model('weights/train_log_pg104', -1)
model.eval()
if model_type == 'gmfss':
    model.device()
else:
    model.to(device).half()
print("Loaded model")


def to_tensor(img):
    return torch.from_numpy(img.transpose(2, 0, 1)).unsqueeze(0).half().cuda() / 255.


def to_numpy(tensor):
    return tensor.squeeze(0).permute(1, 2, 0).cpu().numpy() * 255.


output_counter = 0  # output frame index counter


def put(things):  # put frame to write_buffer
    global output_counter
    output_counter += 1
    things = cv2.resize(things.astype(np.uint8), export_size)
    write_buffer.put([output_counter, things])


def get():  # get frame from read_buffer
    return read_buffer.get()


def build_read_buffer(r_buffer, v):
    ret, __x = v.read()
    while ret:
        r_buffer.put(cv2.resize(__x, global_size))
        ret, __x = v.read()
    r_buffer.put(None)


def clear_write_buffer(w_buffer):
    while True:
        item = w_buffer.get()
        if item is None:
            break
        num = item[0]
        content = item[1]
        cv2.imwrite(os.path.join(save, "{:0>9d}.png".format(num)), cv2.resize(content, global_size))


video_capture = cv2.VideoCapture(video)
total_frames_count = video_capture.get(7)
width, height = map(video_capture.get, [cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT])
read_buffer = Queue(maxsize=100)
write_buffer = Queue(maxsize=-1)
_thread.start_new_thread(build_read_buffer, (read_buffer, video_capture))
_thread.start_new_thread(clear_write_buffer, (write_buffer,))
pbar = tqdm(total=total_frames_count)

width, height = map(int, [width, height])
export_size = (int(width), int(height))
pad_size = (64 / scale)
global_size = (int(math.ceil(width / pad_size) * pad_size), int(math.ceil(height / pad_size) * pad_size))


def make_inf(x, y, _scale, timestep):
    if model_type == 'rife':
        return model(torch.cat((x, y), dim=1), timestep)
    return model.inference(x, y, model.reuse(x, y, _scale), timestep)


def decrase_inference(_inputs: list, layers=0, counter=0):
    while len(_inputs) != 1:
        layers += 1
        tmp_queue = []
        for i in range(len(_inputs) - 1):
            if saved_result.get(f'{layers}{i + 1}') is not None:
                saved_result[f'{layers}{i}'] = saved_result[
                    f'{layers}{i + 1}']
                tmp_queue.append(
                    saved_result[f'{layers}{i}']
                )
            else:
                inp0, inp1 = map(to_tensor, [_inputs[i], _inputs[i + 1]])
                tmp_queue.append(
                    to_numpy(make_inf(inp0, inp1, scale, 0.5))
                )
                saved_result[f'{layers}{i}'] = tmp_queue[-1]
                counter += 1
        _inputs = tmp_queue
    return _inputs[0], counter


def gen_ts_frame(x, y, _scale, ts):
    _outputs = list()
    _reuse_things = model.reuse(x, y, _scale) if model_type == 'gmfss' else None
    for t in ts:
        if model_type == 'rife':
            _out = make_inf(x, y, _scale, t)
        else:
            _out = model.inference(x, y, _reuse_things, t, _scale)
        _outputs.append(to_numpy(_out))
    return _outputs


queue_input = [get()]
queue_output = []
saved_result = {}
output0 = None
# if times = 5, n_forward=3, right=6, left=7
right_infill = (times * n_forward) // 2 - 1
left_infill = right_infill + (times * n_forward) % 2

if shrink_transition_frames:
    right_infill += times - 1

times_ts = [i / times for i in range(1, times)]

while True:
    if output0 is None:
        queue_input.extend(get() for _ in range(n_forward))

        output0, count = decrase_inference(queue_input.copy())

        queue_output.append(queue_input[0])
        inputs = [queue_input[0]]
        inputs.extend(saved_result[f'{layer}0'] for layer in range(1, n_forward + 1))

        timestamp = [0.5 * layer for layer in range(0, n_forward + 1)]
        t_step = timestamp[-1] / (left_infill + 1)
        require_timestamp = [t_step * i for i in range(1, left_infill + 1)]

        for i in range(len(timestamp) - 1):
            t0, t1 = timestamp[i], timestamp[i + 1]
            if t0 in require_timestamp:
                queue_output.append(inputs[i])
                require_timestamp.remove(t0)
            if t1 in require_timestamp:
                queue_output.append(inputs[i + 1])
                require_timestamp.remove(t1)
            condition_middle = [rt for rt in require_timestamp if t0 < rt < t1]
            if len(condition_middle) != 0:
                inp0, inp1 = map(to_tensor, [inputs[i], inputs[i + 1]])
                outputs = gen_ts_frame(inp0, inp1, scale, [(t - t0) * 2 for t in condition_middle])
                queue_output.extend(outputs)
            if len(require_timestamp) == 0:
                break

    _ = queue_input.pop(0)
    queue_input.append(get())

    if (queue_input[-1] is None) or scene_detection.check_scene(queue_input[-2], queue_input[-1]):

        queue_output.append(output0)
        inputs = [output0]
        inputs.extend(saved_result[f'{layer}{n_forward - layer}'] for layer in range(n_forward - 1, 0, -1))
        inputs.append(queue_input[-2])

        timestamp = [0.5 * layer for layer in range(0, n_forward + 1)]
        t_step = timestamp[-1] / (right_infill + 1)
        require_timestamp = [t_step * i for i in range(1, right_infill + 1)]

        for i in range(len(timestamp) - 1):
            t0, t1 = timestamp[i], timestamp[i + 1]
            if t0 in require_timestamp:
                queue_output.append(inputs[i])
                require_timestamp.remove(t0)
            if t1 in require_timestamp:
                queue_output.append(inputs[i + 1])
                require_timestamp.remove(t1)
            condition_middle = [rt for rt in require_timestamp if t0 < rt < t1]
            if len(condition_middle) != 0:
                inp0, inp1 = map(to_tensor, [inputs[i], inputs[i + 1]])
                outputs = gen_ts_frame(inp0, inp1, scale, [(t - t0) * 2 for t in condition_middle])
                queue_output.extend(outputs)
            if len(require_timestamp) == 0:
                break

        queue_output.append(queue_input[-2])

        if not shrink_transition_frames:
            queue_output.extend([queue_input[-2]] * (times - 1))

        for out in queue_output:
            put(out)

        if queue_input[-1] is None:
            break

        queue_input = [queue_input[-1]]
        queue_output = list()
        saved_result = dict()
        output0 = None
        pbar.update(1)
        continue

    output1, count = decrase_inference(queue_input.copy())

    queue_output.append(output0)
    inp0, inp1 = map(to_tensor, [output0, output1])
    queue_output.extend(gen_ts_frame(inp0, inp1, scale, times_ts))

    for out in queue_output:
        put(out)

    queue_output.clear()
    output0 = output1
    pbar.update(1)

print('Wait for all frames to be exported...')
while not write_buffer.empty():
    time.sleep(0.1)

pbar.update(1)
print('Done!')
