import sys
import asyncio
import concurrent.futures
import json
import os
import shutil
import aiofiles
import websockets as ws
from multiprocessing import Process, Event
import signal
from random import randint
from hashlib import md5

import time

from ..log import *

from .CuemsProjectManager import CuemsMedia, CuemsProject
from .CuemsErrors import *
from .CuemsUtils import StringSanitizer, CuemsLibraryMaintenance, LIBRARY_PATH





formatter = logging.Formatter('Cuems:ws-server: %(levelname)s (PID: %(process)d)-%(threadName)-9s)-(%(funcName)s) %(message)s')


logger_ws_server = logging.getLogger('ws-server')
logger_ws_server.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger_ws_server.addHandler(handler)

logger_asyncio = logging.getLogger('asyncio')
logger_asyncio.setLevel(logging.INFO)  # asyncio debug level 

logger_ws = logging.getLogger('websockets')
logger_ws.setLevel(logging.INFO)  # websockets debug level,  in debug prints all frames, also binary frames! 

class CuemsWsServer():
    

    projects=[{"CuemsScript": {"uuid": "76861217-2d40-47a2-bdb5-8f9c91293855", "name": "Proyecto test 0", "date": "14/08/2020 11:18:16", "timecode_cuelist": {"CueList": {"Cue": [{"uuid": "bf2d217f-881d-47c1-9ad1-f5999769bcc5", "time": {"CTimecode": "00:00:33:00"}, "type": "mtc", "loop": "False", "outputs": {"CueOutputs": {"id": 5, "bla": "ble"}}}, {"uuid": "8ace53f3-74f5-4195-822e-93c12fdf3725", "time": {"NoneType": "None"}, "type": "floating", "loop": "False", "outputs": {"CueOutputs": {"physiscal": 1, "virtual": 3}}}], "AudioCue": {"uuid": "be288e38-887a-446f-8cbf-c16c9ec6724a", "time": {"CTimecode": "00:00:45:00"}, "type": "virtual", "loop": "True", "outputs": {"AudioCueOutputs": {"stereo": 1}}}}}, "floating_cuelist": {"CueList": {"DmxCue": {"uuid": "f36fa4b3-e220-4d75-bff1-210e14655c11", "time": {"CTimecode": "00:00:23:00"}, "dmx_scene": {"DmxScene": {"DmxUniverse": [{"id": 0, "DmxChannel": [{"id": 0, "&": 10}, {"id": 1, "&": 50}]}, {"id": 1, "DmxChannel": [{"id": 20, "&": 23}, {"id": 21, "&": 255}]}, {"id": 2, "DmxChannel": [{"id": 5, "&": 10}, {"id": 6, "&": 23}, {"id": 7, "&": 125}, {"id": 8, "&": 200}]}]}}, "outputs": {"DmxCueOutputs": {"universe0": 3}}}, "Cue": {"uuid": "17376d8f-84c6-4f28-859a-a01260a1dadb", "time": {"CTimecode": "00:00:05:00"}, "type": "virtual", "loop": "False", "outputs": {"CueOutputs": {"id": 3}}}}}}}, {"CuemsScript": {"uuid": "e05de59a-b281-4abf-83ba-97198d661a63", "name": "Segundo proyecto", "date": "13/08/2020 07:23:12", "timecode_cuelist": {"CueList": {"Cue": [{"uuid": "d47a75e2-f76e-4c77-b33e-e1df40ffdf02", "time": {"CTimecode": "00:00:33:00"}, "type": "mtc", "loop": "False", "outputs": {"CueOutputs": {"id": 5, "bla": "ble"}}}, {"uuid": "b5c35e3d-91f6-42d8-9825-0176354b44c1", "time": {"NoneType": "None"}, "type": "floating", "loop": "False", "outputs": {"CueOutputs": {"physiscal": 1, "virtual": 3}}}], "AudioCue": {"uuid": "aef5e289-03b0-4b39-99cd-90063d9b8c80", "time": {"CTimecode": "00:00:45:00"}, "type": "virtual", "loop": "True", "outputs": {"AudioCueOutputs": {"stereo": 1}}}}}, "floating_cuelist": {"CueList": {"DmxCue": {"uuid": "5d4ef443-5a49-4986-a283-9563ee7a9e85", "time": {"CTimecode": "00:00:23:00"}, "dmx_scene": {"DmxScene": {"DmxUniverse": [{"id": 0, "DmxChannel": [{"id": 0, "&": 10}, {"id": 1, "&": 50}]}, {"id": 1, "DmxChannel": [{"id": 20, "&": 23}, {"id": 21, "&": 255}]}, {"id": 2, "DmxChannel": [{"id": 5, "&": 10}, {"id": 6, "&": 23}, {"id": 7, "&": 125}, {"id": 8, "&": 200}]}]}}, "outputs": {"DmxCueOutputs": {"universe0": 3}}}, "Cue": {"uuid": "37f80125-1c41-4cce-aab1-13328dd8c94e", "time": {"CTimecode": "00:00:05:00"}, "type": "virtual", "loop": "False", "outputs": {"CueOutputs": {"id": 3}}}}}}}]
    tmp_upload_forlder_path = '/tmp/cuemsupload'
    
    media_path = os.path.join(LIBRARY_PATH, 'media')     #TODO: get upload folder path from settings?
    
    def __init__(self):
        self.state = {"value": 0} #TODO: provisional
        self.users = dict()
        try:
            if not os.path.exists(self.tmp_upload_forlder_path):
                os.mkdir(self.tmp_upload_forlder_path)
                logger.info('creating tmp upload folder {}'.format(self.tmp_upload_forlder_path))
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))



    def start(self, port):
        self.event = Event()
        self.process = Process(target=self.run_async_server, args=(self.event,))
        self.port = port
        self.host = 'localhost'
        self.process.start()

        

    def run_async_server(self, event):
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        self.executor =  concurrent.futures.ThreadPoolExecutor(thread_name_prefix='ws_load_ThreadPoolExecutor', max_workers=5) # TODO: adjust max workers
        #self.event_loop.set_exception_handler(self.exception_handler) ### TODO:UNCOMENT FOR PRODUCTION 
        self.project_server = ws.serve(self.connection_handler, self.host, self.port, max_size=None) #TODO: choose max packets size from ui and limit it here
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.event_loop.add_signal_handler(sig, self.ask_exit)
        logger.info('server listening on {}, port {}'.format(self.host, self.port))
        self.event_loop.run_until_complete(self.project_server)
        self.event_loop.run_forever()
        self.event_loop.close()
        
    def stop(self):
        os.kill(self.process.pid, signal.SIGTERM)
        self.process.join()
        logger.info('ws process joined')
        
    def ask_exit(self):
        self.event_loop.call_soon_threadsafe(self.project_server.ws_server.close)
        logger.info('ws server closing')
        asyncio.run_coroutine_threadsafe(self.stop_async(), self.event_loop)
              

    async def stop_async(self):
        await self.project_server.ws_server.wait_closed()
        logger.info('ws server closed')
        self.event_loop.call_soon(self.event_loop.stop)
        logger.info('event loop stoped')

    async def connection_handler(self, websocket, path):
        
        logger.info("new connection: {}, path: {}".format(websocket, path))

        if path == '/':                                    # project manager
            await self.project_manager_session(websocket)
        elif path == '/upload':                            # file upload
            await self.upload_session(websocket)
        else:
            logger.info("unknow path: {}".format(path))

    async def project_manager_session(self, websocket):
        user_session = CuemsWsUser(self, websocket)
        await self.register(user_session)
        await user_session.outgoing.put(self.counter_event())
        try:
            consumer_task = asyncio.create_task(user_session.consumer_handler())
            producer_task = asyncio.create_task(user_session.producer_handler())
            # start 3 message processing task so a load or any other time consuming action still leaves with 2 tasks running  and interface feels responsive. TODO:discuss this
            processor_tasks = [asyncio.create_task(user_session.consumer()) for _ in range(3)]
            
            done_tasks, pending_tasks = await asyncio.wait([consumer_task, producer_task, *processor_tasks], return_when=asyncio.FIRST_COMPLETED)

            for task in pending_tasks:
                task.cancel()

        finally:
            await self.unregister(user_session)

    async def upload_session(self, websocket):
        user_upload_session = CuemsUpload(self, websocket)
        logger.info("new upload session: {}".format(user_upload_session))

        await user_upload_session.message_handler()
        logger.info("upload session ended: {}".format(user_upload_session))

    async def register(self, user_task):
        logger.info("user registered: {}".format(id(user_task.websocket)))
        self.users[user_task] = None
        await self.notify_users("users")

    async def unregister(self, user_task):
        logger.info("user unregistered: {}".format(id(user_task.websocket)))
        self.users.pop(user_task, None)
        await self.notify_users("users")

    async def notify_state(self):
        if self.users:  # asyncio.wait doesn't accept an empty dcit
            message = self.counter_event()
            for user in self.users:
                await user.outgoing.put(message)

    async def notify_others_list_changes(self, calling_user, list_type):
        if self.users:  #notify others, not the user trigering the action, and only if the have same project loaded
            message = json.dumps({"type": "list_update", "value": list_type})
            for user, project in self.users.items():
                if user is not calling_user:
                    await user.outgoing.put(message)
                    logger.debug('notifing {} {}'.format(user, list_type))
            
    async def notify_others_same_project(self, calling_user, msg_type, project_uuid=None):
        if self.users:  #notify others, not the user trigering the action, and only if the have same project loaded
            message = json.dumps({"type" : "project_update", "value" : project_uuid})
            for user, project in self.users.items():
                if user is not calling_user:
                    if project_uuid is not None:
                        if str(project) != str(project_uuid):
                            continue
                    else:
                        if str(project) != str(self.users[calling_user]):
                            continue

                    logger.debug('same project loaded')
                    await user.outgoing.put(message)
                    logger.debug('notifing {}'.format(user))
    
    async def notify_users(self, type):
        if self.users:  # asyncio.wait doesn't accept an empty dcit
            message = self.users_event(type)
            await asyncio.wait([user.outgoing.put(message) for user in self.users])



    # warning, this non async function should bet not blocking or user @sync_to_async to get their own thread
    def counter_event(self):
        return json.dumps({"type": "counter", **self.state})


    def users_event(self, type, uuid=None):
        if type == "users":
            return json.dumps({"type": type, "value": len(self.users)})
        else:
            return json.dumps({"type": type, "uuid": uuid, "value" : "modified in server"}) # TODO: not used

    def exception_handler(self, loop, context):
        logger.debug("Caught the following exception: (ignore if on closing)")
        logger.debug(context['message'])


