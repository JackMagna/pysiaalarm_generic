# Esempio base: entità alarm_control_panel
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity

class PysiaalarmPanel(AlarmControlPanelEntity):
    def __init__(self, name):
        self._name = name
        self._state = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    def alarm_arm_away(self, **kwargs):
        self._state = "armed_away"

    def alarm_disarm(self, **kwargs):
        self._state = "disarmed"
