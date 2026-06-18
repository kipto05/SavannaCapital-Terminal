"""ai_advisor/advisor.py — multi-provider LLM-backed trade suggestion agent.

Supported providers (set AI_PROVIDER in .env):
  anthropic   — Anthropic Messages API (default)
  nvidia      — NVIDIA NIM (OpenAI-compatible endpoint)
  gemini      — Google Gemini API
  openrouter  — OpenRouter (unified gateway)

3 public methods:
  .suggest()         — single trade idea
  .generate_signals() — bulk suggestions for multiple symbols
  .chat()             — research terminal queries
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from config.settings import config
from db.models import AIAdvisorSuggestion, AISide
from db.session import SessionLocal
from execution.notification_service import NotificationService
from execution.sl_tp_model import DynamicSLTPModel
from strategies.base import atr

log = logging.getLogger(__name__)


# ── Protocol (so we can inject a fake client in tests) ────────────────────────

class _LLMClient(Protocol):
    """Minimal surface our agent needs."""
    def post(self, body: dict[str, Any]) -> dict[str, Any]: ...
    @property
    def model(self) -> str: ...


# ── Provider clients ──────────────────────────────────────────────────────────

class AnthropicClient:
    """Anthropic Messages API client."""
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens

    @property
    def model(self) -> str:
        return self._model

    def post(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {"model": self._model, "max_tokens": self._max_tokens, **body}
        with httpx.Client(timeout=30.0) as client:
            r = client.post(self.API_URL, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()


class NvidiaClient:
    """NVIDIA NIM client — OpenAI-compatible endpoint.

    When ``stream=True`` is passed in the body, chunks are accumulated
    server-side and the complete text is returned as a fake OpenAI
    response dict so everything upstream is unchanged.
    """

    API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str, max_tokens: int, stream: bool = False, reasoning_budget: int = 0) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._stream = stream
        self._reasoning_budget = reasoning_budget

    @property
    def model(self) -> str:
        return self._model

    def post(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }
        # Convert Anthropic-style {system, messages} → OpenAI-style messages
        system = body.pop("system", "")
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(body.get("messages", []))
        stream_requested = body.pop("stream", self._stream)
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": stream_requested,
        }
        if "max_tokens" not in body:
            payload["max_tokens"] = self._max_tokens
        # NVIDIA reasoning/CoT extras
        if self._reasoning_budget > 0:
            payload.setdefault("extra_body", {})
            payload["extra_body"].setdefault("chat_template_kwargs", {})["enable_thinking"] = True
            payload["extra_body"]["reasoning_budget"] = self._reasoning_budget
        payload.update({k: v for k, v in body.items() if k not in ("system", "messages", "stream")})

        with httpx.Client(timeout=60.0) as client:
            if stream_requested:
                return self._stream_response(client, payload, headers)
            r = client.post(self.API_URL, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()

    def _stream_response(self, client: httpx.Client, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        """Accumulate all chunks and return as a synthetic OpenAI response."""
        full_content: list[str] = []
        with client.stream("POST", self.API_URL, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = (chunk.get("choices", [{}])[0].get("delta") or {})
                # Reasoning content (CoT models) streams separately
                if "reasoning_content" in delta:
                    log.debug("NvidiaClient: reasoning chunk len=%d", len(delta["reasoning_content"]))
                if delta.get("content"):
                    full_content.append(delta["content"])
        return {
            "choices": [{
                "message": {
                    "content": "".join(full_content),
                    "role": "assistant",
                },
                "finish_reason": "stop",
            }],
        }


class GeminiClient:
    """Google Gemini API client."""
    API_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens

    @property
    def model(self) -> str:
        return self._model

    def post(self, body: dict[str, Any]) -> dict[str, Any]:
        system = body.pop("system", "")
        user_msg = ""
        for msg in body.get("messages", []):
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")
                break
        # Gemini format: contents array with parts
        contents = [{"parts": [{"text": user_msg}]}]
        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["system_instruction"] = {"parts": [{"text": system}]}
        payload["generationConfig"] = {"maxOutputTokens": self._max_tokens}
        url = self.API_URL_TMPL.format(model=self._model, key=self._api_key)
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json()


class OpenRouterClient:
    """OpenRouter unified gateway — OpenAI-compatible."""
    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens

    @property
    def model(self) -> str:
        return self._model

    def post(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
            "HTTP-Referer": "https://savannacapital.ai",
            "X-Title": "Savanna Capital Quant OS",
        }
        system = body.pop("system", "")
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(body.get("messages", []))
        payload: dict[str, Any] = {"model": self._model, "messages": messages}
        if "max_tokens" not in body:
            payload["max_tokens"] = self._max_tokens
        payload.update({k: v for k, v in body.items() if k not in ("system", "messages")})
        with httpx.Client(timeout=30.0) as client:
            r = client.post(self.API_URL, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()


# ── Client factory ────────────────────────────────────────────────────────────

_PROVIDERS: dict[str, type] = {
    "anthropic": AnthropicClient,
    "nvidia": NvidiaClient,
    "gemini": GeminiClient,
    "openrouter": OpenRouterClient,
}


def _get_api_key(provider: str) -> str | None:
    """Return the configured API key for the given provider."""
    env_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    env_var = env_map.get(provider)
    if not env_var:
        return None
    # Try env first (for live .env), then config (for loaded .env)
    return os.environ.get(env_var) or getattr(config.ai, f"{provider}_api_key", "")


def _default_client(use_case: str = "suggest") -> _LLMClient | None:
    """Return a real LLM client for the configured provider, or None if no key.

    ``use_case`` controls which per-use-case config overrides are applied:
    - "suggest" → trade suggestions endpoint
    - "chat"    → research terminal endpoint
    """
    provider = (config.ai.provider or "anthropic").lower()
    api_key = _get_api_key(provider)
    if not api_key:
        log.warning("AIAdvisor: no API key for provider=%r — unavailable", provider)
        return None
    client_cls = _PROVIDERS.get(provider)
    if client_cls is None:
        log.warning("AIAdvisor: unknown provider=%r — falling back to anthropic", provider)
        client_cls = AnthropicClient
        api_key = _get_api_key("anthropic") or ""
        if not api_key:
            return None
    # Resolve effective settings for this use case
    model = config.ai.effective_model(use_case)
    max_tokens = config.ai.effective_max_tokens(use_case)
    stream = config.ai.effective_stream(use_case)
    reasoning_budget = config.ai.effective_reasoning_budget(use_case)
    if provider == "nvidia":
        return client_cls(
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            stream=stream,
            reasoning_budget=reasoning_budget,
        )
    return client_cls(api_key=api_key, model=model, max_tokens=max_tokens)


# ── Text extraction (provider-agnostic) ───────────────────────────────────────

def _extract_text(response: dict[str, Any]) -> str:
    """Extract raw text from any provider's response."""
    # Anthropic
    if "content" in response:
        for block in response.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "")
    # OpenAI-compatible (NVIDIA, OpenRouter) — guard against empty choices
    choices = response.get("choices", [])
    if choices:
        msg = (choices[0] or {}).get("message") or {}
        content = msg.get("content")
        if content:
            return str(content)
    # Gemini
    candidates = response.get("candidates", [])
    if candidates:
        parts = (candidates[0] or {}).get("content", {}).get("parts", [])
        for p in parts:
            if isinstance(p, dict) and "text" in p:
                return str(p["text"])
    return ""


