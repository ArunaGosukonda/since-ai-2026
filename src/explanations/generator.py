# -*- coding: utf-8 -*-
"""Action-First Explanation and Step Generator for DNA Digital Security Assistant.
Composes localized, jargon-free, grounded advice adhering strictly to:
- Action-first placement (primary step in sentences 1-2)
- Word count 20-200 words, average sentence length <= 22 words
- Full trilingual support (Finnish, English, Swedish)
- Zero unsafe claims
"""
from typing import Any, Dict, List, Optional, Tuple
from src.intelligence.signal_fusion import FusedContext

# Canonical phrases for each step in FI, EN, SV
# Tested against dsakit/textcheck.py
STEP_TEXTS = {
    "explain_benign": {
        "fi": "Tämä viesti vaikuttaa aidolta eikä vaadi toimenpiteitä.",
        "en": "This message looks genuine and no action is needed.",
        "sv": "Det här meddelandet verkar äkta och du behöver inte göra något.",
    },
    "dont_open_link": {
        "fi": "Älä avaa linkkiä äläkä kirjaudu sen kautta.",
        "en": "Do not open the link or enter details through it.",
        "sv": "Öppna inte länken och logga inte in via den.",
    },
    "dont_pay_or_transfer": {
        "fi": "Älä maksa tai siirrä rahaa ennen kuin asia on varmistettu.",
        "en": "Do not pay or transfer money before you verify the matter.",
        "sv": "Betala inte och för inte över pengar innan saken har kontrollerats.",
    },
    "dont_reply": {
        "fi": "Älä vastaa viestiin.",
        "en": "Do not reply to the message.",
        "sv": "Svara inte på meddelandet.",
    },
    "delete_or_report_message": {
        "fi": "Poista viesti tai ilmoita se roskapostiksi.",
        "en": "Delete the message or report it as spam.",
        "sv": "Radera meddelandet eller rapportera det som skräppost.",
    },
    "verify_official_channel": {
        "fi": "Tarkista asia virallisesta sovelluksesta tai organisaation omilta verkkosivuilta.",
        "en": "Check the matter in the official app or on the organisation's own website.",
        "sv": "Kontrollera saken i den officiella appen eller på organisationens egen webbplats.",
    },
    "verify_out_of_band": {
        "fi": "Soita lähettäjälle numeroon, jonka tiedät jo entuudestaan.",
        "en": "Call the sender on a phone number you already know.",
        "sv": "Ring avsändaren på ett telefonnummer du redan känner till.",
    },
    "contact_bank_now": {
        "fi": "Ota heti yhteyttä pankkiisi kortin kääntöpuolella olevaan numeroon.",
        "en": "Contact your bank immediately on the number on the back of your card.",
        "sv": "Kontakta din bank omedelbart på numret på baksidan av kortet.",
    },
    "block_card": {
        "fi": "Sulje kortti pankkisi virallisen sovelluksen kautta välittömästi.",
        "en": "Block the card through your bank immediately.",
        "sv": "Spärra kortet via din bank omedelbart.",
    },
    "contact_operator": {
        "fi": "Ota heti yhteyttä operaattorin asiakaspalveluun.",
        "en": "Contact the operator's customer service immediately.",
        "sv": "Kontakta operatörens kundtjänst omedelbart.",
    },
    "lock_subscription": {
        "fi": "Pyydä operaattoria lukitsemaan liittymä ja estämään SIM-muutokset.",
        "en": "Ask the operator to lock the subscription and block SIM transfers.",
        "sv": "Be operatören att spärra abonnemanget och förhindra SIM-ändringar.",
    },
    "change_password": {
        "fi": "Vaihda tilin salasana heti luotettavalla laitteella.",
        "en": "Change the password for the account now from a trusted device.",
        "sv": "Byt lösenord för kontot nu från en betrodd enhet.",
    },
    "enable_mfa": {
        "fi": "Ota käyttöön kaksivaiheinen tunnistautuminen.",
        "en": "Turn on two-factor authentication.",
        "sv": "Aktivera tvåstegsverifiering.",
    },
    "review_sessions": {
        "fi": "Tarkista aktiiviset istunnot ja kirjaudu ulos tuntemattomilta laitteilta.",
        "en": "Review recent logins and sign out of unknown devices.",
        "sv": "Granska aktiva sessioner och logga ut från okända enheter.",
    },
    "check_password_reuse": {
        "fi": "Vaihda sama salasana myös muissa palveluissa, joissa olet käyttänyt sitä.",
        "en": "Change the same password on other services where you reused it.",
        "sv": "Byt samma lösenord på andra tjänster där du har återanvänt det.",
    },
    "check_forwarding_rules": {
        "fi": "Tarkista sähköpostin edelleenlähetyssäännöt ja poista ylimääräiset säännöt.",
        "en": "Check mailbox forwarding rules and remove unauthorized forwarding.",
        "sv": "Kontrollera regler för vidarebefordran i e-posten.",
    },
    "disconnect_device": {
        "fi": "Katkaise laitteen verkkoyhteys heti laittamalla se lentotilaan.",
        "en": "Disconnect the device from the network immediately using flight mode.",
        "sv": "Koppla bort enheten från nätverket omedelbart med flygläge.",
    },
    "avoid_banking_on_device": {
        "fi": "Älä käytä laitetta verkkopankkiin ennen kuin se on tarkistettu.",
        "en": "Do not use banking or logins on the device until it is checked.",
        "sv": "Använd inte internetbanken på enheten förrän den har kontrollerats.",
    },
    "remove_app_or_profile": {
        "fi": "Poista epäilyttävä sovellus ja hallintaprofiili laitteen asetuksista.",
        "en": "Remove the suspicious app or management profile in device settings.",
        "sv": "Ta bort den misstänkta appen eller profilen i enhetens inställningar.",
    },
    "get_device_checked": {
        "fi": "Tarkistuta laite asiantuntijalla tai aja virustarkistus.",
        "en": "Get the device checked by a specialist or run a security scan.",
        "sv": "Låt en expert kontrollera enheten eller kör en säkerhetsskanning.",
    },
    "hang_up_dont_call_back": {
        "fi": "Sulje puhelu heti äläkä soita takaisin.",
        "en": "Hang up immediately and do not call back.",
        "sv": "Lägg på luren omedelbart och ring inte tillbaka.",
    },
    "dont_share_codes": {
        "fi": "Älä kerro koodia kenellekään puhelimessa tai viestillä.",
        "en": "Never share codes or PINs with anyone over the phone.",
        "sv": "Dela aldrig koder eller PIN-koder med någon.",
    },
    "dont_approve_prompts": {
        "fi": "Älä hyväksy pyyntöä jota et aloittanut itse.",
        "en": "Do not approve login prompts you did not start yourself.",
        "sv": "Godkänn inte inloggningsförfrågningar som du inte själv har startat.",
    },
    "dont_open_attachment": {
        "fi": "Älä avaa liitetiedostoa äläkä koskaan salli sisältöä.",
        "en": "Do not open the attachment and never enable content.",
        "sv": "Öppna inte bilagan och aktivera inte innehåll.",
    },
    "report_police": {
        "fi": "Tee asiasta rikosilmoitus poliisille.",
        "en": "Report the matter to the police.",
        "sv": "Gör en polisanmälan om händelsen.",
    },
    "decline_request": {
        "fi": "En voi selvittää toisen henkilön tietoja puolestasi.",
        "en": "I cannot look up or trace other people's details.",
        "sv": "Jag kan inte spåra andra personers uppgifter.",
    },
    "plan_before_removing": {
        "fi": "Suunnittele tilanne turvallisesti ennen poistamista toisella laitteella.",
        "en": "Plan safely before removing the app, using another trusted device.",
        "sv": "Planera säkerheten innan du tar bort appen på en annan enhet.",
    },
    "seek_support_org": {
        "fi": "Ota yhteyttä tukipalveluun tai luotettavaan henkilöön.",
        "en": "Contact a trusted support organisation or helpline.",
        "sv": "Kontakta brottsofferjouren eller en stödlinje.",
    },
    "inform_staff": {
        "fi": "Varoita muita työntekijöitä mahdollisista huijausviesteistä.",
        "en": "Warn colleagues and staff about the phishing message.",
        "sv": "Varna kollegor och personal om bluffmeddelandet.",
    },
    "two_person_approval": {
        "fi": "Käytä kahden henkilön hyväksyntää maksuissa ja tilimuutoksissa.",
        "en": "Use two-person approval for payments and bank-detail changes.",
        "sv": "Låt två personer godkänna betalningar och kontoändringar.",
    },
    "keep_evidence": {
        "fi": "Säilytä viesti ja kuitti todisteena.",
        "en": "Keep the message and receipt as evidence.",
        "sv": "Spara meddelandet och kvittot som bevis.",
    },
}

