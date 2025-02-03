import json
import re
import traceback
import asyncio
from dataclasses import dataclass, field
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


class JSONResponse(Response):
    def __new__(self, *args, **kwargs):
        super().__new__(*args, content_type="application/json", **kwargs)


class ApiException(Response, BaseException):
    content_type: str = "application/json"


class MostMinimalWebFramework:
    route_table: List[Tuple[re.Pattern, Callable]] = []

    def route(self, path: str) -> Callable:
        def decorator(func: Callable):
            self.route_table.append((re.compile(path + "$"), func))
            return func
        return decorator

    def get_route_function(self, searched_path: str) -> Callable:
        return next(r for r in self.route_table if r[0].match(searched_path))[1]

    def request_parser(self, request_str: str) -> Request:
        request_lines = request_str.split("\r\n")
        method, url, _ = request_lines[0].split(" ")  # first line has method and url

        headers = {}
        for i, line in enumerate(request_lines[1:], 1):
            if not line:  # under empty line, whole data is body
                try:
                    body = json.loads("".join(request_lines[i + 1:]))
                except json.JSONDecodeError:
                    body = "".join(request_lines[i + 1:])
                break

            j = line.find(":")  # left part of : will key, right part will be value
            headers[line[:j].upper()] = line[j + 2:]

        url = urlparse(url)
        return Request(method, headers, url.path, parse_qs(url.query), body)

    def build_response(self, r: Response) -> str:
        body = r.body if isinstance(r.body, str) else json.dumps(r.body)
        return (
            f"HTTP/1.1 {r.status_code}\r\nContent-Type: {r.content_type}; charset=utf-8"
            f"\r\nContent-Length: {len(body.encode('utf-8'))}\r\nConnection: close\r\n\r\n{body}"
        )

    async def handle_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        request = (await reader.read(40960)).decode()  # reading request
        try:
            parsed_req = self.request_parser(request)  # parsing request
            handler = self.get_route_function(parsed_req.path)  # getting handler
            response = await handler(parsed_req) if asyncio.iscoroutinefunction(handler) else handler(parsed_req)
        except ApiException as e:
            response = e
        except Exception:
            print(traceback.format_exc())
            response = Response({"msg": "500 - server error"}, 500)
        print(response.status_code, parsed_req.method, parsed_req.path)
        writer.write(self.build_response(response).encode())  # sending response
        await writer.drain()
        writer.close()  # closing connection

    async def _run(self, address: str, port: int):
        server = await asyncio.start_server(self.handle_request, address, port)
        print("Server started at: ", address, ":", port, sep="")
        async with server:
            await server.serve_forever()

    def run(self, address: str, port: int):
        asyncio.run(self._run(address, port))


if __name__ == "__main__":
    app = MostMinimalWebFramework()

    @app.route("/")
    def f(request):
        return Response("Hello World")

    @app.route("/json-response/")
    def json_response(request):
        return JSONResponse({"msg": "Hello World"})

    @app.route("/method-handling/")
    def method_handling(request):
        if request.method == "GET":
            return Response("Your method is GET")

        elif request.method == "POST":
            return Response("Your method is POST")

    @app.route("/status-code/")
    def status_code(request):
        return Response("Different status code", status_code=202)

    @app.route("/raise-exception/")
    def exception_raising(request):
        raise ApiException({"msg": "custom_exception"}, status_code=400)

    @app.route("/body-handle/")
    def body_handling(request):
        try:
            name = request.body["name"]
        except (KeyError, TypeError):
            raise ApiException({"msg": "name field required"}, status_code=400)

        return JSONResponse({"request__name": name})

    @app.route("/query-param-handling/")
    def query_param_handling(request):
        try:
            q_parameter = request.query_params["q"][0]
        except (KeyError, TypeError):
            raise ApiException({"msg": "q query paramter required"}, status_code=400)

        return JSONResponse({"your_q_parameter": q_parameter})

    @app.route("/header-handling/")
    def header_handling(request):
        try:
            token = request.headers["X-TOKEN"]
        except (KeyError, TypeError):
            raise ApiException({"msg": "Un authorized"}, status_code=403)

        return Response(f"your token {token}")

    @app.route("/user/[^/]*/posts")
    def varialbe_path(request):
        user_id = request.path[len("/user/"): -len("/posts")]
        return Response(f"posts for {user_id}", status_code=201)

    @app.route("/.*")
    def func_404(request):
        return Response("404", status_code=404)

    app.run(address="0.0.0.0", port=3000)
