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


from boto3 import client
import time


class AudioFrameExtractor:
    def __init__(self, role_arn, destination_bucket):
        self.destination_bucket = destination_bucket
        self.role = role_arn

        # Load account endpoint
        mediaconvert = client('mediaconvert')
        endpoint = mediaconvert.describe_endpoints(
            MaxResults=1, Mode='DEFAULT'
        )['Endpoints'][0]['Url']
        self.mediaconvert = client('mediaconvert', endpoint_url=endpoint)

    def start_mediaconvert_job(
        self, S3Key, SampleRate=1, Timestamp=time.time()
    ):
        # settings = self._build_media_convert_job_settings(S3Key, SampleRate)
        try:
            job_response = self.mediaconvert.create_job(
                Role=self.role,
                Settings=self._build_media_convert_job_settings(
                    S3Key, Timestamp, SampleRate
                ),
            )
            return job_response['Job']['Id']
        except Exception as e:
            print("MediaConvert job creation exception \n", e)
            return False

    def get_mediaconvert_job(self, job_id):
        if self.mediaconvert is False:
            raise Exception("MediaConvert client creation failed")
        try:
            job_response = self.mediaconvert.get_job(Id=job_id)
        except Exception as e:
            print("MediaConvert get job exception \n", e)
            return False
        else:
            return job_response

    def _convert_float_to_fraction(self, number, decimal_separator='.'):
        denominator = 1

        if (type(number) is float):
            if (float(number).is_integer() is False):
                number = str(number)
                decimal_point = number.find(decimal_separator)
                if (decimal_separator != -1):
                    denominator = int(
                        pow(10, (len(number) - 1 - decimal_point))
                    )
                    numerator = int(number.replace(decimal_separator, ''))
            else:
                numerator = int(number)
        else:
            numerator = int(number)

        return numerator, denominator

    def _build_media_convert_job_settings(self, S3Key, Timestamp, SampleRate):
        file_name = (S3Key.split('/')[-1])
        # file_name_no_extension = file_name.split('.')[-2]
        destination_bucket_uri = f's3://{self.destination_bucket}/videos/analysis'

        #Always a video required as an output for MediaConvert
        base_video_output = {
            "ContainerSettings":
                {
                    "Container": "MP4",
                    "Mp4Settings":
                        {
                            "CslgAtom": "INCLUDE",
                            "CttsVersion": 0,
                            "FreeSpaceBox": "EXCLUDE",
                            "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
                        }
                },
            "VideoDescription":
                {
                    "ScalingBehavior": "DEFAULT",
                    "TimecodeInsertion": "DISABLED",
                    "AntiAlias": "ENABLED",
                    "Sharpness": 50,
                    "CodecSettings":
                        {
                            "Codec": "H_264",
                            "H264Settings":
                                {
                                    "InterlaceMode":
                                        "PROGRESSIVE",
                                    "NumberReferenceFrames":
                                        3,
                                    "Syntax":
                                        "DEFAULT",
                                    "Softness":
                                        0,
                                    "GopClosedCadence":
                                        1,
                                    "GopSize":
                                        90,
                                    "Slices":
                                        1,
                                    "GopBReference":
                                        "DISABLED",
                                    "SlowPal":
                                        "DISABLED",
                                    "EntropyEncoding":
                                        "CABAC",
                                    "Bitrate":
                                        10000,
                                    "FramerateControl":
                                        "INITIALIZE_FROM_SOURCE",
                                    "RateControlMode":
                                        "CBR",
                                    "CodecProfile":
                                        "MAIN",
                                    "Telecine":
                                        "NONE",
                                    "MinIInterval":
                                        0,
                                    "AdaptiveQuantization":
                                        "AUTO",
                                    "CodecLevel":
                                        "AUTO",
                                    "FieldEncoding":
                                        "PAFF",
                                    "SceneChangeDetect":
                                        "ENABLED",
                                    "QualityTuningLevel":
                                        "SINGLE_PASS",
                                    "FramerateConversionAlgorithm":
                                        "DUPLICATE_DROP",
                                    "UnregisteredSeiTimecode":
                                        "DISABLED",
                                    "GopSizeUnits":
                                        "FRAMES",
                                    "ParControl":
                                        "INITIALIZE_FROM_SOURCE",
                                    "NumberBFramesBetweenReferenceFrames":
                                        2,
                                    "RepeatPps":
                                        "DISABLED",
                                    "DynamicSubGop":
                                        "STATIC"
                                }
                        },
                    "AfdSignaling": "NONE",
                    "DropFrameTimecode": "ENABLED",
                    "RespondToAfd": "NONE",
                    "ColorMetadata": "INSERT"
                },
            "AudioDescriptions":
                [
                    {
                        "AudioTypeControl": "FOLLOW_INPUT",
                        "AudioSourceName": "Audio Selector 1",
                        "CodecSettings":
                            {
                                "Codec": "AAC",
                                "AacSettings":
                                    {
                                        "AudioDescriptionBroadcasterMix":
                                            "NORMAL",
                                        "Bitrate":
                                            96000,
                                        "RateControlMode":
                                            "CBR",
                                        "CodecProfile":
                                            "LC",
                                        "CodingMode":
                                            "CODING_MODE_2_0",
                                        "RawFormat":
                                            "NONE",
                                        "SampleRate":
                                            48000,
                                        "Specification":
                                            "MPEG4"
                                    }
                            },
                        "LanguageCodeControl": "FOLLOW_INPUT"
                    }
                ],
            "Extension": "mp3",
            "NameModifier": "_audio"
        }

        sample_rate_numerator, sample_rate_denominator = self._convert_float_to_fraction(
            SampleRate
        )

        base_framing_output = {
            "ContainerSettings": {
                "Container": "RAW"
            },
            "VideoDescription":
                {
                    "ScalingBehavior": "DEFAULT",
                    "TimecodeInsertion": "DISABLED",
                    "AntiAlias": "ENABLED",
                    "Sharpness": 50,
                    "CodecSettings":
                        {
                            "Codec": "FRAME_CAPTURE",
                            "FrameCaptureSettings":
                                {
                                    "FramerateNumerator":
                                        sample_rate_numerator,
                                    "FramerateDenominator":
                                        sample_rate_denominator,
                                    "MaxCaptures":
                                        10000000,
                                    "Quality":
                                        100
                                }
                        },
                    "DropFrameTimecode": "ENABLED",
                    "ColorMetadata": "INSERT"
                },
            "NameModifier": "_frame_"
        }
        base_audio_output = {
            "ContainerSettings":
                {
                    "Container": "MP4",
                    "Mp4Settings":
                        {
                            "CslgAtom": "INCLUDE",
                            "CttsVersion": 0,
                            "FreeSpaceBox": "EXCLUDE",
                            "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
                        }
                },
            "AudioDescriptions":
                [
                    {
                        "AudioTypeControl": "FOLLOW_INPUT",
                        "AudioSourceName": "Audio Selector 1",
                        "CodecSettings":
                            {
                                "Codec": "AAC",
                                "AacSettings":
                                    {
                                        "AudioDescriptionBroadcasterMix":
                                            "NORMAL",
                                        "Bitrate":
                                            96000,
                                        "RateControlMode":
                                            "CBR",
                                        "CodecProfile":
                                            "LC",
                                        "CodingMode":
                                            "CODING_MODE_2_0",
                                        "RawFormat":
                                            "NONE",
                                        "SampleRate":
                                            48000,
                                        "Specification":
                                            "MPEG4"
                                    }
                            },
                        "LanguageCodeControl": "FOLLOW_INPUT"
                    }
                ]
        }
        output_group = {
            "CustomName": "",
            "Name": "File Group",
            "Outputs":
                [base_video_output, base_audio_output, base_framing_output],
            "OutputGroupSettings":
                {
                    "Type": "FILE_GROUP_SETTINGS",
                    "FileGroupSettings":
                        {
                            "Destination":
                                '{}/{}/{}/{}/'.format(
                                    destination_bucket_uri, file_name,
                                    SampleRate, Timestamp
                                )
                        }
                }
        }
        base_input = {
            "AudioSelectors":
                {
                    "Audio Selector 1":
                        {
                            "Offset": 0,
                            "DefaultSelection": "DEFAULT",
                            "ProgramSelection": 1
                        }
                },
            "VideoSelector": {
                "ColorSpace": "FOLLOW"
            },
            "FilterEnable": "AUTO",
            "PsiControl": "USE_PSI",
            "FilterStrength": 0,
            "DeblockFilter": "DISABLED",
            "DenoiseFilter": "DISABLED",
            "TimecodeSource": "EMBEDDED",
            "FileInput": ""
        }

        base_settings = {"Inputs": [], "OutputGroups": [output_group]}

        base_input["FileInput"] = S3Key
        base_settings["Inputs"].append(base_input.copy())

        return base_settings
