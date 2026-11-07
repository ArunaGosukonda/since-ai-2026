//#region node_modules/.nitro/vite/services/ssr/assets/__23tanstack-start-server-fn-resolver-Cp4KqUr-.js
var manifest = {
	"2eb0bde687b0ba0c061cf756e51117504b7212db297968944e9d54d4befecfad": {
		functionName: "chatFn_createServerFn_handler",
		importer: () => import("./_ssr/live.functions-CYOK34TD.mjs")
	},
	"5d7c928e15040fe7e15b7b32a8bcba8a8c11d820fca04ba936dd5226a50387b4": {
		functionName: "analyzeFn_createServerFn_handler",
		importer: () => import("./_ssr/live.functions-CYOK34TD.mjs")
	},
	"6372e4994e44bb12096fbb4d85b9005118538271eed795d36972d3db5a196e17": {
		functionName: "sttTokenFn_createServerFn_handler",
		importer: () => import("./_ssr/live.functions-CYOK34TD.mjs")
	}
};
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
