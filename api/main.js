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
/*
* endpoint: { s3_path, analysis_list,sample_rate}
* endpoint: {uuid, status_job, outputbucket}
* endpoint: {uuid, status_for_each_analysis}
* policies for each lambda
* */