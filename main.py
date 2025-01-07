import ctypes
from ctypes.wintypes import DWORD, LONG, BOOL, WCHAR, LUID
import sys

# Estructuras necesarias para la API de configuración de pantalla
class DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
    _fields_ = [
        ('sourceInfo', DWORD),
        ('targetInfo', DWORD * 16),
    ]

class DISPLAYCONFIG_SOURCE_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ('type', DWORD),
        ('size', DWORD),
        ('adapterId', LUID),
        ('anonId', DWORD),
        ('deviceName', WCHAR * 32),
    ]

class DISPLAYCONFIG_TARGET_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ('type', DWORD),
        ('size', DWORD),
        ('adapterId', LUID),
        ('outputTechnology', DWORD),
        ('edidManufactureId', DWORD),
        ('edidProductCodeId', DWORD),
        ('connectorId', DWORD),
        ('monitorFriendlyDeviceName', WCHAR * 64),
        ('monitorDevicePath', WCHAR * 128),
    ]

class DISPLAYCONFIG_VIDEO_SIGNAL_INFO(ctypes.Structure):
    _fields_ = [
        ('pixelRate', LONG),
        ('hSyncFreqDivider', DWORD),
        ('vSyncFreqDivider', DWORD),
        ('syncInfo', DWORD),
        ('videoStandard', DWORD),
        ('scanLineOrdering', DWORD),
    ]

class DISPLAYCONFIG_MODE_INFO(ctypes.Structure):
    _fields_ = [
        ('infoType', DWORD),
        ('id', DWORD),
        ('adapterId', LUID),
        ('mode', DISPLAYCONFIG_VIDEO_SIGNAL_INFO),
    ]

class DISPLAYCONFIG_ADAPTER_NAME(ctypes.Structure):
    _fields_ = [
        ('type', DWORD),
        ('size', DWORD),
        ('adapterId', LUID),
        ('adapterName', WCHAR * 128),
    ]

class DISPLAYCONFIG_PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [
        ('adapterId', LUID),
        ('id', DWORD),
        ('modeInfoIdx', DWORD),
        ('outputTechnology', DWORD),
        ('rotation', DWORD),
        ('scaling', DWORD),
        ('rateNumerator', DWORD),
        ('rateDenominator', DWORD),
        ('scanLineOrdering', DWORD),
        ('targetAvailable', BOOL),
        ('statusFlags', DWORD),
        ('adapterTargetName', DISPLAYCONFIG_ADAPTER_NAME),
    ]

# Constantes necesarias
QDC_ONLY_ACTIVE_PATHS = 0x00000001
QDC_DATABASE_CURRENT = 0x00000001
DISPLAYCONFIG_PATH_ACTIVE = 0x00000001
DISPLAYCONFIG_HDR_METADATA_TYPE1 = 1
SDC_APPLY = 0x00000080
SDC_USE_DATABASE_CURRENT = 0x000000F
DISPLAYCONFIG_OUTPUT_TECHNOLOGY_INTERNAL = -2147483648
DISPLAYCONFIG_OUTPUT_TECHNOLOGY_DISPLAYPORT_EMBEDDED = 7
DISPLAYCONFIG_OUTPUT_TECHNOLOGY_HDMI = 8
DISPLAYCONFIG_OUTPUT_TECHNOLOGY_DISPLAYPORT = 10
DISPLAYCONFIG_QCT_PATH_TARGET_INFO = 3 # Valor para obtener información del target path.

# Nuevo flag para HDR (tomado de la documentación)
DISPLAYCONFIG_VSIF_SUPPORT_HDR = 0x00000800

