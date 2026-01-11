import asyncio
from ollama import AsyncClient
import os

class Ollamahealth:
    async def model_available(self, model: str) -> bool:
        """
        Check if a specific model is available in Ollama.
        """
    
        try:
            client = AsyncClient(
                base_url=os.getenv("OLLAMA_API_URL", "http://localhost:11434")
            )
            resp = await client.list()
            available_models = [m.model for m in resp.models if m.model is not None]
            return model in available_models
        except Exception as e:
            print(f"Error checking model availability: {e}")
            return False
    async def ping(self) -> bool:
        """
    Check if the Ollama server is reachable.
        """
        try:
            client = AsyncClient(
                base_url=os.getenv("OLLAMA_API_URL", "http://localhost:11434")
            )
            await client.list()
            return True
        except Exception as e:
            print(f"Error pinging Ollama server: {e}")
            return False
    def health_check(self, model: str) -> bool:
        """
        Perform a health check on the Ollama service.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            model_check = loop.run_until_complete(self.model_available(model))
            ping_check = loop.run_until_complete(self.ping())
            return model_check and ping_check
        finally:
            loop.close()
ollama_health_checker = Ollamahealth()
