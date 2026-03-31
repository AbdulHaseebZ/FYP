# custom_components/my_inverter/rule_matcher.py
"""Rule matching engine for filtering and ranking applicable policies."""

import logging
from typing import Optional

_LOGGER = logging.getLogger(__name__)


class RuleMatcher:
    """
    Three-stage filtering pipeline:
    Stage A: Hard Constraints (Setting & Hardware)
    Stage B: Tag Subset Matching (Relevance)
    Stage C: Scoring and Tie-Breaking
    """

    def __init__(self, rules_db: list[dict]):
        """
        Initialize with a list of rule dictionaries.
        
        Args:
            rules_db: List of rule dicts with keys:
                      - search_string: space-separated tags
                      - content: the rule text
                      - metadata: dict with setting, required_devices, priority_level
        """
        self.rules = rules_db
        # Map specific device types from profile to broad rule categories
        self.device_map = {
            "HVAC": "climate",
            "IR_AC": "climate",
            "Inverter": "inverter",
            "Occupancy Sensor": "occupancy",
            "Occupancy_Sensor": "occupancy",  # Handle both formats
            "EV Charger": "ev_charger",
            "EV_Charger": "ev_charger",  # Handle both formats
            "Washing Machine": "washing_machine",
            "Washing_Machine": "washing_machine",  # Handle both formats
            "Switch": "switch",
            "Shiftable Load": "switch"
        }

    def get_matching_rules(
        self,
        active_tags: list[str],
        user_profile: dict,
        top_k: int = 5
    ) -> list[str]:
        """
        Find the top_k most relevant rules based on three-stage filtering.
        
        Args:
            active_tags: List of active tag strings from TagEngine
            user_profile: User's profile dict with setting, devices, etc.
            top_k: Number of top rules to return (default: 3)
            
        Returns:
            List of rule content strings (the actual rule text), sorted by relevance
        """
        if not user_profile or not self.rules:
            return []

        user_setting = user_profile.get("setting", "residential").lower()
        
        # Stage 1: Map user's actual hardware to required categories
        user_hardware = set()
        for device in user_profile.get("devices", []):
            device_type = device.get("type", "")
            mapped_type = self.device_map.get(device_type, device_type.lower())
            user_hardware.add(mapped_type)
        
        active_tags_set = set(active_tags)
        candidates = []

        # Iterate through all rules
        for rule in self.rules:
            metadata = rule.get("metadata", {})
            
            # ===== STAGE A: HARD FILTERS =====
            
            # Filter 1: Setting (commercial, residential, or both)
            rule_setting = metadata.get("setting", "both").lower()
            if rule_setting != "both" and rule_setting != user_setting:
                _LOGGER.debug(
                    f"Rule '{rule.get('id', 'Unknown')}' filtered by setting. "
                    f"Rule: {rule_setting}, User: {user_setting}"
                )
                continue
            
            # Filter 2: Hardware Availability
            required_devices = set(metadata.get("required_devices", []))
            if required_devices and not required_devices.issubset(user_hardware):
                missing = required_devices - user_hardware
                _LOGGER.debug(
                    f"Rule '{rule.get('id', 'Unknown')}' filtered by hardware. "
                    f"Missing devices: {missing}"
                )
                continue

            # ===== STAGE B: TAG SUBSET MATCHING =====
            # A rule matches if ALL its search_string tags are in active_tags
            rule_tags = set(rule.get("search_string", "").split())
            
            # Empty search_string = always matches (fallback rules)
            if rule_tags and not rule_tags.issubset(active_tags_set):
                _LOGGER.debug(
                    f"Rule '{rule.get('id', 'Unknown')}' filtered by tags. "
                    f"Required: {rule_tags}, Active: {active_tags_set}"
                )
                continue

            # ===== STAGE C: SCORING & RANKING =====
            # Score criteria:
            # 1. Priority Level (1-5, lower is more urgent)
            # 2. Specificity (number of tags, higher is more specific to current situation)
            priority = metadata.get("priority_level", 99)
            specificity = len(rule_tags) if rule_tags else 0
            
            candidates.append({
                "rule": rule,
                "priority": priority,
                "specificity": specificity,
                "id": rule.get("id", "Unknown")
            })

        # Sort by Priority (ascending, 1 is most urgent), then Specificity (descending, more specific first)
        candidates.sort(key=lambda x: (x["priority"], -x["specificity"]))
        
        matched_rules = [c["rule"]["content"] for c in candidates[:top_k]]
        
        _LOGGER.debug(
            f"RuleMatcher: Found {len(candidates)} matching rules, returning top {len(matched_rules)}"
        )
        
        return matched_rules

    def debug_rule_matching(
        self,
        active_tags: list[str],
        user_profile: dict
    ) -> dict:
        """
        Debug helper: return detailed info about rule matching process.
        Useful for understanding why certain rules matched or didn't.
        """
        if not user_profile or not self.rules:
            return {"status": "No profile or rules available"}

        user_setting = user_profile.get("setting", "residential").lower()
        user_hardware = set()
        for device in user_profile.get("devices", []):
            device_type = device.get("type", "")
            mapped_type = self.device_map.get(device_type, device_type.lower())
            user_hardware.add(mapped_type)
        
        active_tags_set = set(active_tags)
        
        results = {
            "user_setting": user_setting,
            "user_hardware": list(user_hardware),
            "active_tags": active_tags,
            "rules_checked": 0,
            "rules_matched": [],
            "rules_filtered": []
        }

        for rule in self.rules:
            metadata = rule.get("metadata", {})
            rule_id = rule.get("id", "Unknown")
            
            # Check each filter
            rule_setting = metadata.get("setting", "both").lower()
            if rule_setting != "both" and rule_setting != user_setting:
                results["rules_filtered"].append({
                    "id": rule_id,
                    "reason": f"Setting mismatch (rule: {rule_setting}, user: {user_setting})"
                })
                continue
            
            required_devices = set(metadata.get("required_devices", []))
            if required_devices and not required_devices.issubset(user_hardware):
                results["rules_filtered"].append({
                    "id": rule_id,
                    "reason": f"Missing devices: {required_devices - user_hardware}"
                })
                continue
            
            rule_tags = set(rule.get("search_string", "").split())
            if rule_tags and not rule_tags.issubset(active_tags_set):
                results["rules_filtered"].append({
                    "id": rule_id,
                    "reason": f"Tag mismatch (required: {rule_tags}, active: {active_tags_set})"
                })
                continue
            
            # Passed all filters
            results["rules_matched"].append({
                "id": rule_id,
                "priority": metadata.get("priority_level", 99),
                "specificity": len(rule_tags)
            })
            results["rules_checked"] += 1

        return results