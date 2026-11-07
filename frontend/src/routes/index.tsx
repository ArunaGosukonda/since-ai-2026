import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { Battery, Signal, Wifi } from "lucide-react";
import {
  AppHome,
  BackHome,
  DemoButton,
  LockScreen,
  PhoneApp,
  type AppId,
  type CallLog,
} from "@/components/HomeScreens";
import { i18n, locales, type Lang } from "@/lib/i18n";
import { ChatScreen } from "@/components/ChatScreen";
import { ComposeUnknown, Inbox, MessageDetail, StoppedBanner } from "@/components/MessageScreens";
import { classifySms, OLD_MESSAGES, pickExample, type Msg } from "@/lib/messages";
import {
  bubbleText,
  CallAfter,
  CallVerdict,
  IncomingCall,
  type Bubble,
  type CallPhase,
} from "@/components/CallScreens";
import { dangerPhrases } from "@/lib/dangerPhrases";
import { storyText, type ChatStory } from "@/lib/chat";
import { useLiveLog, maxStage, type LiveStage } from "@/lib/live";
import { analyzeCallSentence } from "@/lib/liveAgents";
import { useLiveStt } from "@/lib/useLiveStt";
import {
  CALL_AUDIO,
  FALLBACK_MS_PER_WORD,
  LINE_GAP_MS,
  scriptedResults,
  type Stage,
} from "@/lib/callScript";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "DNA Assistant — Scam protection demo" },
      {
        name: "description",
        content: "A phone demo of DNA Assistant, a scam-protection assistant for older people.",
      },
      { property: "og:title", content: "DNA Assistant — Scam protection demo" },
      {
        property: "og:description",
        content: "A phone demo of DNA Assistant, a scam-protection assistant for older people.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Demo,
});

type Screen =
  | "lock"
  | "home"
  | "phone"
  | "incomingCall"
  | "callVerdict"
  | "callAfter"
  | "inbox"
  | "messageDetail"
  | "chat";

const INITIAL_CALLS: CallLog[] = [
  { id: "anna", who: "anna", when: "today" },
  { id: "pharmacy", who: "pharmacy", when: "yesterday" },
];

function useNow() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 10000);
    return () => clearInterval(t);
  }, []);
  return now;
}

