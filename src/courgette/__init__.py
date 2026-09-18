from dotenv import load_dotenv
from litellm import completion

# Charge les variables du fichier .env dans os.environ
load_dotenv()

def main() -> None:
    print("Hello from mai-garden!")

    response = completion(
        model="gemini/gemini-3.6-flash",
        messages=[
            {
                "role": "user",
                "content": "Explique-moi ce qu'est un AI Engineer en une phrase.",
            }
        ],
    )

    print(response.choices[0].message.content)
