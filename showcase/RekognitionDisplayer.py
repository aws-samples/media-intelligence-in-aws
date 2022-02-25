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


from matplotlib import pyplot as plt
from random import randrange
from json import dumps,loads
from math import sqrt,ceil
from cv2 import cvtColor,imread,rectangle,COLOR_BGR2RGB

class BoundingBox:
    def __init__(self,box_color = (255,255,255),box_thickness = 2):
        self.color = box_color
        self.thickness = box_thickness

class RekognitionDisplayer:
    def __init__(self,bounding_box = BoundingBox()):
        self.bounding_box = bounding_box

    def display_image(self,image):
        plt.imshow(image)
        plt.show()

    def display_multiple_images(self,images,rows=1,columns=1):
        total = len(images)
        spaces = rows*columns
        if total > spaces:
            diff = total-spaces
            inc = int(ceil(sqrt(diff)))
            rows += inc
            columns += inc
        fig = plt.figure()
        i = 1
        for image in images:
            fig.add_subplot(rows, columns, i)
            plt.imshow(image)
            plt.axis('off')
            i += 1
        plt.show()

    def display_items_detected(self,items_detected):
        for item in items_detected:
            self.display_image(item['box'])
            print(item['attributes'])


    def open_image(self,source,color = COLOR_BGR2RGB):
        image = imread(source)
        return cvtColor(image, color)


    def close_images(self):
        plt.close("all")

    def plot_rek_results(self,img,plot_data,color = COLOR_BGR2RGB,confidence_threshold=90):
        image = self.open_image(img)
        plot_data = loads(plot_data)
        response = {
            'tags': self.get_tags(plot_data,confidence_threshold),
            'image': image,
            'bounding_boxes':[]
        }
        for result in plot_data:
            if 'Instances' not in result:
                continue
            items = result['Instances']
            if len(items) < 1:
                continue
            boxed_image = self.add_landmarks_to_image(image, self.convert_rek_results(image.shape, items))
            if boxed_image in response['bounding_boxes']:
                continue
            response['bounding_boxes'].append(boxed_image)
        return response

    def get_tags(self,data,threshold=90):
        tags = []
        for item in data:
            if 'Name' not in item:
                continue
            if 'Confidence' not in item:
                continue
            if item['Confidence'] < threshold:
                continue
            tags.append({'tag':item['Name'],'score':item['Confidence']})
        return tags


    def add_landmarks_to_image(self,image,landmarks,color=False):
        if color is False:
            color = tuple(int(divmod(int(color)+randrange(256),256)[1]) for color in self.bounding_box.color)
        for values in landmarks:
            top_corner = (values['x'],values['y'])
            bottom_corner = (values['x']+values['width'],values['y']+values['height'])
            rectangle(image,
                top_corner,
                bottom_corner,
                color,
                self.bounding_box.thickness)
        return image


    def convert_rek_results(self,img_shape,instances_details):
        dimensions = img_shape
        image_height = dimensions[0]
        image_width = dimensions[1]
        if instances_details is False or instances_details == []:
            print("No data to plot")
            return False
        bounding_boxes = []
        for instance in instances_details:
            if 'BoundingBox' not in instance:
                print('No bounding boxes to work with')
                continue
            values = instance['BoundingBox']
            rek_x = float(values['Left'])
            rek_y = float(values['Top'])
            rek_width = float(values['Width'])
            rek_height = float(values['Height'])
            x = int(rek_x * image_width)
            y = int(rek_y * image_height)
            width = int(rek_width * image_width)
            height = int(rek_height * image_height)
            response =  {
                'rek_x': rek_x,
                'rek_y': rek_y,
                'rek_width': rek_width,
                'rek_height': rek_height,
                'x': x,
                'y': y,
                'width': width,
                'height': height
            }
            bounding_boxes.append(response)
        return bounding_boxes