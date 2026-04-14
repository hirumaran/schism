import hashlib
import re
import nltk

try:
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.textrank import TextRankSummarizer
    from sumy.summarizers.lsa import LsaSummarizer
    from sumy.nlp.stemmers import Stemmer
    from sumy.utils import get_stop_words
    SUMY_AVAILABLE = True
except ImportError:
    SUMY_AVAILABLE = False


class DocumentCompressor:
    def __init__(self, algorithm: str = 'textrank', ratio: float = 0.3):
        self.algorithm = algorithm
        self.ratio = ratio
        if SUMY_AVAILABLE:
            try:
                nltk.data.find('tokenizers/punkt')
            except LookupError:
                nltk.download('punkt', quiet=True)

    def _strip_math(self, text: str) -> str:
        # Strip simple inline LaTeX math blocks
        return re.sub(r'\$[^$]+\$|\\\([^)]+\)', '', text)

    def compress(self, text: str) -> str:
        if not text or not text.strip():
            return text
            
        # Bypass for short papers
        if len(text.split()) < 2000:
            return text

        if not SUMY_AVAILABLE:
            return text

        cleaned_text = self._strip_math(text)
        
        try:
            parser = PlaintextParser.from_string(cleaned_text, Tokenizer("english"))
            stemmer = Stemmer("english")
            
            if self.algorithm == 'lsa':
                summarizer = LsaSummarizer(stemmer)
            else:
                summarizer = TextRankSummarizer(stemmer)
                
            summarizer.stop_words = get_stop_words("english")
            
            sentences = list(parser.document.sentences)
            if not sentences:
                return text
                
            sentence_count = max(1, int(len(sentences) * self.ratio))
            
            summary = summarizer(parser.document, sentence_count)
            return ' '.join(str(s) for s in summary)
        except Exception:
            return text
