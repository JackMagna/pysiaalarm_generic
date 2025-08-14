# Esempio base per entità sensore
from homeassistant.components.sensor import SensorEntity

class PysiaalarmSensor(SensorEntity):
    def __init__(self, name):
        self._name = name
        self._state = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state
