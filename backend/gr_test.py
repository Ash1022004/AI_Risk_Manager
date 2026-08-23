import os

from groq import Groq
import dotenv

dotenv.load_dotenv()

print(os.environ.get("GROQ_API_KEY"))
client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

chat_completion = client.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": "Explain the importance of fast language models",
        }
    ],
    model=os.environ.get("GROQ_MODEL"),
)

print(chat_completion.choices[0].message.content)