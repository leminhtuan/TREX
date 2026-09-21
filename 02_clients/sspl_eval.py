"""
Syntactic SLA Predicate Language (SSPL) Evaluator
Implements strict Kleene 3-valued logic (K_3) with Fail-Closed semantics
to eliminate Fail-Open vulnerabilities in decentralized oracle attestations.

RFC 6901 JSON Pointer resolution
RFC 8785 Canonical JSON hashing support
"""

import json
import hashlib
from enum import IntEnum
from typing import Any, Dict, List, Union, Optional
from dataclasses import dataclass

class Verdict(IntEnum):
    FAIL = 0
    PASS = 1
    ERROR = 2  # Represents bot (undefined / missing / type mismatch)


def is_bool(val: Any) -> bool:
    """Strictly checks if val is boolean (excluding Python's int subclassing of bool)."""
    return isinstance(val, bool)


def is_number(val: Any) -> bool:
    """Strictly checks if val is a numeric int or float (excluding bool)."""
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def is_str(val: Any) -> bool:
    return isinstance(val, str)


def is_verdict_error(val: Any) -> bool:
    """Checks whether a value is the Verdict.ERROR sentinel, avoiding collision with int 2."""
    return (isinstance(val, Verdict) and val == Verdict.ERROR) or (val is Verdict.ERROR)


def unescape_token(token: str) -> str:
    """RFC 6901 pointer unescaping: ~1 -> /, ~0 -> ~"""
    return token.replace("~1", "/").replace("~0", "~")


def resolve_path(json_obj: Any, pointer: str, literal: Any = None, op: Optional[str] = None) -> Any:
    """
    Resolves an RFC 6901 JSON pointer against json_obj.
    
    Returns Verdict.ERROR if:
    - pointer syntax is invalid
    - pointer references a missing key or out-of-bounds array index
    - non-container is traversed
    - literal is specified and resolved value is type-incompatible with literal
    
    Otherwise returns the resolved value.
    """
    if not isinstance(pointer, str):
        return Verdict.ERROR

    if pointer == "":
        curr = json_obj
    else:
        if not pointer.startswith("/"):
            return Verdict.ERROR
            
        tokens = pointer.split("/")[1:]
        curr = json_obj
        for token in tokens:
            unescaped = unescape_token(token)
            if isinstance(curr, dict):
                if unescaped not in curr:
                    return Verdict.ERROR
                curr = curr[unescaped]
            elif isinstance(curr, list):
                if not unescaped.isdigit():
                    return Verdict.ERROR
                if len(unescaped) > 1 and unescaped.startswith("0"):
                    # RFC 6901 disallows leading zeros for array indices
                    return Verdict.ERROR
                idx = int(unescaped)
                if idx < 0 or idx >= len(curr):
                    return Verdict.ERROR
                curr = curr[idx]
            else:
                return Verdict.ERROR

    if literal is not None:
        if not check_type_compatibility(curr, literal, op):
            return Verdict.ERROR

    return curr


def check_type_compatibility(val: Any, lit: Any, op: Optional[str] = None) -> bool:
    """
    Validates type compatibility between resolved JSON value and the predicate literal.
    Ordering operators (<, <=, >, >=) are strictly restricted to numeric types.
    """
    if val is None or lit is None:
        # None is only compatible if both are None and equality operator is used
        return val is None and lit is None and op in ("=", "==", "!=")

    # Boolean literal
    if is_bool(lit):
        if not is_bool(val):
            return False
        # Ordering not defined on booleans
        if op in ("<", "<=", ">", ">="):
            return False
        return True

    # Numeric literal (int or float)
    if is_number(lit):
        if not is_number(val):
            return False
        return True

    # String literal
    if is_str(lit):
        if not is_str(val):
            return False
        # Ordering operators are defined only for numbers per SSPL formal specification
        if op in ("<", "<=", ">", ">="):
            return False
        return True

    return False


# --- Kleene Strong 3-Valued Logic Truth Functions ---

def kleene_not(val: Verdict) -> Verdict:
    """
    Kleene Strong Negation:
    Not(PASS)  = FAIL
    Not(FAIL)  = PASS
    Not(ERROR) = ERROR
    """
    if val == Verdict.PASS:
        return Verdict.FAIL
    elif val == Verdict.FAIL:
        return Verdict.PASS
    else:
        return Verdict.ERROR


