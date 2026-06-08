# -*- coding: utf-8 -*-
# tools/security_search.py
"""AgentEagle - SecuritySearch Engine v2.1
Motor de búsqueda inteligente orientado a ciberseguridad.

Features:
• Query enrichment con traducción ES→EN
• Source ranking por tiers de confianza
• Scoring multi-factor (keywords, dominio, snippet, frescura)
• Cache determinista con TTL configurable
• Output estructurado para consumo programático
"""

import hashlib
import logging
import re
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum, auto
from dataclasses import dataclass, field

try:
    from ddgs import DDGS

    DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS

        DDGS_AVAILABLE = True
        logging.warning("⚠️ Usando duckduckgo_search legacy. Actualiza: pip install ddgs")
    except ImportError:
        DDGS_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class SearchCategory(Enum):
    """Categorías de búsqueda soportadas."""
    CVE = auto()
    MITRE = auto()
    CLOUD_AWS = auto()
    CLOUD_AZURE = auto()
    CLOUD_GCP = auto()
    COMPLIANCE = auto()
    ZERO_DAY = auto()
    GENERAL = auto()


class SourceTier(Enum):
    """Niveles de confianza para fuentes."""
    TIER_1 = "tier1"
    TIER_2 = "tier2"
    TIER_3 = "tier3"
    TIER_4 = "tier4"
    UNKNOWN = "unknown"


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class SearchResult:
    """Resultado de búsqueda enriquecido."""
    title: str
    url: str
    snippet: str
    domain: str
    score: float
    source_tier: SourceTier
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "domain": self.domain,
            "score": round(self.score, 3),
            "source_tier": self.source_tier.value,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class SearchResponse:
    """Respuesta estructurada del motor de búsqueda."""
    query_original: str
    query_enriched: str
    category: str
    results: List[SearchResult]
    confidence: float
    total_results: int
    execution_time_ms: float
    cache_hit: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_original": self.query_original,
            "query_enriched": self.query_enriched,
            "category": self.category,
            "results": [r.to_dict() for r in self.results],
            "confidence": round(self.confidence, 3),
            "total_results": self.total_results,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "cache_hit": self.cache_hit
        }


# ============================================================================
# CONFIGURACIÓN DE FUENTES POR TIER
# ============================================================================

SOURCE_TIERS: Dict[str, SourceTier] = {
    "cve.mitre.org": SourceTier.TIER_1,
    "nvd.nist.gov": SourceTier.TIER_1,
    "cisa.gov": SourceTier.TIER_1,
    "attack.mitre.org": SourceTier.TIER_1,
    "mitre.org": SourceTier.TIER_1,
    "docs.aws.amazon.com": SourceTier.TIER_2,
    "aws.amazon.com": SourceTier.TIER_2,
    "learn.microsoft.com": SourceTier.TIER_2,
    "azure.microsoft.com": SourceTier.TIER_2,
    "cloud.google.com": SourceTier.TIER_2,
    "console.cloud.google.com": SourceTier.TIER_2,
    "thehackernews.com": SourceTier.TIER_3,
    "bleepingcomputer.com": SourceTier.TIER_3,
    "securityweek.com": SourceTier.TIER_3,
    "darkreading.com": SourceTier.TIER_3,
    "threatpost.com": SourceTier.TIER_3,
    "krebsonsecurity.com": SourceTier.TIER_3,
    "theregister.com": SourceTier.TIER_3,
    "cybersecuritynews.com": SourceTier.TIER_3,
    "opencve.io": SourceTier.TIER_3,
    "cvedetails.com": SourceTier.TIER_3,
    "threatprotect.qualys.com": SourceTier.TIER_3,
    "security.googleblog.com": SourceTier.TIER_3,
    "github.com": SourceTier.TIER_4,
    "wikipedia.org": SourceTier.TIER_4,
    "stackoverflow.com": SourceTier.TIER_4,
}

BLACKLISTED_DOMAINS = {
    "facebook.com", "pinterest.com", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "linkedin.com", "reddit.com"
}