function Demo() {
  const [screen, setScreen] = useState<Screen>("lock");
  const [lang, setLang] = useState<Lang>("en");
  const [messages, setMessages] = useState<Msg[]>(OLD_MESSAGES);
  const [calls, setCalls] = useState<CallLog[]>(INITIAL_CALLS);
  /** Scam messages the user chose to keep; shown as normal messages afterwards. */
  const [ignored, setIgnored] = useState<string[]>([]);
  /** Demo only: the scam caller number was blocked and reported (nothing is sent anywhere). */
  const [numberBlocked, setNumberBlocked] = useState(false);
  /** Which story the chat was opened from ("Ask DNA Assistant" after the call or the parcel text);
   *  null = opened from the app icon: default story, nothing pre-filled. */
  const [chatStory, setChatStory] = useState<ChatStory | null>(null);
  /** The message the chat was opened from, quoted in the pre-filled question. */
  const [chatAbout, setChatAbout] = useState<Msg | null>(null);
  const [newId, setNewId] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [chatKey, setChatKey] = useState(0);
  const [banner, setBanner] = useState(false);
  const bannerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [live, setLive] = useState(false);
  const [panel, setPanel] = useState(false);
  const now = useNow();
  const t = i18n[lang];
  // Risk reached "scam": warn the user over the ongoing call. The call is NOT ended; the user decides.
  const warnScam = () => setScreen("callVerdict");
  const scripted = useScriptedCall(lang, warnScam);
  const liveCall = useLiveCall(lang, warnScam);
  const [callPhase, setCallPhase] = useState<CallPhase>("ringing");
  const [callMode, setCallMode] = useState<"scripted" | "live">("scripted");
  const call = callMode === "live" ? liveCall : scripted;
  // "What happened": the danger phrases in everything the caller said (pipeline patterns + model flags).
  const callPhrases = dangerPhrases(
    call.bubbles.map((b) => bubbleText(b, lang)).join(" "),
    call.liveFlags,
  );
  const liveRef = useRef(live);
  liveRef.current = live;
  const logEntries = useLiveLog();
  const stopAll = useCallback(() => {
    scripted.stop();
    liveCall.stop();
  }, [scripted.stop, liveCall.stop]);

  /** A text arrives: the project pipeline checks it first, then it lands in the inbox. */
  const [checkingSms, setCheckingSms] = useState(false);
  const lastExample = useRef<string | null>(null);
  const receiveSms = async (sender: string, text: string, msgLang: string, origin: string) => {
    setCheckingSms(true);
    const verdict = await classifySms(sender, text, msgLang);
    setCheckingSms(false);
    const at = Date.now();
    const msg: Msg = { id: `sms-${at}`, sender, text, time: "now", at, verdict, origin };
    setMessages((list) => [msg, ...list]);
    setNewId(msg.id);
    setScreen("inbox");
    if (verdict.stage === "scam") {
      setBanner(true);
      if (bannerTimer.current) clearTimeout(bannerTimer.current);
      bannerTimer.current = setTimeout(() => setBanner(false), 4000);
    }
  };
  /** Demo: a random text message from the dev dataset. */
  const receiveExample = () => {
    const e = pickExample(lang, lastExample.current);
    lastExample.current = e.case_id;
    void receiveSms(e.sender, e.body, e.lang, e.case_id);
  };
  /** Demo: a typed text, arriving from "Unknown". */
  const receiveTyped = (text: string) =>
    void receiveSms(t.phone.unknownSender, text, lang, "typed");
  const resetMessages = () => {
    setMessages(OLD_MESSAGES);
    setNewId(null);
    setOpenId(null);
    setBanner(false);
    setCalls(INITIAL_CALLS);
    setIgnored([]);
    setNumberBlocked(false);
  };
  const openChat = (story: ChatStory | null) => {
    setChatStory(story);
    setChatKey((n) => n + 1);
    setScreen("chat");
  };
  const openApp = (app: AppId) => {
    if (app === "phone") setScreen("phone");
    else if (app === "messages") {
      setBanner(false);
      setScreen("inbox");
    } else openChat(null);
  };
  const goHome = () => {
    stopAll();
    setScreen("home");
  };
  const openMsg = messages.find((m) => m.id === openId) ?? null;
  const chatPrefill = !chatStory
    ? ""
    : chatStory === "sms" && chatAbout
      ? storyText(lang, "sms")
          .prefill.replace("{sender}", chatAbout.sender)
          .replace("{text}", chatAbout.text)
      : storyText(lang, chatStory).prefill;

  const logCall = (note: CallLog["note"]) => {
    const at = Date.now();
    setCalls((list) => [{ id: `caller-${at}`, who: "caller", note, when: at }, ...list]);
  };
  /** The phone rings first; nothing is transcribed until the user answers. */
  const startCall = () => {
    stopAll();
    setCallMode(liveRef.current ? "live" : "scripted");
    setCallPhase("ringing");
    setScreen("incomingCall");
  };
  const answerCall = async () => {
    setCallPhase("inCall");
    if (liveRef.current) {
      setCallMode("live");
      if (await liveCall.start()) return;
    }
    setCallMode("scripted");
    scripted.start();
  };
  /** User declines while ringing, or hangs up during the call. */
  const declineCall = () => {
    stopAll();
    logCall(callPhase === "ringing" ? "declined" : call.stage === "scam" ? "warned" : undefined);
    setScreen("callAfter");
  };

  const receiveExampleRef = useRef(receiveExample);
  receiveExampleRef.current = receiveExample;
  const resetMsgRef = useRef(resetMessages);
  resetMsgRef.current = resetMessages;
  const startCallRef = useRef(startCall);
  startCallRef.current = startCall;
  const declineRef = useRef(declineCall);
  declineRef.current = declineCall;
  const answerRef = useRef(answerCall);
  answerRef.current = answerCall;
  const stopRef = useRef(stopAll);
  stopRef.current = stopAll;
  const screenRef = useRef(screen);
  screenRef.current = screen;
  const openChatRef = useRef(openChat);
  openChatRef.current = openChat;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) return;
      const k = e.key.toLowerCase();
      if (k === "`") setPanel((p) => !p);
      else if (k === "0") {
        stopRef.current();
        setScreen("home");
      } else if (k === "1") startCallRef.current();
      else if (k === "2") {
        stopRef.current();
        receiveExampleRef.current();
      } else if (k === "4") {
        stopRef.current();
        openChatRef.current(null);
      } else if (k === "a") {
        if (screenRef.current === "incomingCall") answerRef.current();
      } else if (k === "d") {
        if (screenRef.current === "incomingCall") declineRef.current();
      } else if (k === "r") {
        stopRef.current();
        setScreen("lock");
        resetMsgRef.current();
        setLang("en");
        setLive(false);
      } else if (k === "l") setLive((v) => !v);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const time = now?.toLocaleTimeString(locales[lang], { hour: "2-digit", minute: "2-digit" }) ?? "";
  const date =
    now?.toLocaleDateString(locales[lang], { weekday: "long", day: "numeric", month: "long" }) ??
    "";

  return (
    <main className="flex min-h-screen items-center justify-center bg-stage">
      <div className="phone-frame relative flex flex-col overflow-hidden bg-background text-ink">
        <div
          className="absolute left-1/2 top-2 z-10 h-7 w-32 -translate-x-1/2 rounded-full bg-ink"
          aria-hidden
        />
        <div className="flex h-12 shrink-0 items-center justify-between px-8 text-base font-bold">
          <span>{time}</span>
          <span className="flex items-center gap-1.5" aria-hidden>
            <Signal size={18} />
            <Wifi size={18} />
            <Battery size={22} />
          </span>
        </div>

        <div className="flex flex-1 flex-col overflow-y-auto px-6 pb-8">
          {screen === "lock" ? (
            <LockScreen
              lang={lang}
              setLang={setLang}
              time={time}
              date={date}
              onUnlock={() => setScreen("home")}
            />
          ) : screen === "home" ? (
            <AppHome lang={lang} time={time} onOpen={openApp} />
          ) : screen === "phone" ? (
            <PhoneApp
              lang={lang}
              calls={calls}
              numberBlocked={numberBlocked}
              onHome={goHome}
              onDemoCall={startCall}
            />
          ) : screen === "incomingCall" || screen === "callVerdict" || screen === "callAfter" ? (
            <IncomingCall
              lang={lang}
              phase={callPhase}
              liveMic={callMode === "live"}
              bubbles={call.bubbles}
              stage={call.stage}
              liveFlags={call.liveFlags}
              onDecline={declineCall}
              onAnswer={answerCall}
            />
          ) : screen === "inbox" ? (
            <div className="flex flex-1 flex-col pt-2">
              <BackHome label={t.home.home} onClick={goHome} />
              <Inbox
                lang={lang}
                messages={messages}
                newId={newId}
                ignored={ignored}
                onOpen={(m) => {
                  setBanner(false);
                  setOpenId(m.id);
                  setScreen("messageDetail");
                }}
              />
              <DemoButton onClick={receiveExample}>{t.phone.demoExample}</DemoButton>
              <ComposeUnknown lang={lang} busy={checkingSms} onSend={receiveTyped} />
            </div>
          ) : screen === "messageDetail" && openMsg ? (
            <MessageDetail
              lang={lang}
              msg={openMsg}
              ignored={ignored.includes(openMsg.id)}
              onIgnore={() => {
                setIgnored((ids) => [...ids, openMsg.id]);
                setScreen("inbox");
              }}
              onBack={() => setScreen("inbox")}
              onAsk={() => {
                setChatAbout(openMsg);
                openChat(openMsg.verdict?.stage === "scam" ? "sms" : null);
              }}
              onDelete={() => {
                setMessages((l) => l.filter((m) => m.id !== openMsg.id));
                setScreen("inbox");
              }}
            />
          ) : null}
        </div>
        {screen === "chat" && (
          <ChatScreen
            key={`${chatKey}-${lang}`}
            lang={lang}
            story={chatStory ?? "sim"}
            prefill={chatPrefill}
            onBack={goHome}
          />
        )}
        {banner && <StoppedBanner lang={lang} />}
        {screen === "callVerdict" && (
          <CallVerdict
            lang={lang}
            reasonText={call.reason}
            onHangUp={declineCall}
            onContinue={() => setScreen("incomingCall")}
          />
        )}
        {screen === "callAfter" && (
          <CallAfter
            lang={lang}
            phrases={callPhrases}
            blocked={numberBlocked}
            onBlock={() => setNumberBlocked(true)}
            onAsk={() => openChat("call")}
            onHome={goHome}
          />
        )}
      </div>

      {panel && (
        <div className="fixed bottom-4 left-4 w-80 rounded-xl bg-ink/70 p-4 text-sm leading-6 text-on-dark backdrop-blur">
          <div className="mb-2 flex items-center gap-2 font-bold">
            Presenter · {live ? "Live" : "Scripted"}
            {logEntries[0] && !logEntries[0].ok && (
              <span
                title="Last live call fell back to scripted"
                className="h-2 w-2 rounded-full bg-ink-secondary"
                aria-label="fallback used"
              />
            )}
          </div>
          <div>
            Screen: {screen} · risk: {call.stage}
          </div>
          <ul className="mt-2 opacity-80">
            <li>0 home screen · R lock + reset</li>
            <li>1 incoming call · A answer · D decline/hang up</li>
            <li>2 random dataset SMS</li>
            <li>4 DNA Assistant chat · L live/scripted</li>
            <li>` hide panel</li>
          </ul>
          {logEntries.length > 0 && (
            <div className="mt-2 max-h-64 overflow-y-auto border-t border-on-dark/20 pt-2 font-mono text-[11px] leading-4">
              {logEntries.map((e) => (
                <div key={e.id} className="mb-1.5 break-all">
                  <span className={e.ok ? "font-bold" : "font-bold opacity-60"}>
                    {e.ok ? "●" : "○"} {e.source}
                  </span>{" "}
                  <span className="opacity-80">{e.json.slice(0, 400)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </main>
  );
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function useScriptedCall(lang: Lang, onScam: () => void) {
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [stage, setStage] = useState<Stage>("listening");
  const [liveFlags, setLiveFlags] = useState<string[]>([]);
  const [reason, setReason] = useState<string | undefined>(undefined);
  const token = useRef(0);
  const audio = useRef<HTMLAudioElement | null>(null);
  const langRef = useRef(lang);
  langRef.current = lang;
  const onScamRef = useRef(onScam);
  onScamRef.current = onScam;

  const stop = useCallback(() => {
    token.current++;
    audio.current?.pause();
    audio.current = null;
  }, []);

  const start = useCallback(async () => {
    stop();
    const my = token.current;
    const alive = () => token.current === my;
    setBubbles([]);
    setStage("listening");
    setLiveFlags([]);
    setReason(undefined);
    const lines = i18n[langRef.current].call.lines;
    const wordsOf = (l: string) => l.split(" ").length;

    // One recording of the whole call (English). Each line gets a share of its length in
    // proportion to its English word count, so the text appears in step with the voice.
    // Other languages show the translated text on a timer, without the English audio.
    let lineMs = lines.map((l) => wordsOf(l) * FALLBACK_MS_PER_WORD);
    if (langRef.current === "en") {
      const a = new Audio(CALL_AUDIO);
      audio.current = a;
      const durMs = await new Promise<number | null>((res) => {
        const t = setTimeout(() => res(null), 2000);
        a.onloadedmetadata = () => {
          clearTimeout(t);
          res(isFinite(a.duration) ? a.duration * 1000 : null);
        };
        a.onerror = () => {
          clearTimeout(t);
          res(null);
        };
      });
      if (!alive()) return;
      if (durMs) {
        const enWords = i18n.en.call.lines.map(wordsOf);
        const total = enWords.reduce((x, y) => x + y, 0);
        lineMs = enWords.map((w) => (durMs * w) / total);
        a.play().catch(() => {});
      } else {
        audio.current = null; // no usable recording: timed text with pauses instead
      }
    }

    for (let line = 0; line < lines.length; line++) {
      if (!alive()) return;
      if (line > 0 && !audio.current) await sleep(LINE_GAP_MS); // pauses are inside the recording
      setBubbles((b) => [...b, { line, shown: 0 }]);
      const words = wordsOf(lines[line]!);
      const step = lineMs[line]! / words;
      for (let w = 1; w <= words; w++) {
        await sleep(step);
        if (!alive()) return;
        setBubbles((b) => b.map((x) => (x.line === line ? { ...x, shown: w } : x)));
      }

      // Analyze sentence using Since AI backend intelligence
      const curLine = lines[line]!;
      const soFar = lines.slice(0, line).join(" ");
      try {
        const res = await analyzeCallSentence(curLine, soFar, langRef.current);
        if (res.flags?.length) {
          setLiveFlags((f) => [...f, ...res.flags.filter((x) => !f.includes(x))]);
        }
        if (res.reason) {
          setReason(res.reason);
        }
        if (res.stage && res.stage !== "listening" && res.stage !== "safe") {
          setStage(res.stage as Stage);
          if (res.stage === "scam") {
            if (audio.current) audio.current.volume = 0.3;
            setTimeout(() => {
              if (alive()) onScamRef.current();
            }, 600);
          }
        } else {
          const r = scriptedResults[line];
          if (r) {
            setStage(r.stage);
            if (r.stage === "scam") {
              if (audio.current) audio.current.volume = 0.3;
              setTimeout(() => {
                if (alive()) onScamRef.current();
              }, 600);
            }
          }
        }
      } catch {
        const r = scriptedResults[line];
        if (r) {
          setStage(r.stage);
          if (r.stage === "scam") {
            if (audio.current) audio.current.volume = 0.3;
            setTimeout(() => {
              if (alive()) onScamRef.current();
            }, 600);
          }
        }
      }
    }
  }, [stop]);

  useEffect(() => stop, [stop]);
  return { bubbles, stage, liveFlags, reason, start, stop };
}

type LiveBubble = Bubble & { text: string };

function useLiveCall(lang: Lang, onScam: () => void) {
  const stt = useLiveStt();
  const [bubbles, setBubbles] = useState<LiveBubble[]>([]);
  const [stage, setStage] = useState<Stage>("listening");
  const [liveFlags, setLiveFlags] = useState<string[]>([]);
  const [reason, setReason] = useState<string | undefined>(undefined);
  const stageRef = useRef<LiveStage>("listening");
  const said = useRef<string[]>([]);
  const token = useRef(0);
  const onScamRef = useRef(onScam);
  onScamRef.current = onScam;

  const stop = useCallback(() => {
    token.current++;
    stt.stop();
  }, [stt.stop]);

  const start = useCallback(async () => {
    stop();
    const my = token.current;
    setBubbles([]);
    setStage("listening");
    setLiveFlags([]);
    setReason(undefined);
    stageRef.current = "listening";
    said.current = [];
    const ok = await stt.start(lang, {
      onPartial: (p) => {
        if (token.current !== my) return;
        const line = said.current.length;
        setBubbles((b) => [...b.filter((x) => x.line !== line), { line, shown: 0, text: p }]);
      },
      onCommitted: async (sentence) => {
        if (token.current !== my) return;
        const line = said.current.length;
        const soFar = said.current.join(" ");
        said.current.push(sentence);
        setBubbles((b) => [
          ...b.filter((x) => x.line !== line),
          { line, shown: 0, text: sentence },
        ]);
        const r = await analyzeCallSentence(sentence, soFar, lang);
        if (token.current !== my) return;
        if (r.flags.length) setLiveFlags((f) => [...f, ...r.flags.filter((x) => !f.includes(x))]);
        if (r.reason && r.stage !== "safe" && r.stage !== "listening") setReason(r.reason);
        const next = maxStage(stageRef.current, r.stage === "safe" ? "listening" : r.stage);
        if (next === stageRef.current) return;
        stageRef.current = next;
        setStage(next as Stage);
        if (next === "scam")
          setTimeout(() => {
            if (token.current === my) onScamRef.current();
          }, 600);
      },
    });
    return ok && token.current === my;
  }, [lang, stop, stt.start]);

  useEffect(() => stop, [stop]);
  return { bubbles, stage, liveFlags, reason, start, stop };
}
