"""
pid_pwm.py — PID + PWM (Pulse Width Modulation) Controller for VRC FISH!

Provides continuous closed-loop control over the fishing bar position using:
1. PID Controller:
   - Proportional (P): Direct response to error (distance between fish and bar).
   - Integral (I): Accumulates steady-state error with anti-windup clamping.
   - Derivative (D): Damps oscillations and prevents overshooting.
   - Base Duty (Feedforward): Equilibrium duty cycle required to hover against gravity.
2. Software PWM:
   - Modulates binary mouse down/up inputs over a short cycle period (e.g. 0.10 - 0.12s).
   - Only triggers OS input events upon state change to minimize system overhead.
3. Telemetry:
   - Captures instant/smoothed FPS, error, P/I/D breakdown, and duty cycle for calibration logging.
"""

import time
import controller
import config as c


class PIDPWMController:
    """PID + PWM Controller for fishing minigame bar positioning."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset internal controller states for a new fishing round."""
        self.initialized = False
        self.filtered_error = 0.0
        self.last_error = 0.0
        self.integral_accum = 0.0
        self.filtered_derivative = 0.0

        self.last_time = time.perf_counter()
        self.pwm_cycle_start = time.perf_counter()
        self.current_mouse_down = False

        # FPS calculation state
        self.last_fps_time = time.perf_counter()
        self.frame_count = 0
        self.current_fps = 0.0

        # Release mouse on reset
        self._set_mouse_down(False)

    def _set_mouse_down(self, is_down: bool):
        """Set physical mouse state only if it changed to minimize OS SendInput overhead."""
        if is_down != self.current_mouse_down:
            self.current_mouse_down = is_down
            if is_down:
                controller.mouse_down()
            else:
                controller.mouse_up()

    def update(self, error_pct: float, progress: float = 0.0) -> dict:
        """
        Update controller with current error and actuate mouse via PWM.

        Args:
            error_pct: Relative distance of fish from bar along track axis (%).
                       Positive (+) -> Fish is ABOVE bar (need to pull bar UP).
                       Negative (-) -> Fish is BELOW bar (need bar to fall DOWN).
            progress: Current fishing progress (0.0 to 1.0).

        Returns:
            telemetry: dict containing all diagnostic values for calibration and logging.
        """
        now = time.perf_counter()
        dt = max(now - self.last_time, 1e-4)
        self.last_time = now

        # Update FPS calculation
        self.frame_count += 1
        elapsed_fps = now - self.last_fps_time
        if elapsed_fps >= 0.25:
            self.current_fps = self.frame_count / elapsed_fps
            self.frame_count = 0
            self.last_fps_time = now

        # --- 1. Error Filtering & Derivative Kick Protection ---
        alpha = max(0.01, min(1.0, getattr(c, 'EMA_ALPHA', 0.45)))
        kp = getattr(c, 'KP', 1.0)
        ki = getattr(c, 'KI', 0.05)
        kd = getattr(c, 'KD', 0.70)
        base_duty = getattr(c, 'BASE_DUTY', 25.0)
        i_max = getattr(c, 'I_MAX', 30.0)
        min_duty = getattr(c, 'MIN_DUTY', 0.0)
        max_duty = getattr(c, 'MAX_DUTY', 100.0)
        pwm_period = max(0.02, getattr(c, 'PWM_PERIOD', 0.12))

        if not self.initialized:
            self.filtered_error = error_pct
            self.last_error = error_pct
            self.filtered_derivative = 0.0
            self.initialized = True
            d_term = 0.0
        else:
            self.filtered_error = alpha * error_pct + (1.0 - alpha) * self.filtered_error
            # D term (filtered derivative) with clamping
            raw_derivative = (self.filtered_error - self.last_error) / dt
            self.filtered_derivative = 0.4 * raw_derivative + 0.6 * self.filtered_derivative
            d_term = kd * self.filtered_derivative
            d_term = max(-40.0, min(40.0, d_term))
            self.last_error = self.filtered_error

        # --- 2. P & I Terms ---
        # Progressive Boost เมื่อปลาอยู่สูงกว่าเบ็ดเยอะ (เร่งดึงขึ้นทันใจ ไม่หน่วง)
        if self.filtered_error > 6.0:
            boost_factor = 1.0 + 0.035 * (self.filtered_error - 6.0)
            p_term = kp * self.filtered_error * boost_factor
        else:
            p_term = kp * self.filtered_error

        # I term with Anti-Windup & Fast Bleed-off
        # เมื่อเบ็ดอยู่สูงกว่าปลา (error < -2.0) ให้สลาย I term บวกทิ้งทันที กันเบ็ดค้างข้างบน
        if self.filtered_error < -2.0 and self.integral_accum > 0:
            self.integral_accum *= 0.65
        elif self.filtered_error > 2.0 and self.integral_accum < 0:
            self.integral_accum *= 0.65
        else:
            self.integral_accum += self.filtered_error * dt

        max_accum = (i_max / ki) if ki > 1e-6 else 0.0
        if max_accum > 0:
            self.integral_accum = max(-max_accum, min(max_accum, self.integral_accum))
        i_term = ki * self.integral_accum
        i_term = max(-i_max, min(i_max, i_term))

        # --- 3. Compute Duty Cycle ---
        # ถ้าเบ็ดอยู่สูงกว่าปลา (error < -4.0%) ให้ลด base_duty ลงชั่วคราวเพื่อให้เบ็ดทิ้งดิ่งลงเร็วตามแรงโน้มถ่วง
        effective_base = base_duty
        if self.filtered_error < -4.0:
            effective_base = max(0.0, base_duty + self.filtered_error * 2.5)

        raw_duty = effective_base + p_term + i_term + d_term
        duty_cycle = max(min_duty, min(max_duty, raw_duty))
        duty_fraction = duty_cycle / 100.0

        # --- 4. PWM Actuation ---
        # Calculate offset in current PWM period
        cycle_elapsed = (now - self.pwm_cycle_start) % pwm_period
        on_duration = duty_fraction * pwm_period

        if duty_fraction >= 0.999:
            desired_mouse_down = True
            is_pwm_on = True
        elif duty_fraction <= 0.001:
            desired_mouse_down = False
            is_pwm_on = False
        else:
            is_pwm_on = (cycle_elapsed < on_duration)
            desired_mouse_down = is_pwm_on

        self._set_mouse_down(desired_mouse_down)

        telemetry = {
            'fps': self.current_fps,
            'dt_ms': dt * 1000.0,
            'raw_error': error_pct,
            'filtered_error': self.filtered_error,
            'p_term': p_term,
            'i_term': i_term,
            'd_term': d_term,
            'base_duty': base_duty,
            'duty_cycle': duty_cycle,
            'pwm_on': is_pwm_on,
            'mouse_down': self.current_mouse_down,
            'progress': progress,
        }

        return telemetry

    def stop(self):
        """Emergency stop — release mouse."""
        self._set_mouse_down(False)