QUERY_TRANSLATIONS: Dict[str, str] = {
    "último": "latest", "última": "latest", "reciente": "recent",
    "nuevo": "new", "nueva": "new", "cómo": "how to", "como": "how to",
    "proteger": "protect", "seguridad": "security",
    "mejores prácticas": "best practices", "mejores practicas": "best practices",
    "ejemplo": "example", "ejemplos": "examples",
    "política": "policy", "politica": "policy",
    "mínimo privilegio": "least privilege", "minimo privilegio": "least privilege",
    "capacidades": "capabilities", "detección": "detection", "deteccion": "detection",
    "recomendaciones": "recommendations", "características": "features",
    "caracteristicas": "features", "controles": "controls",
    "vulnerabilidad": "vulnerability", "zero-day": "zero-day",
    "día cero": "zero-day", "exploit": "exploit",
    "parche": "patch", "mitigación": "mitigation", "mitigacion": "mitigation",
    "crítico": "critical", "critico": "critical",
    "comando": "command", "centro de seguridad": "security command center",
}


# ============================================================================
# CLASE PRINCIPAL
# ============================================================================

class SecuritySearch:
    """Motor de búsqueda inteligente para ciberseguridad."""

    SCORING_WEIGHTS = {
        "keyword_match": 0.35,
        "domain_authority": 0.30,
        "snippet_relevance": 0.20,
        "freshness": 0.15,
    }

    def __init__(self, timeout: int = 10, cache_ttl_hours: int = 24):
        self.timeout = timeout
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self._cache: Dict[str, Tuple[List[Dict], datetime]] = {}
        self._initialized = DDGS_AVAILABLE

        if self._initialized:
            logger.info("🔐 SecuritySearch v2.1 inicializado (cache determinista)")
        else:
            logger.warning("⚠️ ddgs/duckduckgo_search no disponible")

    @staticmethod
    def normalize_query(query: str) -> str:
        """Normaliza query para caché determinista."""
        normalized = query.lower().strip()
        normalized = unicodedata.normalize('NFKD', normalized)
        normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
        normalized = re.sub(r'[^\w\s\-]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        words = normalized.split()
        words.sort()
        return ' '.join(words)

    @staticmethod
    def _generate_cache_key(normalized_query: str, category: str) -> str:
        """Genera cache key determinista basada SOLO en normalized_query + category."""
        key_content = f"{normalized_query}|{category.lower()}"
        return hashlib.sha256(key_content.encode('utf-8')).hexdigest()[:16]

    def _is_cache_valid(self, timestamp: datetime) -> bool:
        return datetime.now() - timestamp < self.cache_ttl

    def _cleanup_cache(self):
        expired_keys = [k for k, (_, ts) in self._cache.items() if not self._is_cache_valid(ts)]
        for k in expired_keys:
            del self._cache[k]
        if expired_keys:
            logger.debug(f"🧹 Cache cleanup: {len(expired_keys)} entradas expiradas")

    @staticmethod
    def classify_query(query: str) -> SearchCategory:
        """Clasifica automáticamente la intención de la query."""
        q = query.lower()

        if re.search(r'cve-\d{4}-\d+', q):
            return SearchCategory.CVE
        if re.search(r'[tT]\d{4}(\.\d{3})?', q) or any(kw in q for kw in ["mitre", "att&ck", "attack framework"]):
            return SearchCategory.MITRE
        if any(kw in q for kw in ["zero-day", "0-day", "día cero", "unknown vulnerability", "active exploitation"]):
            return SearchCategory.ZERO_DAY
        if any(kw in q for kw in ["aws", "amazon web services", "ec2", "s3", "iam", "lambda"]):
            return SearchCategory.CLOUD_AWS
        if any(kw in q for kw in ["azure", "microsoft azure", "entra", "defender for cloud"]):
            return SearchCategory.CLOUD_AZURE
        if any(kw in q for kw in ["gcp", "google cloud", "cloud kms", "security command center"]):
            return SearchCategory.CLOUD_GCP
        if any(kw in q for kw in ["cis", "nist", "iso 27001", "pci dss", "hipaa", "gdpr", "compliance"]):
            return SearchCategory.COMPLIANCE
        return SearchCategory.GENERAL

    def _enrich_query(self, query: str, category: SearchCategory) -> str:
        """Enriquece la query: traduce ES→EN, expande términos."""
        enriched = query.lower()
        for es_term, en_term in QUERY_TRANSLATIONS.items():
            enriched = re.sub(r'\b' + re.escape(es_term) + r'\b', en_term, enriched, flags=re.I)
        if category == SearchCategory.CLOUD_GCP:
            enriched = re.sub(r'\bsecurity\s+command\s+center\b', 'security-command-center', enriched)
        site_filters = {
            SearchCategory.CVE: "site:nvd.nist.gov OR site:cve.mitre.org",
            SearchCategory.MITRE: "site:attack.mitre.org",
            SearchCategory.CLOUD_AWS: "site:docs.aws.amazon.com",
            SearchCategory.CLOUD_AZURE: "site:learn.microsoft.com",
            SearchCategory.CLOUD_GCP: "site:cloud.google.com",
            SearchCategory.COMPLIANCE: "site:cisecurity.org OR site:csrc.nist.gov",
        }
        if category in site_filters:
            import random
            if random.random() < 0.5:
                enriched = f"{enriched} {site_filters[category]}"
        return enriched.strip()

    def _get_source_tier(self, url: str) -> SourceTier:
        """Obtiene el tier de confianza para una URL."""
        domain = url.lower()
        for blacklisted in BLACKLISTED_DOMAINS:
            if blacklisted in domain:
                return SourceTier.UNKNOWN
        for known_domain, tier in SOURCE_TIERS.items():
            if known_domain in domain or domain in known_domain:
                return tier
        return SourceTier.TIER_4

    def _calculate_score(self, result: Dict[str, str], keywords: List[str], category: SearchCategory) -> float:
        """Calcula score multi-factor para un resultado."""
        content = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('url', '')}".lower()
        keyword_score = sum(1 for kw in keywords if kw.lower() in content) / max(len(keywords), 1)
        domain_score_map = {
            SourceTier.TIER_1: 1.0, SourceTier.TIER_2: 0.8, SourceTier.TIER_3: 0.6,
            SourceTier.TIER_4: 0.3, SourceTier.UNKNOWN: 0.0,
        }
        domain_score = domain_score_map.get(self._get_source_tier(result.get('url', '')), 0.0)
        snippet = result.get('snippet', '')
        snippet_score = min(len(snippet) / 200, 1.0) * 0.5
        snippet_score += (sum(1 for kw in keywords if kw.lower() in snippet.lower()) / max(len(keywords), 1)) * 0.5
        current_year = str(datetime.now().year)
        freshness_score = 1.0 if current_year in content else 0.7
        weights = self.SCORING_WEIGHTS
        total_score = (
                weights["keyword_match"] * keyword_score +
                weights["domain_authority"] * domain_score +
                weights["snippet_relevance"] * snippet_score +
                weights["freshness"] * freshness_score
        )
        return min(max(total_score, 0.0), 1.0)

    def search(self, query: str, num_results: int = 5,
               category: Optional[Union[str, SearchCategory]] = None) -> SearchResponse:
        """Ejecuta búsqueda enriquecida con scoring y ranking."""
        start_time = time.time()
        if not self._initialized:
            return SearchResponse(query_original=query, query_enriched=query, category="unknown",
                                  results=[], confidence=0.0, total_results=0, execution_time_ms=0, cache_hit=False)

        if category is None:
            search_category = self.classify_query(query)
        elif isinstance(category, SearchCategory):
            search_category = category
        elif isinstance(category, str):
            cat_upper = category.upper()
            if cat_upper in SearchCategory.__members__:
                search_category = SearchCategory[cat_upper]
            else:
                search_category = self.classify_query(query)
        else:
            search_category = self.classify_query(query)

        normalized = self.normalize_query(query)
        cache_key = self._generate_cache_key(normalized, search_category.name)
        cache_hit = False

        if cache_key in self._cache:
            cached_results, cached_ts = self._cache[cache_key]
            if self._is_cache_valid(cached_ts):
                logger.info(f"📦 Cache HIT: key={cache_key} | query='{query[:40]}...'")
                cache_hit = True
                results_raw = cached_results
            else:
                logger.debug(f"🗑️ Cache EXPIRED: key={cache_key}")
                del self._cache[cache_key]
                results_raw = None
        else:
            logger.info(f"🔍 Cache MISS: key={cache_key} | query='{query[:40]}...'")
            results_raw = None

        if not results_raw:
            enriched_query = self._enrich_query(query, search_category)
            logger.debug(f"📝 Query enriched: {enriched_query[:80]}...")
            try:
                with DDGS(timeout=self.timeout) as ddgs:
                    results_raw = list(ddgs.text(enriched_query, max_results=num_results * 2))
                if not results_raw:
                    logger.debug("🔄 Fallback: trying original query")
                    with DDGS(timeout=self.timeout) as ddgs:
                        results_raw = list(ddgs.text(query, max_results=num_results * 2))
                if results_raw:
                    self._cache[cache_key] = (results_raw, datetime.now())
                    self._cleanup_cache()
                    logger.info(f"💾 Cache SET: key={cache_key} | {len(results_raw)} resultados")
            except Exception as e:
                logger.error(f"❌ Error en búsqueda: {type(e).__name__}: {e}")
                results_raw = []

        keywords = query.split()
        scored_results = []
        for raw in results_raw[:num_results]:
            url = raw.get('href', '')
            if self._get_source_tier(url) == SourceTier.UNKNOWN:
                continue
            score = self._calculate_score(raw, keywords, search_category)
            tier = self._get_source_tier(url)
            scored_results.append(SearchResult(
                title=raw.get('title', '')[:200], url=url, snippet=raw.get('body', '')[:300],
                domain=url.split('/')[2] if url else '', score=score, source_tier=tier))

        scored_results.sort(key=lambda r: r.score, reverse=True)
        if scored_results:
            avg_score = sum(r.score for r in scored_results) / len(scored_results)
            tier_bonus = 0.2 if any(r.source_tier == SourceTier.TIER_1 for r in scored_results) else 0
            confidence = min(avg_score + tier_bonus, 1.0)
        else:
            confidence = 0.0

        execution_time = (time.time() - start_time) * 1000
        return SearchResponse(
            query_original=query, query_enriched=self._enrich_query(query, search_category),
            category=search_category.name.lower(), results=scored_results,
            confidence=confidence, total_results=len(results_raw),
            execution_time_ms=execution_time, cache_hit=cache_hit)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del caché."""
        valid = sum(1 for _, ts in self._cache.values() if self._is_cache_valid(ts))
        return {
            "total_entries": len(self._cache), "valid_entries": valid,
            "expired_entries": len(self._cache) - valid,
            "cache_ttl_hours": self.cache_ttl.total_seconds() / 3600,
        }

    def clear_cache(self):
        """Limpia todo el caché."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"🗑️ Cache cleared: {count} entradas eliminadas")

    @staticmethod
    def format_for_llm(response: SearchResponse, max_results: int = 3) -> str:
        """Formatea resultados para inyección en prompt de LLM."""
        if not response.results:
            return "⚠️ No se encontró información actualizada en fuentes confiables."
        lines = [f"🔍 Query: {response.query_enriched}", f"📊 Confidence: {response.confidence:.1%}", ""]
        for i, r in enumerate(response.results[:max_results], 1):
            tier_emoji = {"tier1": "🏆", "tier2": "✅", "tier3": "📰", "tier4": "🌐"}.get(r.source_tier.value, "❓")
            lines.append(f"{i}. {tier_emoji} **{r.title}**")
            lines.append(f"   🌐 {r.domain} | ⭐ Score: {r.score:.2f} | 🔗 {r.url[:80]}")
            if r.snippet:
                lines.append(f"   📝 {r.snippet[:180]}...")
            lines.append("")
        return "\n".join(lines).strip()

    # ========================================================================
    # ✅ MÉTODO AGREGADO: should_trigger_security_search
    # ========================================================================
    def should_trigger_security_search(self, user_input: str) -> Tuple[bool, str, Optional[str]]:
        """
        Detecta si una query requiere búsqueda de seguridad web.

        Returns:
            Tuple[bool, str, Optional[str]]: (should_search, enriched_query, category)
        """
        t = user_input.lower()
        trigger_keywords = [
            "cve", "vulnerability", "exploit", "zero-day", "0-day",
            "mitre", "att&ck", "t1059", "t1078",
            "aws security", "azure security", "gcp security",
            "cis benchmark", "nist", "compliance",
            "último", "reciente", "nuevo", "latest", "recent"
        ]
        if not any(kw in t for kw in trigger_keywords):
            return False, user_input, None

        category = None
        if re.search(r'cve-\d{4}-\d+', t, re.I):
            category = "cve"
        elif re.search(r'[tT]\d{4}(\.\d{3})?', t) or "mitre" in t:
            category = "mitre"
        elif any(kw in t for kw in ["aws", "amazon web services", "ec2", "s3", "iam"]):
            category = "aws"
        elif any(kw in t for kw in ["azure", "microsoft azure", "entra"]):
            category = "azure"
        elif any(kw in t for kw in ["gcp", "google cloud"]):
            category = "gcp"
        elif any(kw in t for kw in ["cis", "nist", "iso", "compliance"]):
            category = "compliance"
        elif any(kw in t for kw in ["zero-day", "0-day", "exploit"]):
            category = "zero-day"
        else:
            category = "general"

        search_category = SearchCategory[
            category.upper()] if category and category.upper() in SearchCategory.__members__ else SearchCategory.GENERAL
        search_query = self._enrich_query(user_input, search_category)
        return True, search_query, category