def set_hdr(monitor_index: int, enable: bool):
    gdi32 = ctypes.windll.gdi32
    num_paths = ctypes.c_uint32()
    num_modes = ctypes.c_uint32()

    # Obtener el número de rutas y modos activos
    if gdi32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(num_paths), ctypes.byref(num_modes)) != 0:
        print("Error al obtener el tamaño del buffer de configuración.")
        return

    path_array = (DISPLAYCONFIG_PATH_INFO * num_paths.value)()
    mode_array = (DISPLAYCONFIG_MODE_INFO * num_modes.value)()

    # Obtener la configuración actual de la pantalla
    if gdi32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(num_paths), path_array, ctypes.byref(num_modes), mode_array, None) != 0:
        print("Error al obtener la configuración actual de la pantalla.")
        return

    target_index = 0
    current_monitor_index = 1
    found = False

    for i in range(num_paths.value):
        path_info = path_array[i]
        target_info = DISPLAYCONFIG_PATH_TARGET_INFO()
        req = gdi32.GetDisplayConfigTargetDeviceInfo(DISPLAYCONFIG_QCT_PATH_TARGET_INFO, ctypes.byref(path_info.targetInfo[target_index]), ctypes.sizeof(target_info), ctypes.byref(target_info))

        if req == 0:
            if target_info.outputTechnology != DISPLAYCONFIG_OUTPUT_TECHNOLOGY_INTERNAL:
                source_name = DISPLAYCONFIG_SOURCE_DEVICE_NAME()
                source_name.type = 1
                source_name.size = ctypes.sizeof(source_name)
                source_name.adapterId = path_info.sourceInfo
                gdi32.DisplayConfigGetDeviceInfo(ctypes.byref(source_name))

                target_name = DISPLAYCONFIG_TARGET_DEVICE_NAME()
                target_name.type = 2
                target_name.size = ctypes.sizeof(target_name)
                target_name.adapterId = path_info.targetInfo[target_index].adapterId
                target_name.connectorId = path_info.targetInfo[target_index].id
                gdi32.DisplayConfigGetDeviceInfo(ctypes.byref(target_name))

                print(f"Monitor #{current_monitor_index}: {target_name.monitorFriendlyDeviceName}")

                if current_monitor_index == monitor_index:
                    print(f"Monitor encontrado: {target_name.monitorFriendlyDeviceName}")
                    found = True
                    # Modificar la configuración para activar/desactivar HDR
                    for j in range(num_modes.value):
                        mode_info = mode_array[j]
                        if mode_info.adapterId.LowPart == path_info.targetInfo[target_index].adapterId.LowPart and \
                           mode_info.adapterId.HighPart == path_info.targetInfo[target_index].adapterId.HighPart and \
                           mode_info.id == path_info.targetInfo[target_index].modeInfoIdx:
                            print("Modo encontrado, modificando configuración HDR...")
                            if enable:
                                mode_info.mode.syncInfo |= DISPLAYCONFIG_VSIF_SUPPORT_HDR
                            else:
                                mode_info.mode.syncInfo &= ~DISPLAYCONFIG_VSIF_SUPPORT_HDR

                            # Aplicar la nueva configuración
                            path_array[i].flags |= DISPLAYCONFIG_PATH_ACTIVE
                            config_flags = SDC_APPLY | SDC_USE_DATABASE_CURRENT
                            result = gdi32.SetDisplayConfig(num_paths, path_array, num_modes, mode_array, config_flags)
                            if result == 0:
                                print(f"HDR {'activado' if enable else 'desactivado'} para el monitor {monitor_index}.")
                            else:
                                print(f"Error al {'activar' if enable else 'desactivar'} HDR. Código de error: {result}")
                            return True
                    if not found:
                        print(f"No se encontró información de modo para el monitor {monitor_index}.")
                        return False
                current_monitor_index += 1

    if not found:
        print(f"No se encontró el monitor con índice {monitor_index}.")
    return found

def main():
    manager = MonitorManager()

    while True:
        print("\n=== Gestión de Monitores ===")
        print("1. Mostrar información de monitores")
        print("2. Extender pantallas")
        print("3. Duplicar pantallas")
        print("4. Activar monitor específico")
        print("5. Activar/Desactivar HDR")
        print("6. Salir")

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
                monitors = manager.get_monitors()
                if not monitors:
                    print("No se detectaron monitores.")
                    continue
                print("\nMonitores disponibles:")
                for i, monitor in enumerate(monitors, 1):
                    print(f"{i}: {monitor.display_name}")
                monitor_num = int(input("\nIngrese el número del monitor para activar/desactivar HDR: "))
                if 1 <= monitor_num <= len(monitors):
                    hdr_enabled = input("¿Activar HDR? (s/n): ").lower() == 's'
                    set_hdr(monitor_num, hdr_enabled)
                else:
                    print("Número de monitor inválido.")

            elif option == 6:
                break

            else:
                print("Opción no válida")

            if option != 6:
                input("\nPresione Enter para continuar...")

        except ValueError:
            print("Por favor, ingrese un número válido")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    from monitores import MonitorManager
    main()
