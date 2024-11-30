import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
import zmq
import pickle
import requests
import time
from datetime import datetime
import json

file_path = r"dataset.xlsx"
try:
    data = pd.read_excel(file_path)
except Exception as e:
    raise Exception(f"Error loading dataset: {e}")

data.fillna(data.median(), inplace=True)
X = data.drop(columns="Outcome")
y = data["Outcome"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = DecisionTreeClassifier()
model.fit(X_train, y_train)

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")
print("Server is running on tcp://*:5555...")

feature_names = X.columns.tolist()

# API UB
API_TOKEN = "Bearer TOKEN API"
API_URL = "http://10.45.188.253:3003" #API UB

# API META
META_TOKEN = "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"
META_URL = "https://openrouter.ai/api/v1/chat/completions"

def send_api_request(url, headers, payload, retries=5, timeout=60):
    for attempt in range(retries):
        try:
            print(f"Attempt {attempt + 1}: Sending request to API...")
            response = requests.post(url, headers=headers, data=payload, timeout=timeout)
            return response
        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt + 1}. Retrying...")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            break
    return None

def generate_recommendation(prediction):
    if prediction == 0:
        prompt = "Beri rekomendasi kesehatan untuk seseorang yang tidak mengidap diabetes dalam bahasa Indonesia."
    elif prediction == 1:
        prompt = "Beri rekomendasi tindakan lanjutan untuk seseorang yang terindikasi mengidap diabetes dalam bahasa Indonesia."
    else:
        return "Prediksi tidak valid."

    try:
        # Konfigurasi API UB
        # url = f"{API_URL}/api/chat/completions"
        # headers = {
        #     "Authorization": API_TOKEN,
        #     "Content-Type": "application/json"
        # }
        # payload = {
        #     "model": "nemotron:70b-instruct-q8_0",
        #     "messages": [{"role": "user", "content": prompt}]
        # }
        
        # Konfigurasi API META
        url = META_URL
        headers = {
          "Authorization": f"Bearer {META_TOKEN}",
        }
        payload = json.dumps({
          "model": "meta-llama/llama-3.2-90b-vision-instruct:free",
          "messages": [
            {
              "role": "user",
              "content": [{
                "type": "text",
                "text": prompt
              }]
            }
          ]
        })
        print("Mengirim permintaan ke API dengan payload:", payload)
        response = send_api_request(url, headers, payload)
        if response is None:
            return "Error: API tidak merespons setelah beberapa percobaan. Menggunakan rekomendasi default."

        if response.status_code == 200:
            response_data = response.json()
            return response_data["choices"][0]["message"]["content"].strip()
        elif response.status_code == 400:
            print(f"Bad Request: {response.json()}")
            return f"Error: Permintaan tidak valid - {response.json()}"
        elif response.status_code == 401:
            print("Unauthorized: Token tidak valid.")
            return "Error: Tidak diizinkan (401)."
        elif response.status_code == 404:
            print("Not Found: Endpoint atau model tidak ditemukan.")
            return "Error: Model tidak ditemukan (404)."
        elif response.status_code == 500:
            print(f"Internal Server Error: {response.text}")
            return "Error: Terjadi kesalahan di server (500)."
        else:
            print(f"Unexpected Error: {response.status_code} - {response.text}")
            return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        print(f"Error tidak dikenal: {str(e)}")
        return "Rekomendasi tidak tersedia karena terjadi kesalahan."

def save_prediction_to_csv(features, result_message, recommendation, csv_path='predictions.csv'):
    try:
        if os.path.exists(csv_path):
            existing_df = pd.read_csv(csv_path)
            new_id = 1000 + len(existing_df)
        else:
            new_id = 1000

        new_data = {
            'id': [new_id],
            'timestamp': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            'pregnancies': [features[0]],
            'glucose': [features[1]],
            'blood_pressure': [features[2]],
            'skin_thickness': [features[3]],
            'insulin': [features[4]],
            'bmi': [features[5]],
            'diabetes_pedigree': [features[6]],
            'age': [features[7]],
            'prediction_result': [result_message],
            'recommendation': [recommendation]
        }
        
        new_df = pd.DataFrame(new_data)
        
        if os.path.exists(csv_path):
            # Append to existing CSV
            new_df.to_csv(csv_path, mode='a', header=False, index=False)
        else:
            # Create new CSV with headers
            new_df.to_csv(csv_path, index=False)
            
        print(f"Prediction saved to {csv_path}")
        return True
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")
        return False

while True:
    try:
        message = socket.recv()
        data = pickle.loads(message)
        print(f"Received data: {data}")

        if not isinstance(data, list) or len(data) != len(feature_names):
            raise ValueError("Input data tidak valid. Pastikan format data sesuai dengan jumlah fitur.")

        data_df = pd.DataFrame([data], columns=feature_names)
        prediction = model.predict(data_df)[0]
        print(f"Prediction: {prediction}")

        if prediction == 0:
            result_message = "Hasil Analisa Tidak Mengidap Diabetes"
        elif prediction == 1:
            result_message = "Terindikasi Diabetes Melitus, Silahkan Lakukan Pemeriksaan Lebih Lanjut"
        else:
            result_message = "Hasil prediksi tidak valid."

        recommendation = generate_recommendation(prediction)
        full_message = f"{result_message}\nRekomendasi: {recommendation}"

        # Save prediction to CSV
        save_prediction_to_csv(data, result_message, recommendation)

        socket.send(pickle.dumps(full_message))
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
        socket.send(pickle.dumps(error_message))