# ── Response parsers ──────────────────────────────────────────────────────────

def _parse_suggest_response(text: str) -> dict[str, Any] | None:
    """Extract structured suggestion from free-form LLM text.
    Tolerant of markdown fences and extra prose.
    """
    try:
        clean = text.strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            while lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean = "\n".join(lines)
        data = json.loads(clean)
        required = {"symbol", "side", "confidence"}
        if not required.issubset(data.keys()):
            log.warning("AIAdvisor: response missing keys: %s", required - data.keys())
            return None
        side_raw = str(data["side"]).upper()
        if side_raw not in ("BUY", "SELL"):
            side_raw = "BUY" if side_raw in ("LONG", "UP") else "SELL"
        try:
            side_enum = AISide(side_raw)
        except ValueError:
            side_enum = AISide.BUY
        return {
            "symbol": str(data["symbol"]).upper(),
            "side": side_enum,
            "side_raw": side_raw,
            "confidence": float(data.get("confidence", 0.5)),
            "timeframe": data.get("timeframe", "M15"),
            "reasoning": data.get("reasoning", ""),
            "market_context": data.get("market_context") or {},
            "entry": data.get("entry"),
            "sl": data.get("sl"),
            "tp1": data.get("tp1"),
            "tp2": data.get("tp2"),
        }
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        log.warning("AIAdvisor: parse failed: %s — text[:120]=%s", exc, text[:120])
        return None


