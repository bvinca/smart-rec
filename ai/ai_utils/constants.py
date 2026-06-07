# Model names + thresholds - one place for magic numbers

# OpenAI models
OPENAI_EMBEDDING_MODEL = "text-embedding-3-large"
OPENAI_EMBEDDING_DIM = 3072  # text-embedding-3-large dimension
OPENAI_CHAT_MODEL = "gpt-4o-mini"

# embedding settings
MAX_TEXT_LENGTH = 8000  # OpenAI token limit
EMBEDDING_BATCH_SIZE = 100

# scoring weights - legacy 4-way split; production uses 40/40/20 in evaluator.py
SCORE_WEIGHTS = {
    "match": 0.35,
    "skill": 0.30,
    "experience": 0.25,
    "education": 0.10
}

# score thresholds
SCORE_THRESHOLDS = {
    "excellent": 80,
    "good": 60,
    "moderate": 40,
    "poor": 0
}

# RAG settings
RAG_TOP_K = 3  # how many docs to retrieve
RAG_TEMPERATURE = 0.7

# question generation
DEFAULT_NUM_QUESTIONS = 5
MAX_QUESTIONS = 10

# summary settings
SUMMARY_MAX_TOKENS = 200
SUMMARY_TEMPERATURE = 0.7

# feedback settings
FEEDBACK_MAX_TOKENS = 500
FEEDBACK_TEMPERATURE = 0.7

