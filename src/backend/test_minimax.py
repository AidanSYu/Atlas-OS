import asyncio
from app.core.config import settings
import litellm
import traceback

litellm.api_key = settings.MINIMAX_API_KEY
litellm.set_verbose=True

async def main():
    try:
        response = await asyncio.to_thread(
            litellm.completion,
            model='minimax/MiniMax-M2.5',
            messages=[{'role': 'system', 'content': 'You are a bot'}, {'role': 'user', 'content': 'output json please'}],
            response_format={'type': 'json_object'}
        )
        print(response)
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