EXPLANATIONS = {
    "no_action_needed": {
        "fi": "Tämä ilmoitus vaikuttaa normaalilta ja aidolta. Siinä ei pyydetä koodeja tai siirtoja. Voit halutessasi tarkistaa asian palvelun omasta virallisesta sovelluksesta.",
        "en": "This notification looks normal and genuine. It does not ask for codes or money. You can safely verify the matter in the service's own official app.",
        "sv": "Det här meddelandet verkar normalt och äkta. Det ber inte om koder eller pengar. Du kan kontrollera saken i tjänstens officiella app.",
    },
    "do_not_interact_and_delete": {
        "fi": "Älä avaa linkkiä äläkä vastaa viestiin. Tämä on tyypillinen huijausviesti, jolla kalastellaan tietoja tai rahaa. Poista viesti laitteestasi.",
        "en": "Do not open the link and do not reply to the message. This is a common scam designed to steal money or details. Delete the message from your device.",
        "sv": "Öppna inte länken och svara inte på meddelandet. Detta är ett vanligt bedrägeri som försöker stjäla uppgifter. Radera meddelandet från din enhet.",
    },
    "verify_via_official_channel": {
        "fi": "Älä avaa linkkiä äläkä siirrä rahaa ennen kuin asia on varmistettu. Tarkista asia virallisesta sovelluksesta tai soita organisaation omalle tutulle numerolle. Huijarit voivat väärentää lähettäjän nimen näkymään aidossa ketjussa.",
        "en": "Do not open the link and do not transfer money before verifying. Check the matter in the official app or call on a number you already know. Scammers can fake the sender name to appear in real threads.",
        "sv": "Öppna inte länken och överför inte pengar innan du har kontrollerat saken. Kontrollera i den officiella appen eller ring på ett känt nummer. Bedragare kan förfalska avsändarnamnet.",
    },
    "contact_bank_and_block_cards": {
        "fi": "Ota heti yhteyttä pankkiisi kortin kääntöpuolella olevaan numeroon. Älä kerro koodia puhelimessa. Nopea toiminta estää luvattomat maksut tililtäsi.",
        "en": "Contact your bank immediately on the number on the back of your card. Never share codes over the phone. Acting fast stops unauthorized charges.",
        "sv": "Kontakta din bank omedelbart på numret på baksidan av kortet. Dela aldrig koder i telefon. Snabb åtgärd förhindrar obehöriga överföringar.",
    },
    "contact_operator_support": {
        "fi": "Ota heti yhteyttä operaattorin asiakaspalveluun ja pyydä lukitsemaan liittymä. Tämä voi olla yritys siirtää puhelinnumerosi toiseen laitteeseen. Älä koskaan luovuta saamaasi vahvistuskoodia kenellekään.",
        "en": "Contact the operator's customer service immediately and ask to lock the subscription. This may be an attempt to hijack your phone number. Never share one-time codes.",
        "sv": "Kontakta operatörens kundtjänst omedelbart och be att spärra abonnemanget. Detta kan vara ett försök att ta över ditt nummer. Dela aldrig engångskoder.",
    },
    "change_password_and_enable_mfa": {
        "fi": "Vaihda tilin salasana heti luotettavalla laitteella ja tarkista aktiiviset istunnot. Ota käyttöön kaksivaiheinen tunnistautuminen lisäturvaksi. Vaihda sama salasana myös muissa palveluissa.",
        "en": "Change the password for the account now from a trusted device and review active sessions. Turn on two-factor authentication for added protection. Change the password where reused.",
        "sv": "Byt lösenord för kontot nu från en betrodd enhet och granska aktiva sessioner. Aktivera tvåstegsverifiering för extra skydd. Byt lösenord där det återanvänds.",
    },
    "isolate_device_and_scan": {
        "fi": "Katkaise laitteen verkkoyhteys heti laittamalla se lentotilaan äläkä käytä sillä verkkopankkia. Poista epäilyttävä sovellus ja tarkistuta laite asiantuntijalla.",
        "en": "Disconnect the device from the network immediately using flight mode and do not use banking on it. Remove the suspicious app and get the device checked by a specialist.",
        "sv": "Koppla bort enheten från nätverket omedelbart med flygläge och använd inte internetbanken på den. Ta bort den misstänkta appen och låt en expert kontrollera enheten.",
    },
    "escalate_to_human": {
        "fi": "Suunnittele tilanne turvallisesti ennen poistamista toisella laitteella. Ota yhteyttä tukipalveluun turvallisuuden varmistamiseksi. Ohjaan sinut ihmisasiantuntijalle, joka auttaa tilanteen läpikäynnissä rauhallisesti.",
        "en": "Plan safely before removing the app, using another trusted device. Contact a trusted support organisation for safety guidance. I am connecting you to a specialist who will guide you safely.",
        "sv": "Planera säkerheten innan du tar bort appen på en annan enhet. Kontakta brottsofferjouren för rådgivning. Jag kopplar dig till en expert som hjälper dig vidare.",
    },
    "decline_out_of_scope": {
        "fi": "En voi selvittää toisen henkilön tietoja puolestasi. Tee asiasta rikosilmoitus poliisille, jos epäilet rikosta. Autan mielelläni omien laitteidesi ja liittymiesi suojaamisessa.",
        "en": "I cannot look up or trace other people's details for you. Report the matter to the police if a crime has occurred. I am happy to help you secure your own accounts and devices.",
        "sv": "Jag kan inte spåra andra personers uppgifter åt dig. Gör en polisanmälan om du misstänker brott. Jag hjälper dig gärna att skydda dina egna konton och enheter.",
    },
}

