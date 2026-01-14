import os
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

class OpenAIService:
    def __init__(self):
        # ---------------------------------------------------------
        # 1. DEEPSEEK CONFIGURATION (The Brain)
        # ---------------------------------------------------------
        self.llm = ChatOpenAI(
            model="deepseek-chat", 
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.3,
            max_tokens=1024
        )
        
        # ---------------------------------------------------------
        # 2. LOCAL EMBEDDINGS (The Memory)
        # ---------------------------------------------------------
        # Uses 'all-MiniLM-L6-v2' (small, fast, and free)
        # It will download (~80MB) automatically on the first run.
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