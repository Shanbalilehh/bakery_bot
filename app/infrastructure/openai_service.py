import json
import os
import re
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings
# We import the NEW prompt from domain
from app.domain.prompts import SYSTEM_PROMPT, INTENT_PROMPT, EXTRACTION_PROMPT
from app.interfaces.IAiService import IAiService

class OpenAIService(IAiService):
    def __init__(self):
        self.llm = ChatOpenAI(
            model="deepseek-chat", 
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.1, 
            max_tokens=1024
        )
        
        print("⏳ Loading local embeddings model...")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        print("✅ Local embeddings loaded.")
        
        self.vector_store = None
        self._initialize_vector_store()

    def _initialize_vector_store(self):
        try:
            if not os.path.exists("data/menu.md"):
                print("⚠️ Warning: data/menu.md not found. Skipping RAG.")
                return

            loader = TextLoader("data/menu.md")
            documents = loader.load()
            text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=0)
            docs = text_splitter.split_documents(documents)
            self.vector_store = FAISS.from_documents(docs, self.embeddings)
            print("✅ RAG Knowledge Base Loaded: menu.md")
        except Exception as e:
            print(f"⚠️ Warning: Could not load menu.md. Error: {e}")

    async def get_intent(self, user_message: str) -> str:
        messages = [HumanMessage(content=INTENT_PROMPT.format(message=user_message))]
        response = await self.llm.ainvoke(messages)
        return response.content.strip().lower()

    async def generate_response(self, user_message: str, intent: str, history: str = "") -> str:
        context = ""
        if intent in ["menu_query", "order_intent"] and self.vector_store:
            docs = self.vector_store.similarity_search(user_message, k=2)
            context = "\n".join([d.page_content for d in docs])
        
        full_system_prompt = SYSTEM_PROMPT.format(context=context) + f"\n\nCONVERSATION HISTORY:\n{history}"
        
        messages = [
            SystemMessage(content=full_system_prompt),
            HumanMessage(content=user_message)
        ]
        response = await self.llm.ainvoke(messages)
        return response.content

    async def extract_order_items(self, user_message: str, history: str = "") -> dict:
        """
        Returns a DICT with items, modifiers, and delivery info.
        """
        context = ""
        if self.vector_store:
            docs = self.vector_store.similarity_search(user_message, k=3)
            context = "\n".join([d.page_content for d in docs])

        combined_context = f"{context}\n\nRECENT CHAT:\n{history}"
        prompt_content = EXTRACTION_PROMPT.format(context=combined_context, user_input=user_message)
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt_content)])
            cleaned_json = self._clean_json_response(response.content)
            data = json.loads(cleaned_json)
            
            # Ensure structure even if AI misses fields
            return {
                "items": data.get("items", []),
                "modifiers": data.get("modifiers", {}),
                "delivery_info": data.get("delivery_info", {})
            }
        except Exception as e:
            print(f"❌ Extraction Error: {e}")
            return {"items": [], "modifiers": {}, "delivery_info": {}}

    def _clean_json_response(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(json)?", "", text)
            text = re.sub(r"```$", "", text)
        return text.strip()