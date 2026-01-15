import json
import os
import re
# We still use ChatOpenAI client because DeepSeek is compatible with it
from langchain_openai import ChatOpenAI
# NEW: Use local embeddings instead of OpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings
from app.domain.prompts import SYSTEM_PROMPT, INTENT_PROMPT
from app.interfaces.IAiService import IAiService

# --- NEW PROMPT FOR JSON EXTRACTION ---
EXTRACTION_PROMPT = """
You are an Order Extractor for a bakery.
Based on the MENU CONTEXT provided below, convert the USER INPUT into a JSON list of items.

MENU CONTEXT:
{context}

RULES:
1. Extract the product name exactly as it appears in the menu context if possible.
2. Default quantity is 1 if not specified.
3. Return ONLY a valid JSON list. Do not write explanations.
4. Format: [{{"product": "Product Name", "quantity": 1, "price_hint": "from context or 0"}}]

USER INPUT: "{user_input}"
"""

class OpenAIService(IAiService):
    def __init__(self):
        # ---------------------------------------------------------
        # 1. DEEPSEEK CONFIGURATION (The Brain)
        # ---------------------------------------------------------
        self.llm = ChatOpenAI(
            model="deepseek-chat", 
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.1, # Lower temperature for strict JSON
            max_tokens=1024
        )
        
        # ---------------------------------------------------------
        # 2. LOCAL EMBEDDINGS (The Memory)
        # ---------------------------------------------------------
        print("⏳ Loading local embeddings model (this may take a moment)...")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        print("✅ Local embeddings loaded.")
        
        self.vector_store = None
        self._initialize_vector_store()

    def _initialize_vector_store(self):
        """Ingest the menu.md file into FAISS on startup."""
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
        messages = [
            HumanMessage(content=INTENT_PROMPT.format(message=user_message))
        ]
        response = await self.llm.ainvoke(messages)
        return response.content.strip().lower()

    async def generate_response(self, user_message: str, intent: str) -> str:
        context = ""
        
        if intent in ["menu_query", "order_intent"] and self.vector_store:
            docs = self.vector_store.similarity_search(user_message, k=2)
            context = "\n".join([d.page_content for d in docs])
        
        formatted_system_prompt = SYSTEM_PROMPT.format(context=context)
        
        messages = [
            SystemMessage(content=formatted_system_prompt),
            HumanMessage(content=user_message)
        ]
        
        response = await self.llm.ainvoke(messages)
        return response.content

    # --- NEW METHOD: EXTRACT JSON ITEMS ---
    async def extract_order_items(self, user_message: str) -> list:
        """
        Extracts structured data from text using RAG to map products.
        Returns: [{"product": "Cake", "quantity": 1}, ...]
        """
        context = ""
        # 1. Retrieve menu context to help the AI map "Negra" to "Torta Negra"
        if self.vector_store:
            docs = self.vector_store.similarity_search(user_message, k=3)
            context = "\n".join([d.page_content for d in docs])

        # 2. Format Prompt
        prompt_content = EXTRACTION_PROMPT.format(context=context, user_input=user_message)
        
        messages = [HumanMessage(content=prompt_content)]
        
        # 3. Call AI
        try:
            response = await self.llm.ainvoke(messages)
            raw_content = response.content
            
            # 4. Clean and Parse JSON
            cleaned_json = self._clean_json_response(raw_content)
            items = json.loads(cleaned_json)
            
            if isinstance(items, list):
                return items
            return []
        except Exception as e:
            print(f"❌ Extraction Error: {e}")
            return []

    def _clean_json_response(self, text: str) -> str:
        """Removes markdown code blocks if the AI adds them."""
        text = text.strip()
        # Remove ```json and ``` identifiers
        if text.startswith("```"):
            text = re.sub(r"^```(json)?", "", text)
            text = re.sub(r"```$", "", text)
        return text.strip()