def _parse_chat_response(text: str) -> dict[str, Any]:
    """Parse chat terminal response. Falls back to raw text if JSON parse fails."""
    try:
        clean = text.strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            while lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean = "\n".join(lines)
        data = json.loads(clean)
        return {
            "response": data.get("response", text),
            "sql": data.get("sql"),
        }
    except (json.JSONDecodeError, ValueError):
        return {"response": text, "sql": None}


# ── System prompts ────────────────────────────────────────────────────────────

def _suggest_system_prompt() -> str:
    return """
You are a quantitative trading analyst for Savanna Capital.
Your role is to analyse market conditions and produce structured trade suggestions.
Always respond with a JSON object — never plain text.

Required JSON schema:
{
  "symbol": "BTCUSD",
  "side": "BUY",
  "confidence": 0.85,
  "timeframe": "M15",
  "reasoning": "2-sentence summary of the setup",
  "market_context": {
    "trend": "bullish",
    "volatility": "normal",
    "key_levels": ["42000", "43000"]
  },
  "entry": 42500.0,
  "sl": 41800.0,
  "tp1": 43500.0,
  "tp2": 44500.0
}

Rules:
- confidence must be a float 0.0..1.0
- side must be exactly "BUY" or "SELL"
- reasoning must be <= 2 sentences
- If no clear signal, set confidence below 0.5 with the lowest-conviction direction.
""".strip()


def _chat_system_prompt() -> str:
    return """
You are a quantitative research assistant for Savanna Capital's trading desk.
You have access to:
- HFT execution logs
- TickData v5.4 historical market data
- Strategy performance metrics
- AI-generated trade signals

When answering:
- Be concise and technical
- Include SQL snippets when querying data would help (prefix with `sql:`)
- Reference specific metrics (win rate, Sharpe, drawdown) when relevant
- If you don't know something, say so clearly
""".strip()


# ── Core agent ────────────────────────────────────────────────────────────────