def kleene_and(left: Verdict, right: Verdict) -> Verdict:
    """
    Kleene Strong Conjunction:
    And(PASS, PASS)   = PASS
    And(FAIL, ERROR)  = FAIL  (definitive short-circuit on FAIL)
    And(ERROR, FAIL)  = FAIL
    And(PASS, ERROR)  = ERROR
    And(ERROR, PASS)  = ERROR
    And(ERROR, ERROR) = ERROR
    """
    if left == Verdict.FAIL or right == Verdict.FAIL:
        return Verdict.FAIL
    if left == Verdict.ERROR or right == Verdict.ERROR:
        return Verdict.ERROR
    if left == Verdict.PASS and right == Verdict.PASS:
        return Verdict.PASS
    return Verdict.ERROR


def kleene_or(left: Verdict, right: Verdict) -> Verdict:
    """
    Kleene Strong Disjunction:
    Or(PASS, ERROR)  = PASS  (definitive short-circuit on PASS)
    Or(ERROR, PASS)  = PASS
    Or(FAIL, ERROR)  = ERROR
    Or(ERROR, FAIL)  = ERROR
    Or(ERROR, ERROR) = ERROR
    Or(FAIL, FAIL)   = FAIL
    """
    if left == Verdict.PASS or right == Verdict.PASS:
        return Verdict.PASS
    if left == Verdict.ERROR or right == Verdict.ERROR:
        return Verdict.ERROR
    if left == Verdict.FAIL and right == Verdict.FAIL:
        return Verdict.FAIL
    return Verdict.ERROR


# --- Predicate AST ---

class Predicate:
    def eval_kleene(self, doc: Any) -> Verdict:
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError


@dataclass
class Compare(Predicate):
    path: str
    op: str
    lit: Any

    def eval_kleene(self, doc: Any) -> Verdict:
        val = resolve_path(doc, self.path)
        if is_verdict_error(val):
            return Verdict.ERROR

        if not check_type_compatibility(val, self.lit, self.op):
            return Verdict.ERROR

        try:
            if self.op in ("=", "=="):
                return Verdict.PASS if val == self.lit else Verdict.FAIL
            elif self.op == "!=":
                return Verdict.PASS if val != self.lit else Verdict.FAIL
            elif self.op == "<":
                return Verdict.PASS if val < self.lit else Verdict.FAIL
            elif self.op == "<=":
                return Verdict.PASS if val <= self.lit else Verdict.FAIL
            elif self.op == ">":
                return Verdict.PASS if val > self.lit else Verdict.FAIL
            elif self.op == ">=":
                return Verdict.PASS if val >= self.lit else Verdict.FAIL
            else:
                return Verdict.ERROR
        except Exception:
            return Verdict.ERROR

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Compare", "path": self.path, "op": self.op, "lit": self.lit}


@dataclass
class Not(Predicate):
    child: Predicate

    def eval_kleene(self, doc: Any) -> Verdict:
        child_res = self.child.eval_kleene(doc)
        return kleene_not(child_res)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Not", "child": self.child.to_dict()}


@dataclass
class And(Predicate):
    left: Predicate
    right: Predicate

    def eval_kleene(self, doc: Any) -> Verdict:
        l_res = self.left.eval_kleene(doc)
        # Kleene short-circuit: if left is FAIL, conjunction is FAIL even if right is ERROR
        if l_res == Verdict.FAIL:
            return Verdict.FAIL
        r_res = self.right.eval_kleene(doc)
        return kleene_and(l_res, r_res)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "And", "left": self.left.to_dict(), "right": self.right.to_dict()}


@dataclass
class Or(Predicate):
    left: Predicate
    right: Predicate

    def eval_kleene(self, doc: Any) -> Verdict:
        l_res = self.left.eval_kleene(doc)
        # Kleene short-circuit: if left is PASS, disjunction is PASS even if right is ERROR
        if l_res == Verdict.PASS:
            return Verdict.PASS
        r_res = self.right.eval_kleene(doc)
        return kleene_or(l_res, r_res)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Or", "left": self.left.to_dict(), "right": self.right.to_dict()}


