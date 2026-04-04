# tools/duckduckgo_search.py
"""AgentEagle++ - Módulo de búsqueda web GENERAL (no-security)."""
import requests
from bs4 import BeautifulSoup
import logging
import time
import random
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class DuckDuckGoSearch:
    """🔍 Buscador web general usando DuckDuckGo."""

    BASE_URL = "https://html.duckduckgo.com/html"
    MAX_RETRIES = 2
    BASE_DELAY = 1.5
    MAX_DELAY = 4.0

    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15',
    ]

    def __init__(self, timeout: int = 10, language: str = "es-es"):
        self.timeout = timeout
        self.language = language
        self.session = requests.Session()
        self._last_request_time = 0
        logger.info(f"🔍 DuckDuckGoSearch inicializado (búsqueda general)")

    def _get_headers(self) -> Dict[str, str]:
        return {'User-Agent': random.choice(self.USER_AGENTS), 'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
                'Accept-Language': f'{self.language},en;q=0.9', 'DNT': '1', 'Connection': 'keep-alive'}

    def _rate_limit(self):
        now = time.time()
        elapsed = now - self._last_request_time
        min_interval = self.BASE_DELAY + random.uniform(0, 1)
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def _normalize_url(self, url: str) -> str:
        if not url: return ""
        url = url.strip()
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url

    def search_html(self, query: str, num_results: int = 5) -> List[Dict]:
        if not query or len(query.strip()) < 2: return []
        query_clean = query.strip()
        num_results = max(1, min(10, num_results))
        self._rate_limit()
        url = self.BASE_URL.rstrip('/')
        params = {'q': query_clean, 'kl': self.language, 'df': 'w', 't': 'h_ia'}
        logger.debug(f"🔍 DuckDuckGo: '{query_clean[:50]}...'")
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.post(url, data=params, headers=self._get_headers(), timeout=self.timeout,
                                             allow_redirects=True)
                if response.status_code == 200:
                    return self._parse_results(response.text, num_results)
                elif response.status_code == 429 and attempt < self.MAX_RETRIES - 1:
                    time.sleep(min(self.MAX_DELAY, self.BASE_DELAY * (2 ** attempt)) + random.uniform(0, 1))
                    continue
            except Exception as e:
                logger.error(f"❌ DuckDuckGo Error: {type(e).__name__} - {e}")
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(min(self.MAX_DELAY, self.BASE_DELAY * (2 ** attempt)) + random.uniform(0, 1))
        return [{"error": f"Búsqueda fallida", "query": query_clean}]

    def _parse_results(self, html: str, max_results: int) -> List[Dict]:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            for i, result in enumerate(soup.find_all('div', class_='result')[:max_results], 1):
                try:
                    title_elem = result.find('a', class_='result__a')
                    if not title_elem: continue
                    title = title_elem.get_text(strip=True)
                    url = self._normalize_url(title_elem.get('href', ''))
                    snippet_elem = result.find('a', class_='result__snippet')
                    snippet = snippet_elem.get_text(strip=True)[:250] if snippet_elem else ""
                    domain_elem = result.find('a', class_='result__url')
                    domain = domain_elem.get_text(strip=True) if domain_elem else ""
                    results.append({'title': title, 'url': url, 'snippet': snippet, 'domain': domain, 'position': i,
                                    'source': 'duckduckgo'})
                except Exception as e:
                    logger.debug(f"⚠️ Error parseando resultado {i}: {e}")
                    continue
            return results if results else [{"error": "No se encontraron resultados"}]
        except Exception as e:
            logger.error(f"❌ Error parseando HTML: {e}")
            return [{"error": f"Error de parsing: {str(e)}"}]

    def search(self, query: str, num_results: int = 5) -> List[Dict]:
        return self.search_html(query, num_results)

    def format_results_for_llm(self, results: List[Dict], max_snippet_length: int = 200) -> str:
        if not results or 'error' in results[0]:
            return "❌ No se encontraron resultados relevantes."
        lines = ["🌐 **Resultados web**:\n"]
        for r in results:
            if 'error' in r: continue
            title = r.get('title', 'Sin título')[:100]
            snippet = r.get('snippet', '')[:max_snippet_length]
            url = r.get('url', '')[:80]
            domain = r.get('domain', '')
            lines.append(f"• **{title}**")
            if domain: lines.append(f"  🌐 {domain}")
            if snippet: lines.append(f"  📝 {snippet}...")
            if url: lines.append(f"  🔗 {url}")
            lines.append("")
        return "\n".join(lines).strip()

    def should_trigger_general_search(self, user_input: str) -> tuple[bool, str]:
        t = user_input.lower().strip()
        general_keywords = ["noticia", "news", "actualidad", "último", "reciente", "precio", "costo", "pricing",
                            "comparativa", "review", "tutorial", "guía", "cómo hacer", "cómo usar", "documentación",
                            "docs", "ejemplo", "código"]
        security_keywords = ["cve", "vulnerabilidad", "mitre", "aws security", "azure security", "compliance",
                             "zero-day", "ransomware", "breach"]
        if any(sk in t for sk in security_keywords):
            return False, ""
        if any(gk in t for gk in general_keywords):
            return True, user_input
        return False, ""