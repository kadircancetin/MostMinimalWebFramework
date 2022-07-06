from most_minimal_web_framework import (
    ApiException,
    JSONResponse,
    MostMinimalWebFramework,
    Response,
)

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
        user_id = request.path[len("/user/") : -len("/posts")]
        return Response(f"posts for {user_id}", status_code=201)

    @app.route("/.*")
    def func_404(request):
        return Response("404", status_code=404)

    app.run("0.0.0.0", 8080)
