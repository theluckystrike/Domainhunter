"""Token-bucket rate limiter for async API calls.

Supports per-TLD rate limiting (RDAP) and per-service rate limiting
(Dynadot, DataForSEO, DeepSeek). All state lives in class instances --
no global mutable state.

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops/waits,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Frozen config (immutable -- NASA Rule 2)
_MAX_WAIT_SECONDS: Final[float] = 60.0
_MAX_SPIN_ITERATIONS: Final[int] = 600  # 600 * 0.1s = 60s ceiling


@dataclass(frozen=True)
class RateConfig:
    """Immutable rate definition: tokens per second and burst capacity."""
    tokens_per_second: float
    capacity: int

TLD_RATE_CONFIGS: Final[MappingProxyType[str, RateConfig]] = MappingProxyType({
    ".com": RateConfig(10.0 / 60.0, 2),   # Verisign: 10/min
    ".net": RateConfig(10.0 / 60.0, 2),   # Verisign: 10/min
    ".org": RateConfig(20.0 / 60.0, 3),   # PIR: 20/min
    ".io":  RateConfig(15.0 / 60.0, 2),   # 15/min
    ".ai":  RateConfig(15.0 / 60.0, 2),   # 15/min
    ".co":  RateConfig(15.0 / 60.0, 2),   # 15/min
    ".dev": RateConfig(15.0 / 60.0, 2),   # 15/min
})

SERVICE_RATE_CONFIGS: Final[MappingProxyType[str, RateConfig]] = MappingProxyType({
    "rdap":       RateConfig(2.0, 5),
    "dynadot":    RateConfig(1.0, 3),
    "dataforseo": RateConfig(5.0, 10),
    "deepseek":   RateConfig(5.0, 10),
})

_DEFAULT_TLD_CONFIG: Final[RateConfig] = RateConfig(10.0 / 60.0, 2)
_DEFAULT_SERVICE_CONFIG: Final[RateConfig] = RateConfig(1.0, 3)


class TokenBucketRateLimiter:
    """Classic token-bucket with async waiting."""

    __slots__ = ("_rate", "_capacity", "_tokens", "_last_refill", "_lock")

    def __init__(self, rate: float, capacity: int) -> None:
        assert rate > 0, f"rate must be positive, got {rate}"
        assert capacity >= 1, f"capacity must be >= 1, got {capacity}"
        self._rate: float = rate
        self._capacity: int = capacity
        self._tokens: float = float(capacity)
        self._last_refill: float = time.monotonic()
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def tokens(self) -> float:
        """Current token count (approximate without lock)."""
        elapsed = time.monotonic() - self._last_refill
        return min(self._capacity, self._tokens + elapsed * self._rate)

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        assert elapsed >= 0, "monotonic clock went backwards"
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        assert self._rate > 0, "rate limiter has invalid rate"
        assert self._capacity >= 1, "rate limiter has invalid capacity"
        deadline = time.monotonic() + _MAX_WAIT_SECONDS
        iterations = 0
        while iterations < _MAX_SPIN_ITERATIONS:
            iterations += 1
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
            wait = min(1.0 / self._rate, deadline - time.monotonic())
            if wait <= 0:
                raise TimeoutError(f"Rate limiter: waited {_MAX_WAIT_SECONDS}s without token")
            await asyncio.sleep(min(wait, 0.1))
        raise TimeoutError(f"Rate limiter: exceeded {_MAX_SPIN_ITERATIONS} iterations")


class TLDRateLimiter:
    """Manages separate TokenBucketRateLimiter instances per TLD."""

    __slots__ = ("_limiters", "_lock")

    def __init__(self) -> None:
        self._limiters: dict[str, TokenBucketRateLimiter] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    def _get_or_create(self, tld: str) -> TokenBucketRateLimiter:
        """Return existing limiter or create one from config."""
        assert isinstance(tld, str) and tld.startswith("."), f"invalid TLD: {tld!r}"
        if tld not in self._limiters:
            cfg = TLD_RATE_CONFIGS.get(tld, _DEFAULT_TLD_CONFIG)
            assert cfg.tokens_per_second > 0, f"bad config for {tld}"
            self._limiters[tld] = TokenBucketRateLimiter(cfg.tokens_per_second, cfg.capacity)
            logger.debug("rate_limiter.tld_created", tld=tld, rps=cfg.tokens_per_second)
        return self._limiters[tld]

    async def acquire(self, tld: str) -> None:
        """Acquire a token for the given TLD, waiting if necessary."""
        assert isinstance(tld, str) and len(tld) >= 2, f"invalid TLD: {tld!r}"
        assert tld.startswith("."), f"TLD must start with '.': {tld!r}"
        async with self._lock:
            limiter = self._get_or_create(tld)
        await limiter.acquire()


class ServiceRateLimiter:
    """Named rate limiters for different API services."""

    __slots__ = ("_limiters", "_lock")

    def __init__(self) -> None:
        self._limiters: dict[str, TokenBucketRateLimiter] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    def _get_or_create(self, service: str) -> TokenBucketRateLimiter:
        """Return existing limiter or create one from config."""
        assert isinstance(service, str) and len(service) > 0, "empty service name"
        if service not in self._limiters:
            cfg = SERVICE_RATE_CONFIGS.get(service, _DEFAULT_SERVICE_CONFIG)
            assert cfg.capacity >= 1, f"bad config for {service}"
            self._limiters[service] = TokenBucketRateLimiter(cfg.tokens_per_second, cfg.capacity)
            logger.debug("rate_limiter.service_created", service=service, rps=cfg.tokens_per_second)
        return self._limiters[service]

    async def acquire(self, service: str) -> None:
        """Acquire a token for the given service, waiting if necessary."""
        assert isinstance(service, str), f"service must be str, got {type(service)}"
        assert len(service) > 0, "service name must not be empty"
        async with self._lock:
            limiter = self._get_or_create(service)
        await limiter.acquire()