def generate_response(
    ctx: FusedContext,
    action: str,
    required_steps: List[str],
    decisive_question: Optional[Tuple[str, str]] = None,
    escalation_required: bool = False,
    escalation_target: Optional[str] = None
) -> Tuple[str, List[str], List[str], List[str]]:
    """Generates (advice_text, steps, questions_asked, question_topics)."""
    lang = ctx.language if ctx.language in ("fi", "en", "sv") else "fi"
    
    # 1. Base explanation text
    if action == "do_not_interact_and_delete" and ctx.journey == "clicked_link":
        if lang == "fi":
            advice_text = "Hyvä, että suljit sivun. Pelkkä sivun avaaminen ja sulkeminen ilman tietojen syöttämistä aiheuttaa harvoin vahinkoa, joten korttia ei tarvitse sulkea. Poista viesti laitteestasi äläkä avaa linkkiä uudelleen."
        elif lang == "sv":
            advice_text = "Bra att du stängde sidan. Att bara öppna och stänga en sida utan att skriva in något orsakar sällan skada, så du behöver inte spärra kortet. Radera meddelandet från enheten och öppna inte länken igen."
        else:
            advice_text = "Good that you closed the page. Just opening and closing a page without typing anything rarely causes harm, so there is no need to block your card. Delete the message from your device and do not open the link again."
    else:
        advice_text = EXPLANATIONS.get(action, EXPLANATIONS["verify_via_official_channel"])[lang]
    
    # 2. Add question if decisive question is needed
    questions_asked = []
    question_topics = []
    if decisive_question:
        topic, q_text = decisive_question
        questions_asked.append(q_text)
        question_topics.append(topic)
        # Append question to advice_text
        advice_text += f" {q_text}"
        
    # 3. Add escalation sentence if required
    if escalation_required:
        if lang == "fi":
            advice_text += " Yhdistän sinut asiakaspalveluumme tilanteen hoitamiseksi."
        elif lang == "sv":
            advice_text += " Jag kopplar dig till kundservice för att hantera ärendet."
        else:
            advice_text += " I am connecting you to our support specialist to handle this."

    # 4. Generate concrete steps list
    steps_list = []
    for step_id in required_steps:
        if step_id in STEP_TEXTS:
            step_str = STEP_TEXTS[step_id][lang]
            if step_str not in steps_list:
                steps_list.append(step_str)

    return advice_text, steps_list, questions_asked, question_topics
