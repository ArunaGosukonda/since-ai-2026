import { r as __toESM } from "../_runtime.mjs";
import { _ as createFileRoute, b as useRouter, d as Scripts, f as HeadContent, g as lazyRouteComponent, h as Outlet, m as createRouter, v as createRootRouteWithContext, y as Link } from "../_libs/@tanstack/react-router+[...].mjs";
import { n as require_jsx_runtime, r as require_react } from "../_libs/elevenlabs__react+react.mjs";
import { t as QueryClientProvider } from "../_libs/tanstack__react-query.mjs";
import { t as QueryClient } from "../_libs/tanstack__query-core.mjs";
import { existsSync } from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
//#region node_modules/.nitro/vite/services/ssr/assets/router-DqDxxA74.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
var styles_default = "/assets/styles-vCa1y1OU.css";
function reportLovableError(error, context = {}) {
	if (typeof window === "undefined") return;
	window.__lovableEvents?.captureException?.(error, {
		source: "react_error_boundary",
		route: window.location.pathname,
		...context
	}, {
		mechanism: "react_error_boundary",
		handled: false,
		severity: "error"
	});
	const stack = error instanceof Error ? error.stack : void 0;
	window.__lovableReportRuntimeError?.({
		message: describeThrown(error),
		...stack !== void 0 && { stack },
		filename: window.location.pathname
	});
}
var MAX_SERIALIZED_LENGTH = 2e3;
function describeThrown(error) {
	if (error instanceof Response) return `Response ${error.status}${error.url ? ` at ${error.url}` : ""}`;
	if (error instanceof Error) return error.message;
	if (typeof error === "string") return error;
	const { message } = error ?? {};
	if (typeof message === "string" && message.length > 0) return message;
	try {
		return JSON.stringify(error)?.slice(0, MAX_SERIALIZED_LENGTH) ?? String(error);
	} catch {
		return String(error);
	}
}
function NotFoundComponent() {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
		className: "flex min-h-screen items-center justify-center bg-background px-4",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "max-w-md text-center",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h1", {
					className: "text-7xl font-bold text-foreground",
					children: "404"
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
					className: "mt-4 text-xl font-semibold text-foreground",
					children: "Page not found"
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "mt-2 text-sm text-muted-foreground",
					children: "The page you're looking for doesn't exist or has been moved."
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "mt-6",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Link, {
						to: "/",
						className: "inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90",
						children: "Go home"
					})
				})
			]
		})
	});
}
function ErrorComponent({ error, reset }) {
	console.error(error);
	const router = useRouter();
	(0, import_react.useEffect)(() => {
		reportLovableError(error, { boundary: "tanstack_root_error_component" });
	}, [error]);
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
		className: "flex min-h-screen items-center justify-center bg-background px-4",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "max-w-md text-center",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h1", {
					className: "text-xl font-semibold tracking-tight text-foreground",
					children: "This page didn't load"
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "mt-2 text-sm text-muted-foreground",
					children: "Something went wrong on our end. You can try refreshing or head back home."
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "mt-6 flex flex-wrap justify-center gap-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
						onClick: () => {
							router.invalidate();
							reset();
						},
						className: "inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90",
						children: "Try again"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("a", {
						href: "/",
						className: "inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent",
						children: "Go home"
					})]
				})
			]
		})
	});
}
var Route$3 = createRootRouteWithContext()({
	head: () => ({
		meta: [
			{ charSet: "utf-8" },
			{
				name: "viewport",
				content: "width=device-width, initial-scale=1"
			},
			{ title: "DNA Assistant — Scam protection demo" },
			{
				name: "description",
				content: "Scam-protection assistant demo for older people."
			},
			{
				property: "og:type",
				content: "website"
			},
			{
				name: "twitter:card",
				content: "summary_large_image"
			},
			{
				name: "twitter:site",
				content: "@Lovable"
			}
		],
		links: [
			{
				rel: "stylesheet",
				href: styles_default
			},
			{
				rel: "icon",
				href: "/favicon.ico",
				type: "image/x-icon"
			},
			{
				rel: "preconnect",
				href: "https://fonts.googleapis.com"
			},
			{
				rel: "preconnect",
				href: "https://fonts.gstatic.com",
				crossOrigin: "anonymous"
			},
			{
				rel: "stylesheet",
				href: "https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap"
			}
		]
	}),
	shellComponent: RootShell,
	component: RootComponent,
	notFoundComponent: NotFoundComponent,
	errorComponent: ErrorComponent
});
function RootShell({ children }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("html", {
		lang: "en",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("head", { children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(HeadContent, {}) }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("body", { children: [children, /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Scripts, {})] })]
	});
}
function RootComponent() {
	const { queryClient } = Route$3.useRouteContext();
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(QueryClientProvider, {
		client: queryClient,
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Outlet, {})
	});
}
var $$splitComponentImporter = () => import("./routes-1RK-hh5Z.mjs");
var Route$2 = createFileRoute("/")({
	head: () => ({ meta: [
		{ title: "DNA Assistant — Scam protection demo" },
		{
			name: "description",
			content: "A phone demo of DNA Assistant, a scam-protection assistant for older people."
		},
		{
			property: "og:title",
			content: "DNA Assistant — Scam protection demo"
		},
		{
			property: "og:description",
			content: "A phone demo of DNA Assistant, a scam-protection assistant for older people."
		},
		{
			property: "og:type",
			content: "website"
		},
		{
			name: "twitter:card",
			content: "summary"
		}
	] }),
	component: lazyRouteComponent($$splitComponentImporter, "component")
});
/**
* POST /api/classify  {mode?: "sms" | "chat" | "call", sender?, body, lang, granted?: string[], profile?: "default" | "esim"}
*   ->  the project pipeline's decision (dsa/pipeline.py via tools/classify_message.py).
* mode "sms" (default): a forwarded text. mode "chat": the user's own description of what happened.
* mode "call": the caller's words in a live call, transcribed so far.
* granted: consent-gated signal paths the user agreed to share (re-run after "Yes, check").
* profile: synthetic demo account. "default" is clean; "esim" adds a recent eSIM change (presenter key P only).
* The text is passed as JSON on stdin, never through a shell. Set PYTHON_BIN to choose the interpreter.
* The child gets only PATH and PYTHONDONTWRITEBYTECODE, never the API keys in process.env.
*/
var ROOT = path.resolve(process.cwd(), "..");
var SCRIPT = path.join(ROOT, "tools", "classify_message.py");
var LANGS = /* @__PURE__ */ new Set([
	"en",
	"fi",
	"sv"
]);
var SIGNAL_PATH = /^[a-z_]+(\.[a-z_]+)?$/;
var PROFILES = /* @__PURE__ */ new Set(["default", "esim"]);
function pythonBin() {
	if (process.env["PYTHON_BIN"]) return process.env["PYTHON_BIN"];
	const venv = path.join(ROOT, ".venv", "bin", "python");
	return existsSync(venv) ? venv : "python3";
}
function runPipeline(input) {
	return new Promise((resolve, reject) => {
		const child = spawn(pythonBin(), [SCRIPT], {
			cwd: ROOT,
			env: {
				PATH: process.env["PATH"] ?? "/usr/bin:/bin",
				PYTHONDONTWRITEBYTECODE: "1"
			}
		});
		let out = "";
		let err = "";
		const timer = setTimeout(() => {
			child.kill();
			reject(/* @__PURE__ */ new Error("pipeline timeout"));
		}, 8e3);
		child.stdout.on("data", (d) => out += d.toString());
		child.stderr.on("data", (d) => err += d.toString());
		child.on("error", (e) => {
			clearTimeout(timer);
			reject(e);
		});
		child.on("close", (code) => {
			clearTimeout(timer);
			if (code === 0) resolve(out);
			else reject(/* @__PURE__ */ new Error(`pipeline exit ${code}: ${err.slice(-300)}`));
		});
		child.stdin.end(JSON.stringify(input));
	});
}
var Route$1 = createFileRoute("/api/classify")({ server: { handlers: { POST: async ({ request }) => {
	const b = await request.json().catch(() => null);
	const mode = b?.mode === "chat" || b?.mode === "call" ? b.mode : "sms";
	const body = typeof b?.body === "string" ? b.body.slice(0, mode === "sms" ? 1e3 : 4e3) : "";
	if (!body.trim()) return new Response("Missing body", { status: 400 });
	const sender = typeof b?.sender === "string" && b.sender.trim() ? b.sender.slice(0, 60) : "Unknown";
	const lang = typeof b?.lang === "string" && LANGS.has(b.lang) ? b.lang : "en";
	const profile = typeof b?.profile === "string" && PROFILES.has(b.profile) ? b.profile : "default";
	try {
		const granted = Array.isArray(b?.granted) ? b.granted.filter((g) => typeof g === "string" && SIGNAL_PATH.test(g)).slice(0, 20) : [];
		const apiBase = process.env["API_BASE_URL"] || "http://127.0.0.1:8080";
		try {
			const res = await fetch(`${apiBase}/api/classify`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					mode,
					sender,
					body,
					lang,
					granted,
					profile
				})
			});
			if (res.ok) {
				const data = await res.text();
				return new Response(data, { headers: { "Content-Type": "application/json" } });
			}
		} catch (e) {
			console.warn("Direct API call to /api/classify failed, falling back to local python", e);
		}
		const out = await runPipeline({
			mode,
			sender,
			body,
			lang,
			granted,
			profile
		});
		return new Response(out, { headers: { "Content-Type": "application/json" } });
	} catch (e) {
		console.error("classify failed", e);
		return new Response("pipeline unavailable", { status: 502 });
	}
} } } });
var Route = createFileRoute("/api/tts")({ server: { handlers: { POST: async ({ request }) => {
	const key = process.env["ELEVENLABS_API_KEY"];
	if (!key) return new Response("ElevenLabs not connected", { status: 503 });
	const body = await request.json().catch(() => null);
	const text = typeof body?.text === "string" ? body.text.slice(0, 1500) : "";
	if (!text.trim()) return new Response("Missing text", { status: 400 });
	const voice = process.env["ELEVENLABS_VOICE_ID"] || "YSabzCJMvEHDduIDMdwV";
	const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voice}?output_format=mp3_44100_128`, {
		method: "POST",
		headers: {
			"xi-api-key": key,
			"Content-Type": "application/json"
		},
		body: JSON.stringify({
			text,
			model_id: "eleven_flash_v2_5",
			voice_settings: {
				stability: .75,
				similarity_boost: .75,
				style: 0,
				speed: .9
			}
		})
	});
	if (!r.ok) {
		const err = await r.text();
		console.error(`tts failed [${r.status}]: ${err}`);
		let reason = "";
		try {
			reason = JSON.parse(err).detail?.code ?? "";
		} catch {}
		return new Response(`TTS failed [${r.status}]${reason ? ` ${reason}` : ""}`, { status: 502 });
	}
	return new Response(r.body, { headers: {
		"Content-Type": "audio/mpeg",
		"Cache-Control": "no-store"
	} });
} } } });
var rootRouteChildren = {
	IndexRoute: Route$2.update({
		id: "/",
		path: "/",
		getParentRoute: () => Route$3
	}),
	ApiClassifyRoute: Route$1.update({
		id: "/api/classify",
		path: "/api/classify",
		getParentRoute: () => Route$3
	}),
	ApiTtsRoute: Route.update({
		id: "/api/tts",
		path: "/api/tts",
		getParentRoute: () => Route$3
	})
};
var routeTree = Route$3._addFileChildren(rootRouteChildren)._addFileTypes();
var getRouter = () => {
	const queryClient = new QueryClient();
	return createRouter({
		routeTree,
		context: { queryClient },
		scrollRestoration: true,
		defaultPreloadStaleTime: 0
	});
};
//#endregion
export { getRouter };
