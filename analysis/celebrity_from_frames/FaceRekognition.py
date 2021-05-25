from boto3 import client
from re import sub
from botocore import config

class FaceRekognition:
    def __init__(self,region='us-east-1',config=None):
        self.name = "Face Rekognition"
        self.region = region
        if config is None:
            self.rekognition_client = client("rekognition")
        else:
            self.rekognition_client = client("rekognition",config=config)


    def add_face_to_collection(self,bucket, photo_key, collection_id):
        if self.rekognition_client is False:
            print("Failed client, exiting")
            return False

        image = {
            'S3Object': {
                'Bucket': bucket,
                'Name': photo_key
            }
        }

        photo_id = (photo_key.split("/")[-1]).split(".")[0]

        try:
            response = self.rekognition_client.index_faces(CollectionId=collection_id,
                                                      Image=image,
                                                      ExternalImageId=photo_id,
                                                      MaxFaces=1,
                                                      QualityFilter='AUTO',
                                                      DetectionAttributes=['ALL'])
        except Exception as e:
            print("Exception ocurred with photo" + photo_key + "\n", e)
            return False

        return response

    def start_face_search_collection(self,collection_id,bucket,video_key,accuracy=80):
        if self.rekognition_client is False:
            print("Failed client, exiting")
            return False

        video = {
            'S3Object': {
                'Bucket': bucket,
                'Name': video_key
            }
        }

        try:
            response = self.rekognition_client.start_face_search(
                Video=video,
                CollectionId=collection_id
            )
        except Exception as e:
            return False
        else:
            return response

    def celeb_names_in_image(self,faces_found,threshold=80,env='dev'):
        unique_faces = {}
        for face_results in faces_found:
            if face_results['Similarity'] < threshold:
                continue
            face = face_results['Face']
            face_name = self.clean_image_id(face['ExternalImageId'])

            if face_name not in unique_faces:
                unique_faces[face_name] = {
                    'total_matches':1,
                    'avg_similarity': face_results['Similarity'],
                    'avg_confidence': face['Confidence']
                }
                if env == 'dev':
                    unique_faces[face_name]['face_results'].append(face.copy())

            else:
                unique_faces[face_name]['total_matches'] += 1
                unique_faces[face_name]['avg_similarity'] = self.get_average(unique_faces[face_name]['avg_similarity'],face_results['Similarity'],unique_faces[face_name]['total_matches'])
                unique_faces[face_name]['avg_confidence'] = self.get_average(unique_faces[face_name]['avg_confidence'],face['Confidence'],unique_faces[face_name]['total_matches'])
                if env == 'dev':
                    unique_faces[face_name]['face_results'].append(face.copy())
        return unique_faces

    def detect_faces_in_image(self,bucket,image_key,threshold=0.80):
        faces_found = []
        image = {
            'S3Object': {
                'Bucket': bucket,
                'Name': image_key
            }
        }
        try:
            response = self.rekognition_client.detect_faces(Image=image, Attributes=['ALL'])
        except Exception as e:
            print(f"Error occurred while detecting faces on image s3://{bucket}/{image_key}")
            return False
        else:
            if response['FaceDetails'] == []:
                print("No faces found on image")
                return False
            for face in response['FaceDetails']:
                if face['Confidence'] >= threshold:
                    faces_found.append(face)
        return faces_found

    def clean_image_id(self,image_id):
        if '/' in image_id:
            image_id = image_id.split('/')[-1]
        image_id = sub(r'[0-9]*', '', image_id)
        image_id = image_id.replace("_","")
        image_id = image_id.replace(".jpg","")
        image_id = image_id.replace(".jpeg","")
        image_id = image_id.replace(".png","")
        return image_id

    def get_average(self,accumulated, new, n):
        if n == 0 or n == 1:
            return new
        return (accumulated * n + new) / (n + 1)

    def get_face_box(self,image_properties,bounding_box):
        image_height = image_properties[0]
        image_width = image_properties[1]
        top = int(bounding_box['Top'] * image_height)
        left = int(bounding_box['Left'] * image_width)
        height = top + int(bounding_box['Height'] * image_height)
        width = left + int(bounding_box['Width'] * image_width)
        return (left, top), (width, height)

    def detect_faces_from_collection(self, collection_id, bucket='', face_key='', blob=[], accuracy=80, max_faces=10):
        if self.rekognition_client is False:
            print("Failed client, exiting")
            return False

        if blob == []:
            image = {
                'S3Object': {
                    'Bucket': bucket,
                    'Name': face_key
                }
            }
        else:
            image = {
                'Bytes': blob
            }

        try:
            response = self.rekognition_client.search_faces_by_image(CollectionId=collection_id,
                                                                     Image=image,
                                                                     FaceMatchThreshold=accuracy,
                                                                     MaxFaces=max_faces)
        except Exception as e:
            if "There are no faces in the image" not in e:
                print("Exception ocurred while matching the face \n", e)
            return False
        else:
            return response

    def crop_face(self,image, face_start, face_dimensions, defase=40):
        new_image = image.copy()
        size = new_image.shape
        new_face_left = [face_start[0] - defase, face_dimensions[0] + defase]
        if new_face_left[0] < 0:
            new_face_left[0] = 0
        if new_face_left[1] > size[1]:
            new_face_left[1] = size[1]
        new_face_top = [face_start[1] - defase, face_dimensions[1] + defase]
        if new_face_top[0] < 0:
            new_face_top[0] = 0
        if new_face_top[1] > size[0]:
            new_face_top[1] = size[0]

        return new_image[new_face_top[0]:new_face_top[1], new_face_left[0]:new_face_left[1]]