class AIAgent:
    """Core AI advisor agent.

    Public methods:
      .suggest(symbol, timeframe, df, stats) -> AIAdvisorSuggestion | None
      .generate_signals(symbols, tf, dfs, stats_map) -> list[AIAdvisorSuggestion]
      .chat(query, context) -> dict{response, sql?}
      .is_enabled() -> bool
    """

    def __init__(self) -> None:
        self._client: _LLMClient | None = None
        self._last_suggestion_time: dict[str, datetime] = {}
        self._cooldown_seconds = config.ai.cooldown_minutes * 60

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def _ensure_client(self, use_case: str = "suggest") -> None:
        """Build or reuse the LLM client for the given use case."""
        cache_key = f"{config.ai.provider}:{use_case}:{config.ai.effective_model(use_case)}"
        if self._client is not None and getattr(self, "_client_key", None) == cache_key:
            return
        self._client = _default_client(use_case)
        self._client_key = cache_key
        if self._client is None:
            log.warning("AIAgent: no LLM client available (%s) — calls will be skipped", use_case)

    def is_enabled(self) -> bool:
        """Return True if an API key is configured for the active provider."""
        return bool(config.ai.enabled)

    # ── Single suggestion ─────────────────────────────────────────────────

    def suggest(
        self,
        symbol: str,
        timeframe: str,
        df: Any | None = None,
        stats: dict[str, Any] | None = None,
    ) -> AIAdvisorSuggestion | None:
        """Generate a single trade suggestion for symbol/timeframe.

        Always persists an AIAdvisorSuggestion + pseudo-Trade to the DB
        on success, regardless of whether the AI strategy is toggled on.
        """
        self._ensure_client(use_case="suggest")
        if self._client is None:
            return None

        # ── Cooldown ──────────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        last = self._last_suggestion_time.get(symbol)
        if last and (now - last).total_seconds() < self._cooldown_seconds:
            log.debug(
                "AIAgent: cooldown for %s (%.0fs remaining)",
                symbol,
                self._cooldown_seconds - (now - last).total_seconds(),
            )
            return None

        # ── Build context from DataFrame ──────────────────────────────────
        market_snapshot = ""
        if df is not None and hasattr(df, "tail") and len(df) >= 5:
            try:
                tail = df.tail(5)
                close = float(tail["close"].iloc[-1])
                high = float(tail["high"].iloc[-1])
                low = float(tail["low"].iloc[-1])
                rng = high - low if high > low else close * 0.001
                chg = (
                    float(tail["close"].iloc[-1]) - float(tail["close"].iloc[0])
                ) / float(tail["close"].iloc[0])
                market_snapshot = (
                    f"Latest OHLCV snapshot for {symbol} ({timeframe}):\n"
                    f" close={close:.5f}, high={high:.5f}, low={low:.5f}, range={rng:.5f}\n"
                    f" 5-bar change: {chg * 100:+.2f}%\n"
                )
            except Exception as exc:
                log.debug("AIAgent: snapshot build failed for %s: %s", symbol, exc)

        stats_summary = ""
        if stats:
            wr = stats.get("win_rate", 0) * 100
            stats_summary = (
                f"\nStrategy context: win_rate={wr:.1f}%, "
                f"trades={stats.get('total_trades', 0)}, "
                f"sharpe={stats.get('sharpe', 'N/A')}\n"
            )

        user_prompt = (
            f"Analyse {symbol} on {timeframe} and provide a trade suggestion.\n"
            f"{market_snapshot}{stats_summary}"
        )

        # ── Call LLM ──────────────────────────────────────────────────────
        try:
            response = self._client.post(
                {
                    "system": _suggest_system_prompt(),
                    "messages": [{"role": "user", "content": user_prompt}],
                    "temperature": 0.3,
                }
            )
            text = _extract_text(response)
            parsed = _parse_suggest_response(text)
            if parsed is None:
                log.warning("AIAgent: unparseable suggestion for %s", symbol)
                return None

            # ── Compute SL/TP via DynamicSLTPModel ────────────────────────
            sltp = DynamicSLTPModel()
            entry_price: float | None = None
            if parsed.get("entry"):
                entry_price = float(parsed["entry"])
            elif df is not None and hasattr(df, "tail") and len(df) >= 1:
                try:
                    entry_price = float(df["close"].iloc[-1])
                except Exception:
                    pass

            sd: float | None = None
            regime: str = "trending"
            if (
                df is not None
                and hasattr(df, "tail")
                and len(df) >= config.sltp.atr_period
            ):
                try:
                    sd = float(atr(df, config.sltp.atr_period).iloc[-1])
                    atr_pct = (
                        sd / entry_price if entry_price and entry_price > 0 else 0.001
                    )
                    if atr_pct < config.sltp.atr_pct_ranging_thresh:
                        regime = "ranging"
                    elif atr_pct > config.sltp.atr_pct_volatile_thresh:
                        regime = "volatile"
                except Exception as exc:
                    log.debug("AIAgent: ATR compute failed for %s: %s", symbol, exc)

            if entry_price and sd:
                try:
                    sltp_result = sltp.compute(
                        df=df,
                        side=parsed["side_raw"],
                        entry=entry_price,
                        atr=sd,
                        regime=regime,
                    )
                    if sltp_result:
                        parsed["sl"] = sltp_result.sl
                        parsed["tp1"] = sltp_result.tp1
                        parsed["tp2"] = sltp_result.tp2
                except Exception as exc:
                    log.debug(
                        "AIAgent: SL/TP compute failed for %s: %s", symbol, exc
                    )

            # ── Persist to DB ──────────────────────────────────────────────
            self._last_suggestion_time[symbol] = now
            suggestion = self._persist(parsed, symbol, timeframe)
            self._persist_pseudo_trade(suggestion, entry_price, regime)

            # Publish ai_suggestion notification
            try:
                with SessionLocal() as db:
                    ns = NotificationService(db)
                    ns.publish(
                        event_type="ai_suggestion",
                        title=f"AI Suggestion: {symbol} {parsed['side_raw']}",
                        message=f"AI suggests {parsed['side_raw']} on {symbol} with {parsed['confidence']:.0%} confidence: {parsed.get('reasoning', '')}",
                        data={
                            "symbol": symbol,
                            "side": parsed['side_raw'],
                            "confidence": float(parsed['confidence']),
                            "reasoning": parsed.get('reasoning', ''),
                            "timeframe": timeframe,
                        }
                    )
            except Exception as exc:
                log.exception("Failed to publish ai_suggestion notification: %s", exc)

            log.info(
                "AIAgent: suggestion %s %s conf=%.0f%%",
                symbol,
                parsed["side_raw"],
                parsed["confidence"] * 100,
            )
            return suggestion

        except httpx.HTTPStatusError as exc:
            log.error(
                "AIAgent: LLM request failed for %s: HTTP %s",
                symbol,
                exc.response.status_code,
            )
            return None
        except Exception as exc:
            log.exception("AIAgent: suggest failed for %s: %s", symbol, exc)
            return None

    # ── Bulk suggestions ─────────────────────────────────────────────────

    def generate_signals(
        self,
        symbols: list[str],
        timeframe: str = "M15",
        data: dict[str, Any] | None = None,
    ) -> list[AIAdvisorSuggestion]:
        """Run suggest() for each symbol. Returns list of succeeded suggestions."""
        results: list[AIAdvisorSuggestion] = []
        for sym in symbols:
            try:
                df = data.get(sym) if data else None
                sugg = self.suggest(sym, timeframe, df=df)
                if sugg is not None:
                    results.append(sugg)
            except Exception as exc:
                log.error("AIAgent: bulk suggest failed for %s: %s", sym, exc)
            time.sleep(0.3)
        return results

    # ── Chat ──────────────────────────────────────────────────────────────

    def chat(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a query to the research terminal.

        Args:
            query: user message
            context: optional {symbol, timeframe, stats} for the LLM
        Returns:
            {"response": str, "sql": str | None}
        """
        self._ensure_client(use_case="chat")
        if self._client is None:
            return {
                "response": "AI assistant is not configured (no API key for provider).",
                "sql": None,
            }

        context_blob = ""
        if context:
            parts = [f"{k}: {v}" for k, v in context.items() if v is not None]
            if parts:
                context_blob = "\nCurrent context: " + ", ".join(parts) + "\n"

        try:
            response = self._client.post(
                {
                    "system": _chat_system_prompt(),
                    "messages": [
                        {"role": "user", "content": context_blob + query}
                    ],
                    "temperature": 0.2,
                }
            )
            text = _extract_text(response)
            parsed = _parse_chat_response(text)
            log.info("AIAgent: chat query len=%d", len(query))
            return parsed
        except Exception as exc:
            log.exception("AIAgent: chat failed: %s", exc)
            return {"response": f"Error: {exc}", "sql": None}

    # ── Private persistence ───────────────────────────────────────────────

    def _persist(
        self,
        parsed: dict[str, Any],
        symbol: str,
        timeframe: str,
    ) -> AIAdvisorSuggestion:
        """Write an AIAdvisorSuggestion row to the database."""
        db = SessionLocal()
        try:
            # Merge top-level entry/sl/tp into market_context so frontend can read them
            mc = parsed.get("market_context") or {}
            mc.setdefault("entry", parsed.get("entry"))
            mc.setdefault("sl", parsed.get("sl"))
            mc.setdefault("tp1", parsed.get("tp1"))
            mc.setdefault("tp2", parsed.get("tp2"))
            row = AIAdvisorSuggestion(
                symbol=symbol,
                timeframe=timeframe,
                side=parsed["side"],
                confidence=parsed["confidence"],
                reasoning=parsed.get("reasoning"),
                market_context=mc,
                raw_response=None,
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            return row
        finally:
            db.close()

    def _persist_pseudo_trade(
        self,
        suggestion: AIAdvisorSuggestion,
        entry_price: float | None,
        regime: str,
    ) -> None:
        """Write a pseudo-Trade row so AI activity appears in strategy stats."""
        from db.models import Trade

        db = SessionLocal()
        try:
            side_val = suggestion.side
            if hasattr(side_val, "value"):
                side_val = side_val.value
            trade = Trade(
                symbol=suggestion.symbol,
                timeframe=suggestion.timeframe,
                side=side_val,
                strategy_name="ai_trading",
                entry=entry_price,
                sl=getattr(suggestion, "sl", None),
                tp=getattr(suggestion, "tp2", None),
                tp1=getattr(suggestion, "tp1", None),
                tp2=None,
                lot_size=0.01,
                pnl_r=None,
                pnl_usd=None,
                tag=f"ai_suggestion.{suggestion.id}",
                closed_reason="pending_ai",
                metadata={
                    "source": "ai_advisor",
                    "ai_suggestion_id": suggestion.id,
                    "regime": regime,
                    "confidence": suggestion.confidence,
                },
            )
            db.add(trade)
            db.flush()
            log.debug(
                "AIAgent: pseudo-trade written id=%d symbol=%s",
                trade.id,
                suggestion.symbol,
            )
        except Exception as exc:
            log.error("AIAgent: pseudo-trade persist failed: %s", exc)
        finally:
            db.close()


# ── Module-level singleton ────────────────────────────────────────────────────

agent = AIAgent()