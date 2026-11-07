//#region node_modules/.nitro/vite/services/ssr/assets/__23tanstack-start-server-fn-resolver-vqAoBbka.js
var manifest = { "6372e4994e44bb12096fbb4d85b9005118538271eed795d36972d3db5a196e17": {
	functionName: "sttTokenFn_createServerFn_handler",
	importer: () => import("./_ssr/live.functions-Ca3Rt8lk.mjs")
} };
async function getServerFnById(id, access) {
	const serverFnInfo = manifest[id];
	if (!serverFnInfo) throw new Error("Server function info not found for " + id);
	const fnModule = serverFnInfo.module ??= await serverFnInfo.importer();
	if (!fnModule) throw new Error("Server function module not resolved for " + id);
	const action = fnModule[serverFnInfo.functionName];
	if (!action) throw new Error("Server function module export not resolved for serverFn ID: " + id);
	return action;
}
//#endregion
export { getServerFnById as t };
