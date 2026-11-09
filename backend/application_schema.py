"""Inventory of application-owned tables; never includes test fixture metadata."""
import importlib


def application_tables():
    modules = [importlib.import_module('models')]
    modules += [importlib.import_module('modules.devices.' + name) for name in (
        'models', 'verification_models', 'pending_models', 'biometric_models',
        'activation_models', 'management_models')]
    modules += [importlib.import_module(name) for name in (
        'modules.authorization.models', 'modules.networks.models',
        'modules.classroom_wifi.models', 'modules.classroom_ble.models')]
    from models import Base
    from modules.classroom_wifi.models import ClassroomBase
    from modules.classroom_ble.models import BleBase
    names = {obj.__table__.name for module in modules for obj in vars(module).values()
             if isinstance(obj, type) and obj.__module__ == module.__name__ and hasattr(obj, '__table__')}
    return [table for metadata in (Base.metadata, ClassroomBase.metadata, BleBase.metadata)
            for table in metadata.sorted_tables if table.name in names]
