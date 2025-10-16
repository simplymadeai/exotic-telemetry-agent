class PID:
    def __init__(self,kp=0.6,ki=0.04,kd=0.1,setpoint=55.0,out_min=-300,out_max=300):
        self.kp,self.ki,self.kd=kp,ki,kd; self.setpoint=setpoint; self.out_min,out_max=out_min,out_max; self.out_max=out_max; self.integral=0.0; self.prev_error=None
    def update(self,measurement,dt=1.0):
        error=self.setpoint-measurement; self.integral+=error*dt; deriv=0.0 if self.prev_error is None else (error-self.prev_error)/max(dt,1e-6); self.prev_error=error
        out=self.kp*error + self.ki*self.integral + self.kd*deriv
        return max(self.out_min, min(self.out_max, out))
