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

            self.route_table.append((re.compile(path), func))
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
        body = json.dumps(r.body)
        return (
            f"HTTP/1.1 {r.status_code}\r\nContent-Type: {r.content_type}; charset=utf-8"
            f"\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}"
        )

    def run(self, address: str, port: int):
        serversocket = socket(AF_INET, SOCK_STREAM)
        serversocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            serversocket.bind(("0.0.0.0", port))
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


if __name__ == "__main__":

    app = MostMinimalWebFramework()

    @app.route("/hello-world/$")
    def hello_world(request):
        return Response("Hello World")

    @app.route("/json-response/$")
    def json_response(request):
        return JSONResponse({"msg": "Hello World"})

    @app.route("/method-handling/$")
    def method_handling(request: Request):
        if request.method == "GET":
            return Response("Your method is GET")

        elif request.method == "POST":
            return Response("Your method is POST")

    @app.route("/status-code/$")
    def status_code(request: Request):
        return Response("Different status code", status_code=202)

    @app.route("/raise-exception/$")
    def exception_raising(request: Request):
        raise ApiException({"msg": "custom_exception"}, status_code=400)

    @app.route("/body-handle/$")
    def body_handling(request: Request):
        try:
            name = request.body["name"]
        except (KeyError, TypeError):
            raise ApiException({"msg": "name field required"}, status_code=400)

        return JSONResponse({"request__name": name})

    @app.route("/query-param-handling/$")
    def query_param_handling(request: Request):
        try:
            q_parameter = request.query_params["q"][0]
        except (KeyError, TypeError):
            raise ApiException({"msg": "q query paramter required"}, status_code=400)

        return JSONResponse({"your_q_parameter": q_parameter})

    @app.route("/header-handling/$")
    def header_handling(request: Request):
        try:
            token = request.headers["X-TOKEN"]
        except (KeyError, TypeError):
            raise ApiException({"msg": "Un authorized"}, status_code=403)

        return Response(f"your token {token}")

    @app.route("/user/[^/]*/posts")
    def varialbe_path(request: Request):
        user_id = request.path[len("/user/") : -len("/posts")]
        return Response(f"posts for {user_id}", status_code=201)

    @app.route("/*")
    def func_404(request: Request):
        return Response("404", status_code=404)

    app.run("0.0.0.0", 8080)
