import requests

def get_ai_response(user_message, HUGGINGFACE_API_KEY):
    # url = f"https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct"
    url = "https://api-inference.huggingface.co/models/facebook/blenderbot-400M-distill"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    data = {"inputs": user_message}

    try:
        response = requests.post(url, headers=headers, json=data)

        print("API Response:", response.status_code, response.text)  # Debugging log

        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and "generated_text" in result[0]:
                return result[0]["generated_text"]
            else:
                return "Unexpected AI response format. Try again later!"
        
        elif response.status_code == 503:
            return "AI model is loading. Please wait a few seconds and try again."

        elif response.status_code == 429:
            return "Rate limit exceeded. Try again later."

        else:
            return f"AI Error {response.status_code}: {response.text}"

    except Exception as e:
        return f"Error: {str(e)}"
