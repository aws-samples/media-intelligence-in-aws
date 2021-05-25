IndexDefinition = {
  "mappings": {
    "properties": {
      "brands": {
        "type": "nested",
        "properties": {
          "brand": {
          "type": "keyword"
          },
          "accuracy": {
          "type": "float"
          }
        }
      },
      "scenes": {
        "type": "nested",
        "properties": {
            "scene": {
              "type": "keyword"
            },
            "accuracy": {
              "type": "float"
            }
        }
      },
      "sentiments": {
        "type": "nested",
        "properties": {
            "sentiment": {
              "type": "keyword"
            },
            "accuracy": {
              "type": "float"
            }
        }
      },
      "celebrities": {
        "type": "nested",
        "properties": {
            "celebrity": {
              "type": "keyword"
            },
            "accuracy": {
              "type": "float"
            }
        }
      },
      "objects": {
        "type": "nested",
        "properties": {
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
      "doc_type": { 
        "type": "join",
        "relations": {
          "video": "frame"
        }
      }
    }
  }
}