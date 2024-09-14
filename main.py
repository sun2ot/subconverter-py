import base64
import requests

subscription = 'https://nn8qozmu.nn8qozmu.top/api/v1/client/subscribe?token=4e7395dc6413e08cdc2f1c502d140325'
encoded_data = '这里是你的Base64编码字符串'
decoded_data = base64.b64decode(encoded_data).decode('utf-8')
print(decoded_data)