/// <reference path="./.sst/platform/config.d.ts" />

export default $config({
  app(input) {
    return {
      name: "nextstopkc",
      removal: input?.stage === "production" ? "retain" : "remove",
      home: "aws",
      providers: {
        aws: {
          region: "us-east-1",
        },
      },
    };
  },
  async run() {
    // --- Secrets ---
    const databaseUrl = new sst.Secret("DatabaseUrl");
    const gtfsRtApiKey = new sst.Secret("GtfsRtApiKey");

    // --- Domain ---
    const domain =
      $app.stage === "production"
        ? "nextstopkc.app"
        : `${$app.stage}.nextstopkc.app`;

    // --- API Gateway + Lambda ---
    const api = new sst.aws.ApiGatewayV2("Api", {
      domain: {
        name: domain,
        dns: sst.aws.dns(),
      },
      cors: {
        allowOrigins: ["*"],
        allowMethods: ["GET", "POST", "OPTIONS"],
        allowHeaders: ["content-type"],
      },
    });

    const apiFn = new sst.aws.Function("FastApi", {
      runtime: "python3.12",
      handler: "src/better_transit/handler.handler",
      url: false,
      timeout: "30 seconds",
      memory: "512 MB",
      python: {
        container: true,
      },
      environment: {
        DATABASE_URL: databaseUrl.value,
        GTFS_RT_API_KEY: gtfsRtApiKey.value,
      },
      link: [databaseUrl, gtfsRtApiKey],
    });

    // Route all requests to the FastAPI Lambda
    api.route("$default", apiFn.arn);

    // --- Scheduled GTFS Import ---
    new sst.aws.Cron("GtfsImport", {
      schedule: "cron(0 12 * * ? *)", // 12:00 UTC = 6:00 AM CT
      function: {
        runtime: "python3.12",
        handler: "src/better_transit/gtfs/importer.lambda_handler",
        timeout: "300 seconds",
        memory: "1024 MB",
        python: {
          container: true,
        },
        environment: {
          DATABASE_URL: databaseUrl.value,
        },
        link: [databaseUrl],
      },
    });

    return {
      api: api.url,
      domain: domain,
    };
  },
});
