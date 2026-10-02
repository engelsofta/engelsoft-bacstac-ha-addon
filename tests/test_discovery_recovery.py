"""Exercise production discovery methods without BACnet hardware dependencies."""
import ast
import asyncio
import logging
import unittest
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).parents[1] / 'engelsoft_bacstac/rootfs/usr/bin/BACnetIOHandler.py'

class Identifier(tuple):
    def __new__(cls, value):
        return super().__new__(cls, value)

class BacnetError(Exception):
    pass

def load_methods(*names):
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'BACnetIOHandler')
    methods = [n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name in names]
    module = ast.Module(body=methods, type_ignores=[])
    scope = dict(ObjectIdentifier=Identifier, ObjectType=lambda x: x,
                 ErrorRejectAbortNack=BacnetError, ErrorType=type('ErrorType', (), {}),
                 LOGGER=logging.getLogger('test'), object_properties_to_read_once=[])
    exec(compile(module, str(SOURCE), 'exec'), scope)
    return SimpleNamespace(**{name: scope[name] for name in names})

class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    def handler(self, error):
        objects = [Identifier(('analogValue', 1)), Identifier(('analogValue', 905))]
        visited = []
        async def request(device, method, **kwargs):
            obj = kwargs['parameter_list'][0]
            visited.append(obj[1])
            if obj[1] == 1:
                raise BacnetError(error)
            return []
        handler = SimpleNamespace(
            bacnet_device_dict={'device:1': {'device:1': {'objectList': objects}}},
            vendor_info=SimpleNamespace(registered_object_classes={'analogValue'}),
            _run_discovery_request=request, read_property_multiple=None,
            dev_to_addr=lambda device: 'test', dict_updater=lambda **kwargs: None)
        return handler, visited

    async def test_object_error_does_not_hide_later_av(self):
        handler, visited = self.handler('other')
        result = await load_methods('read_multiple_objects').read_multiple_objects(handler, Identifier(('device', 1)))
        self.assertFalse(result)
        self.assertEqual(visited, [1, 905])

    async def test_offline_station_stops_requests(self):
        handler, visited = self.handler('no-response')
        result = await load_methods('read_multiple_objects').read_multiple_objects(handler, Identifier(('device', 1)))
        self.assertFalse(result)
        self.assertEqual(visited, [1])

    async def test_incremental_read_only_requests_new_av(self):
        handler, visited = self.handler('other')
        result = await load_methods('read_multiple_objects').read_multiple_objects(
            handler, Identifier(('device', 1)), objects=[Identifier(('analogValue', 905))])
        self.assertTrue(result)
        self.assertEqual(visited, [905])

    async def test_repeated_iam_does_not_overlap(self):
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []
        async def check(apdu):
            calls.append(apdu)
            entered.set()
            await release.wait()
        handler = SimpleNamespace(_active_discovery_devices=set(),
                                  identifier_to_string=lambda obj: 'device:1', _check_object_list=check)
        method = load_methods('handle_object_list_check').handle_object_list_check
        apdu = SimpleNamespace(iAmDeviceIdentifier=Identifier(('device', 1)))
        task = asyncio.create_task(method(handler, apdu))
        await entered.wait()
        await method(handler, apdu)
        release.set()
        await task
        self.assertEqual(len(calls), 1)
        self.assertEqual(handler._active_discovery_devices, set())

if __name__ == '__main__':
    unittest.main()
