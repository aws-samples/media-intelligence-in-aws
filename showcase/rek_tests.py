# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Amazon Software License (the "License"). You may not
# use this file except in compliance with the License. A copy of the
# License is located at:
#    http://aws.amazon.com/asl/
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, expressi
# or implied. See the License for the specific language governing permissions
# and limitations under the License.


from json import dumps, loads
from RekognitionDisplayer import BoundingBox,RekognitionDisplayer

CONFIDENCE_THRESHOLD = 90

def open_image(image_src):
    with open(image_src, "rb") as image:
        f = image.read()
        b = bytearray(f)
    return b

def open_output_file(source):
    with open(source,"r") as file:
        f = file.read()
        content = loads(f)
    return content

def write_json_file(content,path):
    with open(path, "a") as f:
        f.write(content)
        f.close()

i=0
image_base = "frames/NV_9_frame_."
api_response = open_output_file('responses.json')
api_json_response = api_response
rek_displayer = RekognitionDisplayer()
if 'data' not in api_json_response:
    print('No Data in JSON response')
    exit(0)
data = api_json_response['data']
for analysis in data:
    frames = data[analysis]
    if len(frames) < 1:
        print('No frames with results for analysis '+analysis)
        continue
    for frame in frames:
        if 'FrameS3Key' not in frame:
            continue
        frame_key = 'frames/' + frame['FrameS3Key'].split('/')[-1]
        labels_found = frame['DetectedLabels']
        response = rek_displayer.plot_rek_results(frame_key,labels_found,confidence_threshold=CONFIDENCE_THRESHOLD)

        if response['bounding_boxes'] is []:
            continue
        for bounding_box in response['bounding_boxes']:
            print('displaying bounding box '+frame_key)
            rek_displayer.display_image(bounding_box)