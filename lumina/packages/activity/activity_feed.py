"""
LUMINA Activity Feed
═════════════════════
Every financial event gets a timestamped
client-facing feed entry.

This is what makes the system feel alive.

Before:
  Events fire silently in logs.
  User has no idea what the system did.

After:
  09:12  🔴  Market crash detected (-22%)
  09:12  📊  Portfolio risk increased
  09:13  🤖  3 agents ran in 0.4ms
  09:13  ✅  Rebalance decision created (P1)
  09:14  👤  Advisor Priya notified
  09:14  🔒  Decision logged to Merkle chain

Feed types:
  MARKET_EVENT     — external financial event
  AGENT_RUN        — agents analysed the event
  DECISION_CREATED — system created a decision
  DECISION_APPROVED— advisor approved
  DECISION_REJECTED— advisor rejected
  ACTION_EXECUTED  — action was executed
  SCORE_CHANGE     — health score moved
  ALERT            — something needs attention
  SYSTEM           — system-level message
  ADVISOR_NOTE     — RM added a note

Each entry:
  timestamp, type, emoji, title, detail,
  amount_inr, linked_decision_id, merkle_hash
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from lumina.observability.logging import get_logger

logger = get_logger("lumina.activity_feed")


class FeedEntryType(str, Enum):
    MARKET_EVENT      = "market_event"
    AGENT_RUN         = "agent_run"
    DECISION_CREATED  = "decision_created"
    DECISION_APPROVED = "decision_approved"
    DECISION_REJECTED = "decision_rejected"
    ACTION_EXECUTED   = "action_executed"
    SCORE_CHANGE      = "score_change"
    ALERT             = "alert"
    SYSTEM            = "system"
    ADVISOR_NOTE      = "advisor_note"
    TWIN_UPDATE       = "twin_update"


ENTRY_EMOJI = {
    FeedEntryType.MARKET_EVENT:      "📉",
    FeedEntryType.AGENT_RUN:         "🤖",
    FeedEntryType.DECISION_CREATED:  "💡",
    FeedEntryType.DECISION_APPROVED: "✅",
    FeedEntryType.DECISION_REJECTED: "❌",
    FeedEntryType.ACTION_EXECUTED:   "⚡",
    FeedEntryType.SCORE_CHANGE:      "📊",
    FeedEntryType.ALERT:             "🔴",
    FeedEntryType.SYSTEM:            "🔒",
    FeedEntryType.ADVISOR_NOTE:      "👤",
    FeedEntryType.TWIN_UPDATE:       "🔄",
}


class FeedPriority(str, Enum):
    CRITICAL     = "critical"
    HIGH         = "high"
    MEDIUM       = "medium"
    LOW          = "low"
    INFORMATIONAL= "informational"


@dataclass
class FeedEntry:
    entry_id:           str
    user_id:            str
    entry_type:         FeedEntryType
    priority:           FeedPriority
    title:              str
    detail:             str
    emoji:              str              = ""
    amount_inr:         Optional[float]  = None
    linked_decision_id: Optional[str]    = None
    linked_event_type:  Optional[str]    = None
    merkle_hash:        Optional[str]    = None
    agent_names:        list[str]        = field(default_factory=list)
    metadata:           dict[str, Any]   = field(default_factory=dict)
    timestamp:          float            = field(default_factory=time.time)
    read:               bool             = False

    def __post_init__(self):
        if not self.emoji:
            self.emoji = ENTRY_EMOJI.get(self.entry_type, "•")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id":           self.entry_id,
            "user_id":            self.user_id,
            "type":               self.entry_type.value,
            "priority":           self.priority.value,
            "emoji":              self.emoji,
            "title":              self.title,
            "detail":             self.detail,
            "amount_inr":         self.amount_inr,
            "linked_decision_id": self.linked_decision_id,
            "linked_event_type":  self.linked_event_type,
            "merkle_hash":        self.merkle_hash,
            "agent_names":        self.agent_names,
            "timestamp":          self.timestamp,
            "read":               self.read,
        }

    def time_str(self) -> str:
        import datetime
        return datetime.datetime.fromtimestamp(
            self.timestamp
        ).strftime("%H:%M:%S")

    def render_line(self) -> str:
        amt = (
            f"  ₹{self.amount_inr/1e5:.1f}L"
            if self.amount_inr else ""
        )
        return (
            f"  {self.time_str()}  "
            f"{self.emoji}  "
            f"{self.title:<38}"
            f"{amt}"
        )


class ActivityFeed:
    """
    Per-user activity feed.

    Receives events from:
      EventReactor    → MARKET_EVENT, AGENT_RUN
      DecisionRegistry→ DECISION_CREATED
      AdvisorPanel    → DECISION_APPROVED/REJECTED
      ActionEngine    → ACTION_EXECUTED
      ScoreEngine     → SCORE_CHANGE
      System          → SYSTEM, ALERT

    Consumers:
      Client mobile app  → GET /users/{id}/feed
      Advisor dashboard  → GET /advisor/{id}/feed
      API               → paginated feed endpoint
    """

    def __init__(self):
        # user_id → list of FeedEntry (newest first)
        self._feeds: dict[str, list[FeedEntry]] = {}
        self._id_counter = 0

    # ── Write methods ─────────────────────────────────────────────

    def add(self, entry: FeedEntry) -> FeedEntry:
        feed = self._feeds.setdefault(entry.user_id, [])
        feed.insert(0, entry)          # newest first
        # Cap at 500 entries per user
        if len(feed) > 500:
            self._feeds[entry.user_id] = feed[:500]

        logger.info(
            "feed.entry",
            user_id    = entry.user_id,
            entry_type = entry.entry_type.value,
            priority   = entry.priority.value,
            title      = entry.title[:40],
        )
        return entry

    def market_event(
        self,
        user_id:    str,
        event_type: str,
        title:      str,
        detail:     str,
        severity:   str = "advisory",
        amount_inr: Optional[float] = None,
    ) -> FeedEntry:
        priority = {
            "critical": FeedPriority.CRITICAL,
            "alert":    FeedPriority.HIGH,
            "advisory": FeedPriority.MEDIUM,
            "info":     FeedPriority.LOW,
        }.get(severity.lower(), FeedPriority.MEDIUM)

        return self.add(FeedEntry(
            entry_id         = self._next_id("mkt"),
            user_id          = user_id,
            entry_type       = FeedEntryType.MARKET_EVENT,
            priority         = priority,
            title            = title,
            detail           = detail,
            amount_inr       = amount_inr,
            linked_event_type= event_type,
        ))

    def agent_run(
        self,
        user_id:     str,
        event_type:  str,
        agent_names: list[str],
        verdict:     str,
        latency_ms:  float,
        policy_result: str = "allowed",
    ) -> FeedEntry:
        return self.add(FeedEntry(
            entry_id         = self._next_id("agt"),
            user_id          = user_id,
            entry_type       = FeedEntryType.AGENT_RUN,
            priority         = FeedPriority.INFORMATIONAL,
            title            = f"{len(agent_names)} agents analysed",
            detail           = (
                f"Event: {event_type} | "
                f"Verdict: {verdict} | "
                f"Policy: {policy_result} | "
                f"{latency_ms:.1f}ms"
            ),
            agent_names      = agent_names,
            linked_event_type= event_type,
        ))

    def decision_created(
        self,
        user_id:     str,
        decision_id: str,
        dtype:       str,
        priority:    str,
        action:      str,
        amount_inr:  Optional[float],
        reasoning:   str,
        agent:       str,
    ) -> FeedEntry:
        feed_priority = {
            "P0_IMMEDIATE": FeedPriority.CRITICAL,
            "P1_THIS_WEEK": FeedPriority.HIGH,
            "P2_THIS_MONTH":FeedPriority.MEDIUM,
            "P3_INFORMATIONAL": FeedPriority.LOW,
        }.get(priority, FeedPriority.MEDIUM)

        return self.add(FeedEntry(
            entry_id           = self._next_id("dec"),
            user_id            = user_id,
            entry_type         = FeedEntryType.DECISION_CREATED,
            priority           = feed_priority,
            title              = f"Decision: {action.replace('_',' ').title()}",
            detail             = reasoning[:80],
            amount_inr         = amount_inr,
            linked_decision_id = decision_id,
            metadata           = {
                "decision_type": dtype,
                "priority":      priority,
                "agent":         agent,
            },
        ))

    def decision_approved(
        self,
        user_id:     str,
        decision_id: str,
        action:      str,
        advisor_name:str,
        amount_inr:  Optional[float],
        reason:      str,
        merkle_hash: str = "",
    ) -> FeedEntry:
        return self.add(FeedEntry(
            entry_id           = self._next_id("apv"),
            user_id            = user_id,
            entry_type         = FeedEntryType.DECISION_APPROVED,
            priority           = FeedPriority.HIGH,
            title              = f"Approved: {action.replace('_',' ').title()}",
            detail             = f"By {advisor_name} — {reason[:60]}",
            amount_inr         = amount_inr,
            linked_decision_id = decision_id,
            merkle_hash        = merkle_hash,
        ))

    def decision_rejected(
        self,
        user_id:     str,
        decision_id: str,
        action:      str,
        advisor_name:str,
        reason:      str,
        merkle_hash: str = "",
    ) -> FeedEntry:
        return self.add(FeedEntry(
            entry_id           = self._next_id("rej"),
            user_id            = user_id,
            entry_type         = FeedEntryType.DECISION_REJECTED,
            priority           = FeedPriority.MEDIUM,
            title              = f"Rejected: {action.replace('_',' ').title()}",
            detail             = f"By {advisor_name} — {reason[:60]}",
            linked_decision_id = decision_id,
            merkle_hash        = merkle_hash,
        ))

    def action_executed(
        self,
        user_id:     str,
        decision_id: str,
        action:      str,
        result:      str,
        detail:      str,
        amount_inr:  Optional[float] = None,
        external_ref:Optional[str]   = None,
        merkle_hash: str             = "",
    ) -> FeedEntry:
        priority = (
            FeedPriority.HIGH
            if result == "success"
            else FeedPriority.CRITICAL
        )
        return self.add(FeedEntry(
            entry_id           = self._next_id("exe"),
            user_id            = user_id,
            entry_type         = FeedEntryType.ACTION_EXECUTED,
            priority           = priority,
            title              = f"Executed: {action.replace('_',' ').title()}",
            detail             = f"{detail[:60]}"
                                 + (f" | ref:{external_ref[:12]}"
                                    if external_ref else ""),
            amount_inr         = amount_inr,
            linked_decision_id = decision_id,
            merkle_hash        = merkle_hash,
            metadata           = {"result": result},
        ))

    def score_change(
        self,
        user_id:     str,
        old_score:   float,
        new_score:   float,
        band:        str,
        top_insight: str,
    ) -> FeedEntry:
        delta    = new_score - old_score
        arrow    = "↑" if delta >= 0 else "↓"
        priority = (
            FeedPriority.HIGH
            if abs(delta) > 0.05
            else FeedPriority.LOW
        )
        return self.add(FeedEntry(
            entry_id   = self._next_id("scr"),
            user_id    = user_id,
            entry_type = FeedEntryType.SCORE_CHANGE,
            priority   = priority,
            title      = (
                f"Health score {arrow} "
                f"{new_score:.0%} ({band})"
            ),
            detail     = top_insight[:80],
            metadata   = {
                "old_score": old_score,
                "new_score": new_score,
                "delta":     delta,
                "band":      band,
            },
        ))

    def alert(
        self,
        user_id:  str,
        title:    str,
        detail:   str,
        priority: FeedPriority = FeedPriority.HIGH,
        amount_inr: Optional[float] = None,
    ) -> FeedEntry:
        return self.add(FeedEntry(
            entry_id   = self._next_id("alt"),
            user_id    = user_id,
            entry_type = FeedEntryType.ALERT,
            priority   = priority,
            title      = title,
            detail     = detail,
            amount_inr = amount_inr,
        ))

    def system(
        self,
        user_id: str,
        title:   str,
        detail:  str,
        merkle_hash: str = "",
    ) -> FeedEntry:
        return self.add(FeedEntry(
            entry_id    = self._next_id("sys"),
            user_id     = user_id,
            entry_type  = FeedEntryType.SYSTEM,
            priority    = FeedPriority.INFORMATIONAL,
            title       = title,
            detail      = detail,
            merkle_hash = merkle_hash,
        ))

    def advisor_note(
        self,
        user_id:      str,
        advisor_name: str,
        note:         str,
        decision_id:  Optional[str] = None,
    ) -> FeedEntry:
        return self.add(FeedEntry(
            entry_id           = self._next_id("adv"),
            user_id            = user_id,
            entry_type         = FeedEntryType.ADVISOR_NOTE,
            priority           = FeedPriority.MEDIUM,
            title              = f"Note from {advisor_name}",
            detail             = note[:80],
            linked_decision_id = decision_id,
        ))

    def twin_update(
        self,
        user_id:      str,
        field_updated:str,
        detail:       str,
        snapshot_hash:str = "",
    ) -> FeedEntry:
        return self.add(FeedEntry(
            entry_id   = self._next_id("twn"),
            user_id    = user_id,
            entry_type = FeedEntryType.TWIN_UPDATE,
            priority   = FeedPriority.LOW,
            title      = f"Profile updated: {field_updated}",
            detail     = detail[:80],
            merkle_hash= snapshot_hash,
        ))

    # ── Read methods ──────────────────────────────────────────────

    def get_feed(
        self,
        user_id:     str,
        limit:       int                      = 20,
        entry_type:  Optional[FeedEntryType]  = None,
        priority:    Optional[FeedPriority]   = None,
        unread_only: bool                     = False,
        since_ts:    Optional[float]          = None,
    ) -> list[FeedEntry]:
        entries = self._feeds.get(user_id, [])
        if entry_type:
            entries = [e for e in entries
                       if e.entry_type == entry_type]
        if priority:
            entries = [e for e in entries
                       if e.priority == priority]
        if unread_only:
            entries = [e for e in entries if not e.read]
        if since_ts:
            entries = [e for e in entries
                       if e.timestamp >= since_ts]
        return entries[:limit]

    def get_alerts(self, user_id: str) -> list[FeedEntry]:
        return self.get_feed(
            user_id,
            limit      = 50,
            entry_type = FeedEntryType.ALERT,
            priority   = FeedPriority.CRITICAL,
        ) + self.get_feed(
            user_id,
            limit      = 50,
            entry_type = FeedEntryType.ALERT,
            priority   = FeedPriority.HIGH,
        )

    def mark_read(self, user_id: str, entry_id: str) -> bool:
        for e in self._feeds.get(user_id, []):
            if e.entry_id == entry_id:
                e.read = True
                return True
        return False

    def mark_all_read(self, user_id: str) -> int:
        count = 0
        for e in self._feeds.get(user_id, []):
            if not e.read:
                e.read = True
                count += 1
        return count

    def unread_count(self, user_id: str) -> int:
        return sum(
            1 for e in self._feeds.get(user_id, [])
            if not e.read
        )

    def summary(self, user_id: str) -> dict[str, Any]:
        entries = self._feeds.get(user_id, [])
        by_type: dict[str, int] = {}
        for e in entries:
            by_type[e.entry_type.value] = (
                by_type.get(e.entry_type.value, 0) + 1
            )
        return {
            "user_id":      user_id,
            "total":        len(entries),
            "unread":       self.unread_count(user_id),
            "by_type":      by_type,
            "latest_title": entries[0].title if entries else None,
        }

    def render(
        self,
        user_id: str,
        limit:   int = 15,
    ) -> str:
        entries = self.get_feed(user_id, limit=limit)
        if not entries:
            return f"  No activity for {user_id}"

        lines = [
            "┌" + "─" * 58 + "┐",
            f"│  📱 ACTIVITY FEED — {user_id:<36}│",
            f"│  {self.unread_count(user_id)} unread"
            f"{'':49}│",
            "├" + "─" * 58 + "┤",
        ]
        for e in entries:
            lines.append(e.render_line())
            lines.append(f"     {e.detail[:54]}")
            lines.append("")
        lines.append("└" + "─" * 58 + "┘")
        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────────

    def _next_id(self, prefix: str) -> str:
        self._id_counter += 1
        return f"{prefix}_{self._id_counter:06d}"
