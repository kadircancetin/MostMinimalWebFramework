import json
import re
import traceback
from dataclasses import dataclass, field
from socket import AF_INET, SHUT_WR, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET, socket
from typing import Any, Callable, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse


@dataclass
class Request:
    method: str
    headers: Dict[str, str]
    path: str
    query_params: List[Dict[str, List[str]]] = field(default_factory=list)
    body: Any = None


@dataclass
class Response:
    body: Any
    status_code: int = 200
    content_type: str = "text/html"


class JSONResponse:
    def __new__(cls, *args, **kwargs):
        return Response(content_type="application/json", *args, **kwargs)


class ApiException(Response, BaseException):
    pass


class MostMinimalWebFramework:
    route_table: List[Tuple[re.Pattern, Callable]] = []

    def route(self, path: str) -> Callable:
        def decorator(func: Callable):
            def __inner():
                return func()

            self.route_table.append((re.compile(path + "$"), func))
            return __inner

        return decorator

    def get_route_function(self, searched_path: str) -> Callable:
        return next(r for r in self.route_table if r[0].match(searched_path))[1]

    def request_parser(self, request_str: str) -> Request:
        request_lines = request_str.split("\r\n")
        method, url, _ = request_lines[0].split(" ")  # first line has method and url

        headers = {}
        for i, line in enumerate(request_lines[1:], 1):

            if line == "":  # under empty line, whole data is body
                try:
                    body = json.loads("".join(request_lines[i + 1 :]))
                except json.JSONDecodeError:
                    body = "".join(request_lines[i + 1 :])
                break

            j = line.find(":")  # left part of : will key, right part will be value
            headers[line[:j].upper()] = line[j + 2 :]

        url = urlparse(url)
        return Request(method, headers, url.path, parse_qs(url.query), body)

    def build_response(self, r: Response) -> str:
        body = r.body if isinstance(r.body, str) else json.dumps(r.body)
        return (
            f"HTTP/1.1 {r.status_code}\r\nContent-Type: {r.content_type}; charset=utf-8"
            f"\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}"
        )

    def run(self, address: str, port: int):
        serversocket = socket(AF_INET, SOCK_STREAM)
        serversocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            serversocket.bind((address, port))
            serversocket.listen(5)
            while True:
                clientsocket, _ = serversocket.accept()
                request = clientsocket.recv(4096).decode()
                try:
                    parsed_req = self.request_parser(request)
                    response = self.get_route_function(parsed_req.path)(parsed_req)
                except ApiException as e:
                    response = e
                except Exception:
                    print(traceback.format_exc())
                    response = Response({"msg": "500 - server error"}, 500)
                print(response.status_code, parsed_req.method, parsed_req.path)
                clientsocket.sendall(self.build_response(response).encode())
                clientsocket.shutdown(SHUT_WR)
        finally:
            serversocket.close()
