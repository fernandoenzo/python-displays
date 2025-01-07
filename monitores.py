import ctypes
from ctypes import wintypes
import sys
from typing import List, Dict
from dataclasses import dataclass

# Estructuras necesarias para las APIs de Windows
class DISPLAY_DEVICE(ctypes.Structure):
    _fields_ = [
        ('cb', ctypes.c_int),
        ('DeviceName', ctypes.c_wchar * 32),
        ('DeviceString', ctypes.c_wchar * 128),
        ('StateFlags', ctypes.c_ulong),
        ('DeviceID', ctypes.c_wchar * 128),
        ('DeviceKey', ctypes.c_wchar * 128)
    ]

class DEVMODE(ctypes.Structure):
    _fields_ = [
        ('dmDeviceName', ctypes.c_wchar * 32),
        ('dmSpecVersion', ctypes.c_short),
        ('dmDriverVersion', ctypes.c_short),
        ('dmSize', ctypes.c_short),
        ('dmDriverExtra', ctypes.c_short),
        ('dmFields', ctypes.c_int),
        ('dmPositionX', ctypes.c_int),
        ('dmPositionY', ctypes.c_int),
        ('dmDisplayOrientation', ctypes.c_int),
        ('dmDisplayFixedOutput', ctypes.c_int),
        ('dmColor', ctypes.c_short),
        ('dmDuplex', ctypes.c_short),
        ('dmYResolution', ctypes.c_short),
        ('dmTTOption', ctypes.c_short),
        ('dmCollate', ctypes.c_short),
        ('dmFormName', ctypes.c_wchar * 32),
        ('dmLogPixels', ctypes.c_short),
        ('dmBitsPerPel', ctypes.c_int),
        ('dmPelsWidth', ctypes.c_int),
        ('dmPelsHeight', ctypes.c_int),
        ('dmDisplayFlags', ctypes.c_int),
        ('dmDisplayFrequency', ctypes.c_int),
        ('dmICMMethod', ctypes.c_int),
        ('dmICMIntent', ctypes.c_int),
        ('dmMediaType', ctypes.c_int),
        ('dmDitherType', ctypes.c_int),
        ('dmReserved1', ctypes.c_int),
        ('dmReserved2', ctypes.c_int),
        ('dmPanningWidth', ctypes.c_int),
        ('dmPanningHeight', ctypes.c_int)
    ]

@dataclass
class Monitor:
    index: int
    device_name: str
    display_name: str
    is_primary: bool
    is_active: bool

