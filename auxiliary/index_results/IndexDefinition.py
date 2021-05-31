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


IndexDefinition = {
    "mappings":
        {
            "properties":
                {
                    "brands":
                        {
                            "type": "nested",
                            "properties":
                                {
                                    "brand": {
                                        "type": "keyword"
                                    },
                                    "accuracy": {
                                        "type": "float"
                                    }
                                }
                        },
                    "scenes":
                        {
                            "type": "nested",
                            "properties":
                                {
                                    "scene": {
                                        "type": "keyword"
                                    },
                                    "accuracy": {
                                        "type": "float"
                                    }
                                }
                        },
                    "sentiments":
                        {
                            "type": "nested",
                            "properties":
                                {
                                    "sentiment": {
                                        "type": "keyword"
                                    },
                                    "accuracy": {
                                        "type": "float"
                                    }
                                }
                        },
                    "celebrities":
                        {
                            "type": "nested",
                            "properties":
                                {
                                    "celebrity": {
                                        "type": "keyword"
                                    },
                                    "accuracy": {
                                        "type": "float"
                                    }
                                }
                        },
                    "objects":
                        {
                            "type": "nested",
                            "properties":
                                {
                                    "object": {
                                        "type": "keyword"
                                    },
                                    "accuracy": {
                                        "type": "float"
                                    }
                                }
                        },
                    "SampleRate": {
                        "type": "integer"
                    },
                    "Timestamp": {
                        "type": "integer"
                    },
                    "S3_Key": {
                        "type": "keyword"
                    },
                    "JobId": {
                        "type": "keyword"
                    },
                    "doc_type":
                        {
                            "type": "join",
                            "relations": {
                                "video": "frame"
                            }
                        }
                }
        }
}
