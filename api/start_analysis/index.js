const {LAMBDA} =require('@aws-sdk/client-lambda')
const {S3} =require('@aws-sdk/client-s3')

const region = process.env.AWS_REGION
const lambda_function_name = process.env.START_ANALYSIS_FUNCTION

const lambda_function = new AWS.Lambda({
    region: region
})


exports.handler = function (event, context) {
    console.log("Processing event:\n"+JSON.stringify(event))

    var response = {
        headers: {
            'Access-Control-Allow-Origin': '*'
        },
        statusCode: 200,
        body: {
            msg: "",
            data: {}
        }
    };

    if(!validate_params(event)){
        response["statusCode"] = 400
        response["body"]["msg"] = "Invalid request, validate all parameters are present."
        context.succeed(response)
    }

    try{
        var params = {
            FunctionName: lambda_function_name,
            InvocationType: 'RequestResponse',
            LogType: 'Tail',
            Payload: event
        };
        lambda_function.invoke(params,function(err,data){
           if(err){
               context.fail(err)
           } else{
               response['body'] = data.Payload
           }
        });
    }catch (e) {
        response["statusCode"] = 500
        response["body"]["msg"] = "Exception occured while invoking lambda function."
        context.succeed(response)
    }

    console.log(response);
    context.succeed(response);
};

function validate_params(request){
    if(!request.hasOwnProperty('s3_path')){
        console.log("Missing s3_path on request")
        return false
    }
    if(!request.hasOwnProperty('analysis_list')){
        console.log("Missing analysis_list on request")
        return false
    }
    if(!request.hasOwnProperty('sample_rate')){
        console.log("Missing sample_rate on request")
        return false
    }
    return true
}

/*
* endpoint: { s3_path, analysis_list,sample_rate}
* endpoint: {uuid, status_job, outputbucket}
* endpoint: {uuid, status_for_each_analysis}
* policies for each lambda
* */