class MonitorManager:
    # Constantes
    ENUM_CURRENT_SETTINGS = -1
    CDS_UPDATEREGISTRY = 0x01
    CDS_TEST = 0x02
    DISP_CHANGE_SUCCESSFUL = 0
    DISP_CHANGE_RESTART = 1
    DISP_CHANGE_FAILED = -1

    def __init__(self):
        self.user32 = ctypes.windll.user32

    def get_monitors(self) -> List[Monitor]:
        """Obtiene la lista de monitores conectados."""
        monitors = []

        display_device = DISPLAY_DEVICE()
        display_device.cb = ctypes.sizeof(display_device)

        i = 0
        while True:
            result = self.user32.EnumDisplayDevicesW(None, i, ctypes.byref(display_device), 0)
            if not result:
                break

            if display_device.StateFlags & 0x1:  # DISPLAY_DEVICE_ACTIVE
                monitor = Monitor(
                    index=i,
                    device_name=display_device.DeviceName,
                    display_name=display_device.DeviceString,
                    is_primary=(display_device.StateFlags & 0x4) != 0,  # DISPLAY_DEVICE_PRIMARY_DEVICE
                    is_active=True
                )
                monitors.append(monitor)
            i += 1

        return monitors

    def set_single_display(self, monitor_number: int) -> bool:
        """Activa un monitor específico y desactiva los demás."""
        monitors = self.get_monitors()

        if monitor_number < 1 or monitor_number > len(monitors):
            print(f"Error: Monitor inválido. Monitores disponibles: {len(monitors)}")
            return False

        selected_monitor = monitors[monitor_number - 1]
        print(f"Configurando monitor {monitor_number} ({selected_monitor.display_name}) como único monitor activo...")

        for monitor in monitors:
            devmode = DEVMODE()
            devmode.dmSize = ctypes.sizeof(devmode)

            result = self.user32.EnumDisplaySettingsW(
                monitor.device_name,
                self.ENUM_CURRENT_SETTINGS,
                ctypes.byref(devmode)
            )

            if monitor.index == selected_monitor.index:
                # Activar el monitor seleccionado
                devmode.dmFields = 0x020  # DM_PELSWIDTH | DM_PELSHEIGHT
                result = self.user32.ChangeDisplaySettingsExW(
                    monitor.device_name,
                    ctypes.byref(devmode),
                    None,
                    self.CDS_UPDATEREGISTRY | self.CDS_TEST,
                    None
                )

                if result == self.DISP_CHANGE_SUCCESSFUL:
                    result = self.user32.ChangeDisplaySettingsExW(
                        monitor.device_name,
                        ctypes.byref(devmode),
                        None,
                        self.CDS_UPDATEREGISTRY,
                        None
                    )
                    print(f"Monitor {monitor_number} activado correctamente")
                else:
                    print(f"Error al activar el monitor {monitor_number}")
                    return False
            else:
                # Desactivar los otros monitores
                devmode.dmFields = 0x020
                devmode.dmPelsWidth = 0
                devmode.dmPelsHeight = 0

                self.user32.ChangeDisplaySettingsExW(
                    monitor.device_name,
                    ctypes.byref(devmode),
                    None,
                    self.CDS_UPDATEREGISTRY,
                    None
                )

        return True

    def set_display_mode(self, mode: str) -> bool:
        """Configura el modo de visualización (extend/clone)."""
        monitors = self.get_monitors()

        if mode == "extend":
            x_pos = 0
            for monitor in monitors:
                devmode = DEVMODE()
                devmode.dmSize = ctypes.sizeof(devmode)

                result = self.user32.EnumDisplaySettingsW(
                    monitor.device_name,
                    self.ENUM_CURRENT_SETTINGS,
                    ctypes.byref(devmode)
                )

                devmode.dmFields = 0x020 | 0x002  # DM_POSITION
                devmode.dmPositionX = x_pos
                devmode.dmPositionY = 0

                result = self.user32.ChangeDisplaySettingsExW(
                    monitor.device_name,
                    ctypes.byref(devmode),
                    None,
                    self.CDS_UPDATEREGISTRY,
                    None
                )

                x_pos += devmode.dmPelsWidth
            print("Monitores configurados en modo extendido")
            return True

        elif mode == "clone":
            if monitors:
                primary_monitor = next((m for m in monitors if m.is_primary), monitors[0])
                devmode = DEVMODE()
                devmode.dmSize = ctypes.sizeof(devmode)

                result = self.user32.EnumDisplaySettingsW(
                    primary_monitor.device_name,
                    self.ENUM_CURRENT_SETTINGS,
                    ctypes.byref(devmode)
                )

                for monitor in monitors:
                    if not monitor.is_primary:
                        result = self.user32.ChangeDisplaySettingsExW(
                            monitor.device_name,
                            ctypes.byref(devmode),
                            None,
                            self.CDS_UPDATEREGISTRY,
                            None
                        )
                print("Monitores configurados en modo clonado")
                return True

        return False

def main():
    manager = MonitorManager()

    while True:
        print("\n=== Gestión de Monitores ===")
        print("1. Mostrar información de monitores")
        print("2. Extender pantallas")
        print("3. Duplicar pantallas")
        print("4. Activar monitor específico")
        print("5. Salir")

        try:
            option = int(input("\nSeleccione una opción: "))

            if option == 1:
                monitors = manager.get_monitors()
                print(f"\nMonitores detectados: {len(monitors)}")
                for i, monitor in enumerate(monitors, 1):
                    print(f"\nMonitor {i}:")
                    print(f"  Nombre: {monitor.device_name}")
                    print(f"  Descripción: {monitor.display_name}")
                    print(f"  Principal: {monitor.is_primary}")
                    print(f"  Activo: {monitor.is_active}")

            elif option == 2:
                manager.set_display_mode("extend")

            elif option == 3:
                manager.set_display_mode("clone")

            elif option == 4:
                monitors = manager.get_monitors()
                print(f"\nMonitores disponibles: {len(monitors)}")
                for i, monitor in enumerate(monitors, 1):
                    print(f"{i}: {monitor.display_name}")
                monitor_num = int(input("\nIngrese el número del monitor que desea activar: "))
                manager.set_single_display(monitor_num)

            elif option == 5:
                break

            else:
                print("Opción no válida")

            if option != 5:
                input("\nPresione Enter para continuar...")

        except ValueError:
            print("Por favor, ingrese un número válido")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
