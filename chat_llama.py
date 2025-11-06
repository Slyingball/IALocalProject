import requests

def demander_a_llama(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]

# Exemple d’utilisation
if __name__ == "__main__":
    question = input("Pose ta question à LLaMA : ")
    reponse = demander_a_llama(question)
    print("\nRéponse de LLaMA:\n", reponse)

