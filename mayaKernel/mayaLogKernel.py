import pathlib
import json
import socket
import threading
import time
import re

from ipykernel.kernelbase import Kernel


def get_maya_config():
    this_file_path = pathlib.Path(__file__)
    json_path = this_file_path.parent.joinpath("maya.json")
    config_dict = None
    with json_path.open("r") as f:
        config_dict = json.load(f)

    print(config_dict)
    # assert (pathlib.Path(config_dict["mayapyPath"]).exists())
    # for path in config_dict["python_path"]:
    #     assert (pathlib.Path(path).exists())
    return config_dict


def get_port_number(port_str):
    try:
        port_num = int(port_str)

        if 1 <= port_num <= 65535:
            return port_num
        else:
            return None
    except ValueError:
        return None


class FileListener(threading.Thread):
    def __init__(self, file_path, maya_kernel):
        threading.Thread.__init__(self)
        self.file_path = file_path
        self.kernel: MayaKernel = maya_kernel
        self.running = threading.Event()
        self.running.set()  # 设置为运行状态
        self.paused = threading.Event()
        self.paused.clear()  # 设置为未暂停状态
        self.last_position = 0
        self.file = None
        self.new_log = ""

    def update_log(self):
        if self.file is not None and not self.file.closed:
            log_read = self.file.read()  # 读取新增的行
            if log_read:
                self.new_log += log_read
                if self.kernel is not None:
                    self.kernel.send_response_text(log_read)

    def run(self):
        try:
            with open(self.file_path, 'r', encoding='locale') as file:
                file.seek(0, 2)  # 移动到文件末尾，准备读取新内容
                self.file = file
                # last_position = file.tell()  # 获取初始文件末尾位置

                self.running.wait()  # 等待线程运行信号
                while self.running.is_set():
                    self.paused.wait()  # 等待线程未暂停信号
                    self.update_log()
                    time.sleep(0.2)
        except Exception as e:
            print(e)

    def pause(self):
        self.paused.clear()  # 设置为暂停状态
        self.update_log()

    def resume(self):
        if self.file is not None and not self.file.closed:
            self.file.seek(0, 2)
        self.new_log = ""
        self.paused.set()  # 设置为未暂停状态

    def stop(self):
        self.paused.set()
        self.running.clear()  # 设置为停止状态

    def log_Empty(self):
        return len(self.new_log.strip()) <= 0