def parse_predicate(pred_data: Any) -> Predicate:
    """
    Parses a predicate specification into a typed AST.
    Accepts:
    - Predicate instances (Compare, Not, And, Or)
    - JSON strings
    - Dictionaries with standard or shorthand grammar
    """
    if isinstance(pred_data, Predicate):
        return pred_data

    if isinstance(pred_data, (bytes, bytearray)):
        pred_data = pred_data.decode("utf-8")

    if isinstance(pred_data, str):
        try:
            pred_data = json.loads(pred_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in predicate string: {e}")

    if not isinstance(pred_data, dict):
        raise TypeError(f"Predicate data must be a dict or Predicate, got {type(pred_data).__name__}")

    # Standard "type" tagged dicts
    pred_type = pred_data.get("type")
    if pred_type == "Compare":
        return Compare(path=pred_data["path"], op=pred_data["op"], lit=pred_data["lit"])
    elif pred_type == "Not":
        child_raw = pred_data.get("child") or pred_data.get("arg") or pred_data.get("predicate")
        return Not(child=parse_predicate(child_raw))
    elif pred_type == "And":
        if "left" in pred_data and "right" in pred_data:
            return And(left=parse_predicate(pred_data["left"]), right=parse_predicate(pred_data["right"]))
        elif "args" in pred_data and len(pred_data["args"]) == 2:
            return And(left=parse_predicate(pred_data["args"][0]), right=parse_predicate(pred_data["args"][1]))
    elif pred_type == "Or":
        if "left" in pred_data and "right" in pred_data:
            return Or(left=parse_predicate(pred_data["left"]), right=parse_predicate(pred_data["right"]))
        elif "args" in pred_data and len(pred_data["args"]) == 2:
            return Or(left=parse_predicate(pred_data["args"][0]), right=parse_predicate(pred_data["args"][1]))

    # Shorthand operator dictionaries
    if "Compare" in pred_data:
        c = pred_data["Compare"]
        if isinstance(c, dict):
            return Compare(path=c["path"], op=c["op"], lit=c["lit"])
        elif isinstance(c, (list, tuple)) and len(c) == 3:
            return Compare(path=c[0], op=c[1], lit=c[2])

    if "Not" in pred_data:
        return Not(child=parse_predicate(pred_data["Not"]))

    if "And" in pred_data:
        args = pred_data["And"]
        if isinstance(args, (list, tuple)) and len(args) == 2:
            return And(left=parse_predicate(args[0]), right=parse_predicate(args[1]))

    if "Or" in pred_data:
        args = pred_data["Or"]
        if isinstance(args, (list, tuple)) and len(args) == 2:
            return Or(left=parse_predicate(args[0]), right=parse_predicate(args[1]))

    # Direct compare dictionary
    if "path" in pred_data and "op" in pred_data and "lit" in pred_data:
        return Compare(path=pred_data["path"], op=pred_data["op"], lit=pred_data["lit"])

    raise ValueError(f"Unable to parse predicate specification: {pred_data}")


def eval_kleene(predicate_data: Any, response_data: Any) -> Verdict:
    """
    Evaluates an SSPL predicate against a response document
    under Kleene Strong 3-Valued Logic (K_3).
    
    Returns:
        Verdict.PASS (1)
        Verdict.FAIL (0)
        Verdict.ERROR (2)
    """
    if isinstance(response_data, (bytes, bytearray)):
        response_data = response_data.decode("utf-8")
    if isinstance(response_data, str):
        try:
            response_data = json.loads(response_data)
        except json.JSONDecodeError as e:
            # Response is not valid JSON -> bot / ERROR
            return Verdict.ERROR

    pred = parse_predicate(predicate_data)
    return pred.eval_kleene(response_data)


def evaluate(predicate_data: Any, response_data: Any) -> Verdict:
    """
    Top-level evaluation function for smart-contract attestation.
    Enforces Fail-Closed semantics:
    If Kleene evaluation yields Verdict.ERROR (bot / undefined / missing field / type mismatch),
    it is strictly mapped to Verdict.FAIL (0) to protect against Fail-Open bypasses.
    
    Returns Verdict.PASS (1) or Verdict.FAIL (0).
    """
    k_verdict = eval_kleene(predicate_data, response_data)
    if k_verdict == Verdict.ERROR:
        return Verdict.FAIL
    return k_verdict


# --- RFC 8785 Canonical JSON Serialization & Hashing Support ---

def canonical_jcs(obj: Any) -> bytes:
    """Produces RFC 8785 compliant canonical JSON serialization."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def canonical_hash(obj: Any) -> bytes:
    """Produces SHA-256 digest over canonical JSON serialization."""
    return hashlib.sha256(canonical_jcs(obj)).digest()