class CuemsWsUser():
    
    def __init__(self, server, websocket):
        self.server = server
        asyncio.set_event_loop(server.event_loop)
        self.incoming = asyncio.Queue()
        self.outgoing = asyncio.Queue()
        self.websocket = websocket
        server.users[self] = None

    async def consumer_handler(self):
        try:
            async for message in self.websocket:
                await self.incoming.put(message)
        except (ws.exceptions.ConnectionClosed, ws.exceptions.ConnectionClosedOK, ws.exceptions.ConnectionClosedError) as e:
                logger.debug(e)

    async def producer_handler(self):
        while True:
            message = await self.producer()
            try:
                await self.websocket.send(message)
            except (ws.exceptions.ConnectionClosed, ws.exceptions.ConnectionClosedOK, ws.exceptions.ConnectionClosedError) as e:
                logger.debug(e)
                break


    async def consumer(self):
        while True:
            message = await self.incoming.get()
            try:
                data = json.loads(message)
            except Exception as e:
                logger.error("error: {} {}".format(type(e), e))
                await self.notify_error_to_user('error decoding json') 
                continue
            try:
                if "action" not in data:
                    logger.error("unsupported event: {}".format(data))
                    await self.notify_error_to_user("unsupported event: {}".format(data))
                elif data["action"] == "minus":
                    self.server.state["value"] -= 1
                    await self.server.notify_state()
                elif data["action"] == "plus":
                    self.server.state["value"] += 1
                    await self.server.notify_state()
                elif data["action"] == "project_load":
                    await self.send_project(data["value"])
                elif data["action"] == "project_save":
                    await self.received_project(data["value"])
                elif data["action"] == "project_delete":
                    await self.request_delete_project(data["value"])
                elif data["action"] == "project_restore":
                    await self.request_restore_project(data["value"])
                elif data["action"] == "project_trash_delete":
                    await self.request_delete_project_trash(data["value"])
                elif data["action"] == "project_list":
                    await self.list_project()
                elif data["action"] == "file_list":
                    await self.list_file()
                elif data["action"] == "project_trash_list":
                    await self.list_project_trash()
                elif data["action"] == "file_trash_list":
                    await self.list_file_trash()
                elif data["action"] == "file_save":
                    await self.received_file_data(data["value"])
                elif data["action"] == "file_delete":
                    await self.request_delete_file(data["value"])
                elif data["action"] == "file_restore":
                    await self.request_restore_file(data["value"])
                elif data["action"] == "file_trash_delete":
                    await self.request_delete_file_trash(data["value"])
                else:
                    logger.error("unsupported action: {}".format(data))
                    await self.notify_error_to_user("unsupported action: {}".format(data))
            except Exception as e:
                logger.error("error: {} {}".format(type(e), e))
                await self.notify_error_to_user('error processing request')


    async def producer(self):
        while True:
            message = await self.outgoing.get()
            return message

    async def notify_user(self, msg=None, uuid=None, action=None):
        if (uuid is None) and (action is None) and (msg is not None):
            await self.outgoing.put(json.dumps({"type": "state", "value":msg}))
        elif (msg is None):
            await self.outgoing.put(json.dumps({"type": action, "value": uuid}))

    async def notify_error_to_user(self, msg=None, uuid=None, action=None):
        if (msg is not None) and (uuid is None) and (action is None):
            await self.outgoing.put(json.dumps({"type": "error", "value": msg}))
        elif (action is not None) and (msg is not None) and (uuid is None):
            await self.outgoing.put(json.dumps({"type": "error", "action": action, "value": msg}))
        elif (action is not None) and (msg is not None) and (uuid is not None):
            await self.outgoing.put(json.dumps({"type": "error", "uuid": uuid, "action": action, "value": msg}))


    async def list_project(self):
        logger.info("user {} loading project list".format(id(self.websocket)))
        try:
            project_list = await self.server.event_loop.run_in_executor(self.server.executor, self.load_project_list)    
            await self.outgoing.put(json.dumps({"type": "project_list", "value": project_list}))
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e),  action="project_list")

    async def send_project(self, project_uuid):
        try:
            if project_uuid == '':
                raise NonExistentItemError('project uuid is empty')
            logger.info("user {} loading project {}".format(id(self.websocket), project_uuid))
            project = await self.server.event_loop.run_in_executor(self.server.executor, self.load_project, project_uuid)
            msg = json.dumps({"type":"project", "value":project})
            await self.outgoing.put(msg)
            self.server.users[self] = project_uuid
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e), uuid=project_uuid, action="project_load")

    async def received_project(self, data):
        try:
            project = data
            project_uuid = None
            project_uuid = project['CuemsScript']['uuid']

            logger.info("user {} saving project {}".format(id(self.websocket), project_uuid))
            
            return_message = await self.server.event_loop.run_in_executor(self.server.executor, self.save_project, project_uuid, project)
            self.server.users[self] = project_uuid
            await self.notify_user(uuid=project_uuid, action="project_save")
            await self.server.notify_others_list_changes(self, "project_list")
            await self.server.notify_others_same_project(self, "project_modified", project_uuid)
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user((str(type(e)) + str(e)), uuid=project_uuid, action="project_save")

    async def list_project_trash(self):
        logger.info("user {} loading project trash list".format(id(self.websocket)))
        try:
            project_trash_list = await self.server.event_loop.run_in_executor(self.server.executor, self.load_project_trash_list)    
            await self.outgoing.put(json.dumps({"type": "project_trash_list", "value": project_trash_list}))
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e),  action="project_trash_list")

    async def request_delete_project(self, project_uuid):
        try:
            logger.info("user {} deleting project: {}".format(id(self.websocket), project_uuid))
            
            await self.server.event_loop.run_in_executor(self.server.executor, self.delete_project, project_uuid)

            await self.notify_user(uuid=project_uuid, action="project_delete")
            await self.server.notify_others_same_project(self, "project_update", project_uuid=project_uuid)
            await self.server.notify_others_list_changes(self, "project_list")
            await self.server.notify_others_list_changes(self, "project_trash_list")
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e), uuid=project_uuid, action="project_delete")

    async def request_restore_project(self, project_uuid):
        try:
            logger.info("user {} restoring project: {}".format(id(self.websocket), project_uuid))
            
            await self.server.event_loop.run_in_executor(self.server.executor, self.restore_project, project_uuid)

            await self.notify_user(uuid=project_uuid, action="project_restore")
            await self.server.notify_others_list_changes(self, "project_list")
            await self.server.notify_others_list_changes(self, "project_trash_list")
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e), uuid=project_uuid, action="project_restore")

    async def request_delete_project_trash(self, project_uuid):
        try:
            logger.info("user {} deleting project from trash: {}".format(id(self.websocket), project_uuid))
            
            await self.server.event_loop.run_in_executor(self.server.executor, self.delete_project_trash, project_uuid)

            await self.notify_user(uuid=project_uuid, action="project_trash_delete")
            await self.server.notify_others_list_changes(self, "project_trash_list")
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e), uuid=project_uuid, action="project_trash_delete")

    async def list_file(self):
        logger.info("user {} loading file list".format(id(self.websocket)))
        try:
            file_list = await self.server.event_loop.run_in_executor(self.server.executor, self.load_file_list)    
            await self.outgoing.put(json.dumps({"type": "file_list", "value": file_list}))
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e),  action="file_list")

    async def received_file_data(self, data):
        try:
            file_uuid = data['uuid']

            logger.info("user {} update file data {}".format(id(self.websocket), file_uuid))
            
            return_message = await self.server.event_loop.run_in_executor(self.server.executor, self.save_file, file_uuid, data)
            await self.notify_user(uuid=file_uuid, action="file_save")
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e), uuid=file_uuid, action="file_save")

    async def list_file_trash(self):
        logger.info("user {} loading file trash list".format(id(self.websocket)))
        try:
            file_trash_list = await self.server.event_loop.run_in_executor(self.server.executor, self.load_file_trash_list)    
            await self.outgoing.put(json.dumps({"type": "file_trash_list", "value": file_trash_list}))
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e),  action="file_trash_list")


    async def request_delete_file(self, file_uuid):
        try:
            logger.debug("user {} deleting file: {}".format(id(self.websocket), file_uuid))
            await self.server.event_loop.run_in_executor(self.server.executor, self.delete_file, file_uuid)
            await self.notify_user(uuid=file_uuid, action="file_delete")
            await self.server.notify_others_list_changes(self, "file_list")
            await self.server.notify_others_list_changes(self, "file_trash_list")
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e), uuid=file_uuid, action="file_delete")

    async def request_restore_file(self, file_uuid):
        try:
            logger.debug("user {} restoring file: {}".format(id(self.websocket), file_uuid))
            await self.server.event_loop.run_in_executor(self.server.executor, self.restore_file, file_uuid)
            await self.notify_user(uuid=file_uuid, action="file_restore")
            await self.server.notify_others_list_changes(self, "file_list")
            await self.server.notify_others_list_changes(self, "file_trash_list")
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e), uuid=file_uuid, action="file_restore")

    async def request_delete_file_trash(self, file_uuid):
        try:
            logger.info("user {} deleting file from trash: {}".format(id(self.websocket), file_uuid))
            await self.server.event_loop.run_in_executor(self.server.executor, self.delete_file_trash, file_uuid)
            await self.notify_user(uuid=file_uuid, action="file_trash_delete")
            await self.server.notify_others_list_changes(self, "file_trash_list")
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.notify_error_to_user(str(e), uuid=file_uuid, action="file_trash_delete")

    # call blocking functions asynchronously with run_in_executor ThreadPoolExecutor
    def load_project_list(self):
        logger.info("loading project list")
        return CuemsProject.list()

    
    def load_project(self, project_uuid):
        logger.info("loading project: {}".format(project_uuid))
        return CuemsProject.load(project_uuid)

    def save_project(self, project_uuid, data):
        logger.debug('saving project, uuid:{}, data:{}'.format(project_uuid, data))
        return CuemsProject.save(project_uuid, data)

    def delete_project(self, project_uuid):
        CuemsProject.delete(project_uuid)

    def restore_project(self, project_uuid):
        CuemsProject.restore(project_uuid)

    def load_project_trash_list(self):
        logger.info("loading project trash list")
        return CuemsProject.list_trash()

    def delete_project_trash(self, project_uuid):
        CuemsProject.delete_from_trash(project_uuid)

    def load_file_list(self):
        logger.info("loading file list")
        return CuemsMedia.list()

    def save_file(self, file_uuid, data):
        logger.info("saving file data")
        CuemsProject.save(file_uuid, data)

    def delete_file(self, file_uuid):
        CuemsMedia.delete(file_uuid)

    def restore_file(self, file_uuid):
        CuemsMedia.restore(file_uuid)

    def load_file_trash_list(self):
        logger.info("loading file trash list")
        return CuemsMedia.list_trash()

    def delete_file_trash(self, file_uuid):
        CuemsMedia.delete_from_trash(file_uuid)