class MayaKernel(Kernel):
    implementation = 'Maya'
    implementation_version = '1.0'
    language = 'python'
    # language_version = '0.1'
    language_info = {
        'name': 'Maya Python',
        'mimetype': 'text/plain',
        'file_extension': '.py',
        'version': '0.1'
    }
    debugger = True,
    banner = "Maya kernel"
    maya_port = -1
    log_path = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        config_dict = get_maya_config()
        self.log_listener = None
        if "default_port" in config_dict:
            self.setPort(int(config_dict['default_port']))

    def setPort(self, port):
        self.maya_port = port
        self.log_path = self.setLogPath()
        if self.log_path is not None:
            if self.log_listener is not None:
                self.log_listener.stop()
                self.log_listener.join()
            self.log_listener = FileListener(self.log_path, self)
            self.log_listener.start()

    def setLogPath(self, log_path: str = None, port=-1):
        this_file_path = pathlib.Path(__file__)
        if log_path is None:
            log_path = this_file_path.parent.joinpath("mayalog.txt").__str__().replace('\\', r'/')
        else:
            log_path = log_path.__str__().replace('\\', r'/')
        code = "import maya.cmds as cmds;cmds.cmdFileOutput(closeAll=True);cmds.cmdFileOutput(o=\"{0}\")".format(
            log_path)
        try:
            sendCode2Maya(code, self.maya_port)
        except Exception as e:
            return None
        return log_path

    def send_err_response(self, text):
        stream_content = {'name': 'stderr', 'text': text}
        self.send_response(self.iopub_socket, 'stream', stream_content)

    def send_response_text(self, text):
        stream_content = {'name': 'stdout', 'text': text}
        self.send_response(self.iopub_socket, 'stream', stream_content)

    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False, *, cell_id=None, ):

        # if len(code.strip()) <= 0:
        #     return {'status': 'ok', 'execution_count': self.execution_count}
        pythonCode = True

        ErrRet = {'status': 'error',
                  'execution_count': self.execution_count,
                  }
        OkRet = {'status': 'ok',
                 'execution_count': self.execution_count,
                 'payload': [],
                 'user_expressions': {},
                 }

        if not code.strip():
            return OkRet  # Empty instruction returns directly

        # % 指令处理
        if code.startswith('%'):
            parts = code.split(maxsplit=1)
            if len(parts) > 1:
                command = parts[0][1:]
                args = parts[1].strip()
            else:
                command = parts[0][1:]
                args = ''

            if command == 'mel':
                code = args
                pythonCode = False
            elif command == 'setPort':
                port = get_port_number(args.split(maxsplit=1)[0])
                if port is not None:
                    self.setPort(port)
                    return OkRet
                else:
                    self.send_err_response("{} is not a valid port".format(args))
                    return ErrRet
            elif command == 'setlog':
                args = args.split()
                if len(args) > 0:
                    self.setLogPath(args[0])
                else:
                    self.setLogPath()
                return OkRet
            else:
                self.send_err_response("{} is not a valid command".format(command))
                return ErrRet

        if not silent:

            try:
                # last_position = 0
                # new_log = "Log path is not valid."
                #

                self.log_listener.resume()
                result = sendCode2Maya(code,
                                       port=self.maya_port,
                                       pythonCode=pythonCode)
            except ConnectionError as e:
                self.send_err_response(f"No maya session found at port {self.maya_port}.")
                return ErrRet
            except KeyboardInterrupt as e:
                self.send_err_response(f"KeyboardInterrupt got, but code in maya is still running")
                return ErrRet
            except BaseException as e:
                # self.log.debug(e)
                self.send_err_response(e.__str__())
                return ErrRet
            finally:
                self.log_listener.pause()

            if result.strip():
                if pythonCode:
                    errText = result
                    result_splitlines = result.splitlines()
                    if len(result_splitlines) > 1:
                        errText = '\n'.join(result_splitlines[1:])
                    self.send_err_response(errText)
                    return ErrRet

            if self.log_listener.log_Empty():
                self.send_response_text(result)
            # else:
            # self.send_response_text(self.log_listener.new_log)

        return OkRet

    def do_shutdown(self, restart):
        if self.log_listener is not None:
            self.log_listener.stop()
            self.log_listener.join()
        return {"status": "ok", "restart": restart}


def sendCode2Maya(code, port=-1, pythonCode=True):
    if port == -1:
        return "\nPort Not Available"

    host = 'localhost'
    client = None
    try:
        # Connect to Maya Command Port
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((host, port))
        message = code
        if pythonCode:
            message = re.sub(r"#.*?(\n|$)", '\n', message)  # 删除注释
            pattern = r'(".*?\\.*?"|\'.*?\\.*?\')'  # 引号内的\转码

            def replace_function(match):
                quoted_string = match.group(0)
                # 首先编码为 bytes 然后解码为 str，这将自动转义字符串中的字符
                # 'unicode_escape' 编码会处理转义字符
                escaped_string = quoted_string.encode('unicode_escape').decode('utf-8')
                unicode_pattern = r'\\u([0-9a-fA-F]{4})'

                def unicode_replacer(match):
                    # 从匹配的字符串中获取十六进制值并转换为字符
                    return chr(int(match.group(1), 16))

                decoded_string = re.sub(unicode_pattern, unicode_replacer, escaped_string)
                return decoded_string

            message = re.sub(pattern, replace_function, message, flags=re.DOTALL)

            message = 'python("' + message.replace(r'"', r'\"').replace('\r\n', '\n').replace('\r', '\n').replace('\n',
                                                                                                                  '\\n') + '")'
        # print(message)
        client.send(message.encode())
        data = client.recv(10240)
        result = data.strip(b"\x00").decode()
        if result:
            return result
    except BaseException as e:
        raise e

    finally:
        # Close Socket Connection
        if client is not None:
            client.close()


if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp

    IPKernelApp.launch_instance(kernel_class=MayaKernel)
