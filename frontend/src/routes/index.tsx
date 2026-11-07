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
  CallMicAsk,
  CallVerdict,
  IncomingCall,
  type CallPhase,
} from "@/components/CallScreens";
import { dangerPhrases } from "@/lib/dangerPhrases";
import { storyText, type ChatStory } from "@/lib/chat";
import { useLiveLog } from "@/lib/live";
import { setDemoProfile, useDemoProfile } from "@/lib/decision";
import { useLiveCall } from "@/lib/useLiveCall";
import { getMicConsent, setMicConsent } from "@/lib/micConsent";

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
  const [panel, setPanel] = useState(false);
  // Synthetic demo account: clean by default; the presenter switches to the eSIM persona with P.
  const demoProfile = useDemoProfile();
  const now = useNow();
  const t = i18n[lang];
  // Risk reached "scam": warn the user over the ongoing call. The call is NOT ended; the user decides.
  const warnScam = () => setScreen("callVerdict");
  // Calls are transcribed live; after each sentence dsa.pipeline judges everything said so far.
  const call = useLiveCall(lang, warnScam);
  const [callPhase, setCallPhase] = useState<CallPhase>("ringing");
  const [askMic, setAskMic] = useState(false);
  // "What happened": the danger phrases in everything the caller said (pipeline patterns).
  const callPhrases = dangerPhrases(call.bubbles.map((b) => bubbleText(b, lang)).join(" "));
  const logEntries = useLiveLog();
  const stopAll = useCallback(() => {
    setAskMic(false);
    call.stop();
  }, [call.stop]);

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
    setCallPhase("ringing");
    setScreen("incomingCall");
  };
  const answerCall = () => {
    setCallPhase("inCall");
    if (getMicConsent() === true) void call.start();
    else setAskMic(true); // nothing is recorded until the user taps Allow
  };
  const answerMic = (allow: boolean) => {
    setAskMic(false);
    setMicConsent(allow);
    if (allow) void call.start();
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
  const demoProfileRef = useRef(demoProfile);
  demoProfileRef.current = demoProfile;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) return;
      const k = e.key.toLowerCase();
      if (k === "`") setPanel((p) => !p);
      else if (k === "p") setDemoProfile(demoProfileRef.current === "esim" ? "default" : "esim");
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
        setDemoProfile("default");
      }
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
              mic={askMic ? "asking" : call.mic}
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
                openChat(openMsg.verdict ? "sms" : null);
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
            prefill={chatPrefill}
            onBack={goHome}
          />
        )}
        {banner && <StoppedBanner lang={lang} />}
        {askMic && screen === "incomingCall" && <CallMicAsk lang={lang} onAnswer={answerMic} />}
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

      {demoProfile === "esim" && (
        <div
          role="status"
          className="fixed left-1/2 top-3 z-20 -translate-x-1/2 rounded-full bg-ink/70 px-3 py-1 text-xs font-bold text-on-dark backdrop-blur"
        >
          Demo persona: recent eSIM change
        </div>
      )}

      {panel && (
        <div className="fixed bottom-4 left-4 w-80 rounded-xl bg-ink/70 p-4 text-sm leading-6 text-on-dark backdrop-blur">
          <div className="mb-2 flex items-center gap-2 font-bold">
            Presenter · decisions: dsa.pipeline · call: live transcription
            {logEntries[0] && !logEntries[0].ok && (
              <span
                title="Last pipeline / voice call failed"
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
            <li>4 DNA Assistant chat (dsa.pipeline)</li>
            <li>
              P demo persona: {demoProfile === "esim" ? "recent eSIM change" : "clean (default)"}
            </li>
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
