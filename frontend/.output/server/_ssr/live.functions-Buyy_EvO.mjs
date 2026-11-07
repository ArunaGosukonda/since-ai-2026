import { a as TSS_SERVER_FUNCTION, l as createServerFn } from "./createServerFn-DDDJMFWM.mjs";
import processModule from "node:process";
//#region node_modules/.nitro/vite/services/ssr/assets/live.functions-Buyy_EvO.js
var createServerRpc = (serverFnMeta, splitImportFn) => {
	const url = "/_serverFn/" + serverFnMeta.id;
	return Object.assign(splitImportFn, {
		url,
		serverFnMeta,
		[TSS_SERVER_FUNCTION]: true
	});
};
/** Single-use ElevenLabs realtime STT token. Only requested after the user allowed the microphone. */
var sttTokenFn_createServerFn_handler = createServerRpc({
	id: "6372e4994e44bb12096fbb4d85b9005118538271eed795d36972d3db5a196e17",
	name: "sttTokenFn",
	filename: "src/lib/live.functions.ts"
}, (opts) => sttTokenFn.__executeServer(opts));
var sttTokenFn = createServerFn({ method: "POST" }).handler(sttTokenFn_createServerFn_handler, async () => {
	let key = processModule.env["ELEVENLABS_API_KEY"];
	if (!key) try {
		const fs = await import("node:fs");
		const path = await import("node:path");
		const candidates = [
			path.resolve(processModule.cwd(), ".env"),
			path.resolve(processModule.cwd(), "src/.env"),
			path.resolve(processModule.cwd(), "frontend/.env"),
			path.resolve(processModule.cwd(), "frontend/src/.env")
		];
		for (const p of candidates) if (fs.existsSync(p)) {
			const m = fs.readFileSync(p, "utf-8").match(/^ELEVENLABS_API_KEY=(.+)$/m);
			if (m && m[1]) {
				key = m[1].trim();
				break;
			}
		}
	} catch {}
	if (!key) return {
		ok: false,
		error: "ElevenLabs not connected"
	};
	const r = await fetch("https://api.elevenlabs.io/v1/single-use-token/realtime_scribe", {
		method: "POST",
		headers: { "xi-api-key": key }
	});
	if (!r.ok) {
		const body = await r.text();
		console.error(`stt-token failed [${r.status}]: ${body}`);
		return {
			ok: false,
			error: `stt-token ${r.status}`
		};
	}
	return {
		ok: true,
		data: (await r.json()).token
	};
});
//#endregion
export { sttTokenFn_createServerFn_handler };
