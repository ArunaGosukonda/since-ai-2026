/**
 * Microphone consent for this session, shared by the chat mic and live calls. null = not asked yet.
 * Nothing is recorded and no audio leaves the device (no ElevenLabs token, no browser speech
 * recognition) until the user taps Allow.
 */
let consent: boolean | null = null;

export const getMicConsent = () => consent;
export const setMicConsent = (allow: boolean) => {
  consent = allow;
};