class CuemsUpload(StringSanitizer):

    uploading = False
    filename = None
    tmp_filename = None
    bytes_received = 0
    filesize = 0
    file_handle = None

    def __init__(self, server, websocket):
        self.server = server
        self.websocket = websocket
        self.tmp_upload_forlder_path = server.tmp_upload_forlder_path
        self.media_path = server.media_path
        
    async def message_handler(self):
        while True:
            try:
                message = await self.websocket.recv()
                if isinstance(message, str):
                    await self.process_upload_message(message)
                elif isinstance(message, bytes):
                    await self.process_upload_packet(message)
            except (ws.exceptions.ConnectionClosed, ws.exceptions.ConnectionClosedOK, ws.exceptions.ConnectionClosedError):
                logger.debug('upload connection closed, exiting loop')
                break

    async def message_sender(self, message):
        try:
            await self.websocket.send(message)
        except (ws.exceptions.ConnectionClosed, ws.exceptions.ConnectionClosedOK, ws.exceptions.ConnectionClosedError) as e:
                logger.debug(e)

    async def process_upload_message(self, message):
        data = json.loads(message)
        if 'action' not in data:
            return False
        if data['action'] == 'upload':
            await self.set_upload(file_info=data["value"])
        elif data['action'] == 'finished':
            await self.upload_done(data["value"])

    async def set_upload(self, file_info):
        
        if not os.path.exists(self.media_path):
            logger.error("upload folder doenst exists")
            await self.message_sender(json.dumps({'error' : 'upload folder doenst exist', 'fatal': True}))
            return False
        
        self.filename = StringSanitizer.sanitize(file_info['name'])
        self.tmp_filename = self.filename + '.tmp' + str(randint(100000, 999999))
        logger.debug('tmp upload path: {}'.format(self.tmp_file_path()))

        if not os.path.exists(self.tmp_file_path()):
            self.filesize = file_info['size']
            self.uploading = 'Ready'
            await self.message_sender(json.dumps({"ready" : True}))
        else:
            await self.message_sender(json.dumps({'error' : 'file allready exists', 'fatal': True}))
            logger.error("file allready exists")

    async def process_upload_packet(self, bin_data):

        if self.uploading == 'Ready':
            async with aiofiles.open(self.tmp_file_path(), mode='wb', loop=self.server.event_loop, executor=self.server.executor) as stream:
                await stream.write(bin_data)
                self.bytes_received += len(bin_data)
                await self.message_sender(json.dumps({"ready" : True}))

                while True:
                    message = await self.websocket.recv()
                    if isinstance(message, bytes):
                        await stream.write(message)
                        self.bytes_received += len(message)
                        await self.message_sender(json.dumps({"ready" : True}))
                    else:
                        await self.process_upload_message(message)
                        break


    async def upload_done(self, received_md5):
        try:
            
            await self.server.event_loop.run_in_executor(self.server.executor, self.check_file_integrity,  self.tmp_file_path(), received_md5)
            
            await self.server.event_loop.run_in_executor(self.server.executor, CuemsMedia.new,  self.tmp_file_path(), self.filename)
            self.tmp_filename = None
            logger.debug('upload completed')
            await self.message_sender(json.dumps({"close" : True}))
            await self.server.notify_others_list_changes(None, "file_list")
        except Exception as e:
            logger.error("error: {} {}".format(type(e), e))
            await self.message_sender(json.dumps({'error' : 'error saving file', 'fatal': True}))

    def check_file_integrity(self, path, original_md5):
        
        with open(path, 'rb') as file_to_check:
            data = file_to_check.read()    
            returned_md5 = md5(data).hexdigest()
        if original_md5 != returned_md5:
            raise FileIntegrityError('MD5 mistmatch')
            
        return True

    def tmp_file_path(self):
        if not self.tmp_filename is None:
            return os.path.join(self.tmp_upload_forlder_path, self.tmp_filename)

    def __del__(self):
        try:
            if self.tmp_file_path():
                os.remove(self.tmp_file_path())  # TODO: change to pathlib ?  
                logger.debug('cleaning tmp upload file on object destruction: ({})'.format(self.tmp_file_path()))
        except FileNotFoundError:
            pass
