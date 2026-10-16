"""
Stall-Triggered Complexity Ratio Controller for MOSES.

Manages dynamic relaxation of complexityRatio when search hits raw fitness plateaus,
with minimum hold windows, grace periods on improvement, cooldowns, and rescoring triggers.
"""

import random

class StallController:
    def __init__(self, r_base=14.0, r_relax=100.0, k_stall=3, m_min=3, grace=2, cooldown=3, mode="dynamic"):
        self.r_base = float(r_base)
        self.r_relax = float(r_relax)
        self.k_stall = int(k_stall)
        self.m_min = int(m_min)
        self.grace = int(grace)
        self.cooldown = int(cooldown)
        self.mode = mode  # 'dynamic', 'static', 'trigger_only', 'random'
        
        self.reset()
        
    def reset(self):
        self.current_ratio = self.r_base
        self.best_raw_ever = -1e9
        self.stall_count = 0
        self.state = "BASE"  # "BASE", "RELAXED", "COOLDOWN"
        self.relaxed_gens_remaining = 0
        self.cooldown_gens_remaining = 0
        self.total_gens = 0
        self.total_relaxed_gens = 0
        self.switch_events = []
        self.history = []
        
    def configure(self, r_base=14.0, r_relax=100.0, k_stall=3, m_min=3, grace=2, cooldown=3, mode="dynamic"):
        self.r_base = float(r_base)
        self.r_relax = float(r_relax)
        self.k_stall = int(k_stall)
        self.m_min = int(m_min)
        self.grace = int(grace)
        self.cooldown = int(cooldown)
        self.mode = mode
        self.reset()

    def step(self, gen_remaining, best_raw_metapop, best_raw_ever_input=None):
        """
        Invoked at the end of each generation.
        Returns: (next_ratio, switched: int [0 or 1], state: str)
        """
        self.total_gens += 1
        
        # Best-ever raw tracking (monotonically non-decreasing)
        raw_val = best_raw_ever_input if best_raw_ever_input is not None else best_raw_metapop
        improved = (raw_val > self.best_raw_ever)
        if improved:
            self.best_raw_ever = raw_val
            
        switched = 0
        prev_ratio = self.current_ratio
        
        if self.mode == "static":
            self.current_ratio = self.r_base
            return (self.current_ratio, 0, "STATIC")
            
        target_relax = self.r_base if self.mode == "trigger_only" else self.r_relax
        
        if self.state == "BASE":
            if improved:
                self.stall_count = 0
            else:
                self.stall_count += 1
                
            if self.stall_count >= self.k_stall:
                # Trigger relaxation window!
                self.state = "RELAXED"
                self.relaxed_gens_remaining = self.m_min
                self.current_ratio = target_relax
                switched = 1
                self.switch_events.append((self.total_gens, "BASE->RELAXED", self.current_ratio, self.best_raw_ever))
                
        elif self.state == "RELAXED":
            self.total_relaxed_gens += 1
            if improved:
                # Raw breakthrough! Grant grace period G
                self.relaxed_gens_remaining = max(self.relaxed_gens_remaining, self.grace)
                self.stall_count = 0
                self.switch_events.append((self.total_gens, "RAW_BREAKTHROUGH", self.current_ratio, self.best_raw_ever))
            else:
                self.relaxed_gens_remaining -= 1
                if self.relaxed_gens_remaining <= 0:
                    # Restore back to r_base
                    self.state = "COOLDOWN"
                    self.cooldown_gens_remaining = self.cooldown
                    self.stall_count = 0
                    self.current_ratio = self.r_base
                    switched = 1
                    self.switch_events.append((self.total_gens, "RELAXED->COOLDOWN", self.current_ratio, self.best_raw_ever))
                    
        elif self.state == "COOLDOWN":
            self.cooldown_gens_remaining -= 1
            if improved:
                self.stall_count = 0
            else:
                self.stall_count += 1
                
            if self.cooldown_gens_remaining <= 0:
                self.state = "BASE"
                # If stall count is already high, it must wait for at least 1 more stall generation in BASE
                self.stall_count = 0
                
        record = {
            "gen": self.total_gens,
            "best_raw_ever": self.best_raw_ever,
            "state": self.state,
            "ratio": self.current_ratio,
            "switched": switched,
            "stall_count": self.stall_count,
            "relaxed_remaining": self.relaxed_gens_remaining,
            "cooldown_remaining": self.cooldown_gens_remaining
        }
        self.history.append(record)
        return (self.current_ratio, switched, self.state)

    def get_summary(self):
        fraction_relaxed = self.total_relaxed_gens / max(1, self.total_gens)
        return {
            "total_gens": self.total_gens,
            "total_relaxed_gens": self.total_relaxed_gens,
            "fraction_relaxed": fraction_relaxed,
            "switch_count": len(self.switch_events),
            "switches": self.switch_events,
            "best_raw_ever": self.best_raw_ever
        }

# Global singleton for MeTTa py-call interop
_controller = StallController()

def configure_controller(r_base, r_relax, k_stall, m_min, grace, cooldown, mode="dynamic"):
    _controller.configure(r_base, r_relax, k_stall, m_min, grace, cooldown, mode)
    return 1

def reset_controller():
    _controller.reset()
    return 1

def step_controller(gen_remaining, best_raw_metapop, best_raw_ever=None):
    if best_raw_ever is None:
        try:
            import logger_helper
            best_raw_ever = logger_helper.get_best_raw_ever()
        except Exception:
            best_raw_ever = best_raw_metapop
    ratio, switched, state = _controller.step(gen_remaining, best_raw_metapop, best_raw_ever)
    return int(switched)

def get_current_ratio():
    return float(_controller.current_ratio)

def get_current_state():
    return str(_controller.state)

def get_fraction_relaxed():
    return float(_controller.total_relaxed_gens / max(1, _controller.total_gens))

def get_summary_str():
    s = _controller.get_summary()
    return f"TotalGens: {s['total_gens']} RelaxedGens: {s['total_relaxed_gens']} FractionRelaxed: {s['fraction_relaxed']:.2f} Switches: {s['switch_count']}"
