exports.handler = function (event, context) {
    var response = {
        headers: {
            'Access-Control-Allow-Origin': '*'
        },
        statusCode: 200,
        body: {
            msg: "Sample API for prototype",
            data: {}
        }
    };
    console.log(response);
    context.succeed(response);
};