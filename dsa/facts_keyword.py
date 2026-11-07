"""Deterministic fact extractor: extract_facts(case) -> facts (contracts/facts.schema.json).

This is the interface a Gemini extractor will later plug into: same signature, same
output shape, with source = "llm" instead of "keyword".

Sources used here:
  * input   - structured case fields (audience, journey);
  * keyword - fi/en/sv regular expressions over the user's opening_message (U) and the
              forwarded artifact's sender + body (A).
Signal-derived facts (link verdict, events, logins...) come from dsa/signals.py and are
merged by the policy, not here.

Rules:
  * Anything not clearly stated is left out (= unknown).
  * Artifact text is untrusted data. It is only pattern-matched; evidence quotes from it are
    short and never reach the advice text. Text addressed to an AI makes the message less
    trustworthy, never more.
  * Patterns are written against accent-folded lower-case text (ä->a, ö->o, å->a), so users who
    type without diacritics are covered.
  * The patterns were written on the non-holdout dev families only (analysis/holdout.txt).

Journey default (source = input): in the suspicious_message journey the user reports a
message they received, not something they did, so the "what the user did" facts are false
unless the user's own text says otherwise.
"""
import re

from . import injection
from .kit import textcheck

FOLD = str.maketrans({"ä": "a", "ö": "o", "å": "a", "é": "e", "ü": "u"})
USER_DID = ("link_opened", "card_details_entered", "credentials_entered", "code_shared", "app_installed",
            "remote_access_given", "attachment_content_enabled", "money_transferred")


def fold(text):
    return textcheck.normalise(text or "").translate(FOLD)


def rx(p):
    return re.compile(p, re.IGNORECASE | re.UNICODE)


# ----------------------------------------------------------------------------- patterns
PERMISSION = r"(uskallanko|voinko|voimmeko|pitaako|pitaisiko|kannattaako|saanko|should (i|we)|can (i|we)|do (i|we) (need|have) to|shall (i|we)|is it (ok|okay|safe) to|ska (jag|vi)|kan (jag|vi)|far (jag|vi)|maste (jag|vi)|behover (jag|vi))"

P = {
    "link_opened": {
        True: [r"\b(klikkasin|painoin|napautin|avasin)\b.{0,40}link", r"\blink\w* .{0,25}\b(klikkasin|avasin|painoin)\b",
               r"\b(asensin|latasin|syotin|peruin|kirjauduin)\b.{0,60}\blinki", r"\blinkista\b.{0,40}\b(asensin|latasin|kirjauduin|syotin|peruin)\b",
               r"\bi (clicked|tapped|opened|followed|pressed)\b.{0,40}\blink", r"\b(logged|signed) in (through|via|from|using) .{0,20}link",
               r"\b(from|through|via) a (text |sms |message |email )?link\b", r"\b(oppnade|klickade|tryckte)\b.{0,40}lank",
               r"\b(via|fran) en lank\b", r"\bloggade in via\b"],
        False: [r"\ben (ole )?(avannut|klikannut|painanut)\b", r"\bi (did not|didn't|have not|haven't|never) (open|click|tap)",
                r"\bjag (har inte|klickade inte|oppnade inte)\b"],
    },
    "card_details_entered": {
        True: [r"\b(syotin|annoin|kirjoitin|taytin)\b.{0,30}kort", r"\bmaksoin\b(?!.{0,20}\blasku)",
               r"\bi (paid|entered|typed|gave|put in)\b.{0,30}\b(card|fee|payment|delivery)",
               r"\b(skrev in|angav|fyllde i)\b.{0,25}kort", r"\bjag betalade\b(?! inte)"],
        False: [PERMISSION + r".{0,30}\b(maksaa|maksa|pay|betala|paivittaa|update|uppdatera|lunastaa|claim)",
                r"\ben (ole )?(maksanut|syottanyt)\b", r"\bi (did not|didn't|have not|haven't|never) (pay|enter|type)",
                r"\bjag (har inte|betalade inte)\b"],
    },
    "credentials_entered": {
        True: [r"\b(syotin|annoin|kirjoitin|taytin)\b.{0,30}(tunnu|salasan)", r"\bkirjauduin\b.{0,40}\b(link|sivu)",
               r"\bkirjautui\b.{0,40}(sivu|link)", r"\bantoi\b.{0,30}salasan",
               r"\bi (entered|typed|gave|put in)\b.{0,25}\b(my )?(credentials|password|login|bank (id|codes|credentials)|user ?name)",
               r"\b(logged|signed) in (through|via|with|on|using)\b.{0,40}\b(link|page|site)\b",
               r"\bsigned in with (their|my|his|her) (work )?email\b", r"\bgave\b.{0,30}\bpassword",
               r"\b(skrev in|angav)\b.{0,20}\b(mina )?(koder|uppgifter|losenord)", r"\bloggade in via\b"],
        False: [PERMISSION + r".{0,20}\b(kirjautua|log ?in|sign ?in|logga in)",
                r"\ben (ole )?(kirjautunut|syottanyt|antanut tunnu)", r"\bi (did not|didn't|haven't|never) (log|sign|enter|type)"],
    },
    "code_shared": {
        True: [r"\b(syotin|annoin|luin|kerroin|sanoin|kirjoitin)\b.{0,50}(koodi|tunnuslu|\bpin\b)",
               r"\b(i|and|then) (gave|read( out)?|told|typed( in)?|entered|shared|sent)\b.{0,40}\b(code|pin)\b",
               r"\b(skrev in|lamnade|gav|laste upp)\b.{0,40}kod"],
        False: [r"\ben (antanut|kertonut|lukenut|syottanyt)\b.{0,30}(koodi|tunnuslu)",
                r"\bi (did not|didn't|never|haven't) (give|read|tell|share|type|enter)\b.{0,30}\b(code|pin)",
                r"\b(gav|lamnade|laste) (inte|aldrig)\b.{0,20}kod", r"\bjag har inte (gett|lamnat)\b.{0,20}kod"],
    },
    "app_installed": {
        True: [r"\b(asensin|latasin)\b", r"\bi (installed|downloaded)\b", r"\b(installerade|laddade ner)\b(?! inte)"],
        False: [r"\ben (ole )?(asentanut|ladannut)\b", r"\bi (did not|didn't|haven't|never) (install|download)",
                r"\b(installerade|laddade ner) inte\b"],
    },
    "remote_access_given": {
        True: [r"\bannoin\b.{0,30}\b(ohjata|etana|etayhte|kayttaa)", r"\betana\b", r"\bohjasi\b.{0,20}\b(konetta|tietokonetta|puhelinta)",
               r"\b(controlled|took control of|took over) (my|our|the) (computer|screen|laptop|phone|pc)",
               r"\bi (let|allowed) (him|her|them|the caller)\b.{0,20}\b(connect|control|access|in)\b",
               r"\binstalled a remote\b.{0,40}\bfor (him|her|them)", r"\b(gave|given) (him|her|them|the caller) (remote )?access",
               r"\b(fick|fatt) (styra|komma at)", r"\blat (honom|henne|dem) (styra|ansluta)"],
        False: [r"\ben (antanut|paastanyt|asentanut)\b.{0,40}\b(eta|ohjata|kayttaa)",
                r"\bi (did not|didn't|never|refused to) (let|allow|give|install|connect)",
                r"\b(hung up|ended the call)\b", r"\b(lopetin|katkaisin|suljin) (puhelun|puhelimen)\b", r"\blade (jag )?pa\b",
                PERMISSION + r".{0,40}\b(eta\w*|remote|fjarr\w*)", r"\b(etayhteyden antaminen|giving (them )?(remote )?access)\b.{0,10}\b(ok|okay|turvallista|safe)"],
    },
    "attachment_content_enabled": {
        True: [r"\b(sallin|hyvaksyin|otin kayttoon)\b.{0,30}\b(sisallo|muokkau|makro)", r"\bi (enabled|allowed|clicked enable)\b.{0,20}\b(content|editing|macros)",
               r"\baktiverade\b.{0,20}\b(innehall|redigering|makro)"],
        False: [r"\ben (sallinut|hyvaksynyt)\b.{0,30}\b(sisallo|muokkau|makro)", r"\bi (did not|didn't|haven't|never) (enable|allow)"],
    },
    "money_transferred": {
        True: [r"\b(siirsin|siirsimme|maksoimme|lahetin rahaa)\b", r"\blahetin\b.{0,15}\beuroa\b", r"\bmaksoin laskun\b",
               r"\bi (already )?(moved|transferred|sent|wired)\b.{0,30}\b(money|euros?|funds|savings|some|it)\b",
               r"\b(already|jo) (paid|maksettu|maksoin|maksoimme|sent|lahetetty)\b", r"\b(we|i) (have )?(already )?paid (the|it|this)\b",
               r"\b(forde over|overforde|skickade pengar|vi betalade|jag betalade fakturan)\b"],
        False: [PERMISSION + r".{0,30}\b(maksaa|maksa|siirtaa|lahettaa|pay|transfer|send|betala|fora over|skicka)",
                r"\b(en|emme) (ole )?(viela )?(maksanut|maksaneet|siirtanyt|lahettanyt)\b",
                r"\b(i|we) (have not|haven't|did not|didn't) (yet )?(paid|sent|transferred)", r"\b(not|ei) (yet |viela )?(paid|maksettu)\b"],
        # A question about legitimacy ("is it ok?", "kai kunnossa?") is not evidence that nothing was paid.
    },
    "self_initiated": {
        True: [r"\btilasin (itse|kylla|juuri)", r"\btilasimme itse\b", r"\btiketin tein itse\b",
               r"\bi (ordered|booked|requested)\b.{0,30}\b(myself|just now)\b", r"\bi did order\b", r"\bwe (booked|ordered|requested)\b",
               r"\bkirjaudun juuri\b", r"\bolen ottamassa\b.{0,30}\bkayttoon", r"\bi'?m (logging|signing) in\b", r"\bi am (logging|signing) in\b",
               r"\blisasin\b.{0,30}\b(toimittaja|maksunsaaja)", r"\bi added\b.{0,20}\b(supplier|payee)", r"\blade till\b.{0,25}\b(leverantor|mottagare)",
               r"\bjag har bestallt\b", r"\bbestallde (jag|vi) (sjalv|sjalva)\b",
               r"\b(vaihdoin|vaihdan) (puhelimen|puhelinta|sim)", r"\bi (changed|switched|got a new) (my )?(phone|sim)",
               r"\bolen (matkoilla|ulkomailla)\b", r"\bi'?m (travelling|traveling|abroad)\b", r"\bjag (reser|ar utomlands)\b"],
        # a business user's "I didn't order it" does not exclude a colleague: false only for consumers
        "False_consumer": [r"\ben (ole )?(pyytanyt|tilannut|tehnyt tata|kirjautunut)\b", r"\bvaikka en (pyytanyt|kirjaudu|tilannut)\b",
                           r"\ben ollut mina\b", r"\bi (did not|didn't|never|haven't) (ask|request|order|log ?in|sign ?in|start|make)\b",
                           r"\beven though i('m| am)? not (logging|signing)", r"\bwasn'?t me\b",
                           r"\b(fast|trots att) jag inte (bad|bestallde|loggade)\b", r"\binte jag\b"],
    },
    "password_reused": {
        True: [r"\bkaytan samaa salasana", r"\bsama salasana\b.{0,30}\b(muualla|myos|kaytossa)", r"\bi use the same password",
               r"\bsame password (on|for|everywhere|elsewhere)", r"\bjag anvander samma losenord", r"\bsamma losenord (pa|overallt)"],
        False: [r"\ben kayta samaa salasana", r"\bi (don't|do not|never) (re)?use (the same )?password", r"\bdifferent passwords? (everywhere|for)"],
    },
}

EVENT = {
    "sim_change_event": [r"\besim\w*\b.{0,60}\b(aktivoi\w*|activated|aktiverad\w*|siirr\w*|transferred|moved|uuteen laitteeseen|new (phone|device)|ny (telefon|enhet))",
                         r"\bsim\w*\b.{0,30}\b(vaihdettu|vaihdettiin|swapped|replaced|bytt|aktivoitu|activated)\b",
                         r"\bnumero\w* .{0,20}\bsiirto", r"\bnumber (port|transfer)", r"\bport(ing|ed)? (out|your number)", r"\bnummerflytt"],
    "service_lost": [r"\bkentta (katosi|havisi|lahti|meni)", r"\bkatosi kentta", r"\bei (ole )?kenttaa", r"\b(no|lost( the)?|lost my) (signal|service|network|coverage|reception)\b",
                     r"\bsignal (is )?(gone|lost)", r"\bingen (tackning|signal)", r"\btackningen (forsvann|ar borta)", r"\bpuhelut eivat (toimi|tule)",
                     r"\bcalls? (stopped|don'?t work|not working)"],
    "subscription_order_event": [r"\b(tilausvahvistus\w*|order confirmation|orderbekraftelse|bestallningsbekraftelse)\b.{0,80}(\bliittym\w*|\bsim\w*|laajakaist\w*|\bbroadband|\bsubscriptions?|\babonnemang|\bmobil\w*)",
                                 r"\b(liittym\w*|sim\w*|subscriptions?|abonnemang)\b.{0,40}\b(tilattu|tilannut|ordered|bestallt|bestallda)\b",
                                 r"\btilannut meille\b.{0,25}\b(sim|liittym)", r"\b\d+ (uutta|new|nya) (sim|liittym|subscriptions?|abonnemang)"],
    "unknown_login": [r"\bkirjauduttiin\b", r"\b(kirjautuminen|kirjautui|sisaankirjautumi\w*)\b.{0,40}\b(uudelta laitteelta|ulkomail\w*|tuntemattom\w*|vieraas\w*)",
                      r"\bkirjautuminen \w+(sta|lta)\b", r"\b(logged|signed) in from\b", r"\b(login|sign-?in) (attempt )?from (a )?(new|unknown|another) (device|country|location)",
                      r"\binloggning fran\b", r"\bloggade? in fran\b"],
    "unrequested_mfa_prompts": [r"\b(toistunut|repeated|upprepad\w*) \d+ (kertaa|times|ganger)",
                                r"\b(jatkuvasti|koko ajan|keeps? (getting|coming|sending)|over and over|again and again|hela tiden|om och om igen)\b.{0,60}\b(hyvaksy\w*|kirjautu\w*|approv\w*|prompts?|requests?|notifications?|godkann\w*|inloggning\w*)",
                                r"\b(vaikka en kirjaudu|even though i'?m not (logging|signing) in|fast jag inte loggar in)"],
    "account_misuse_signs": [r"\bedelleenlahetyssaan\w*", r"\bforwarding rule", r"\b(inbox|mail|mailbox) rule", r"\bvidarebefordr\w*",
                             r"\b(viela|yha|edelleen) kirjautunee\w*", r"\bstill (logged|signed) in\b", r"\bpaasee (yha|viela|edelleen)\b",
                             r"\bstill has access\b", r"\bhar fortfarande (atkomst|tillgang)"],
    "account_used_against_others": [r"\basiakk\w*\b.{0,40}\b(saaneet|saivat|kysyi\w*)\b.{0,60}lasku", r"\bvalelasku\w*",
                                    r"\bcustomers?\b.{0,40}\b(received|got|asked)\b.{0,60}\binvoices?", r"\bfake invoices?\b",
                                    r"\bkunder\w*\b.{0,40}\b(fatt|fick)\b.{0,40}faktur"],
    "former_staff_access": [r"\b(lahtenyt|entinen|irtisanottu|lopettanut) tyontekija", r"\bformer (employee|staff|colleague)",
                            r"\b(employee|colleague|worker) who (left|quit)", r"\bex-?employee", r"\b(tidigare|fore detta) anstalld", r"\banstalld som slutat"],
    "device_compromise_signs": [r"\b(files|tiedosto\w*|filer\w*)\b.{0,30}\b(encrypted|salattu|salattiin|krypterade?)\b",
                                r"\b(encrypted|salasi|krypterade?)\b.{0,20}\b(files|tiedosto\w*|filer\w*)", r"\b(lunnas\w*|ransom\w*|bitcoin\w*|btc)\b",
                                r"\btiedostot eivat aukea",
                                r"\bfiles (won'?t|will not|don'?t|do not) open", r"\bfilerna gar inte att oppna", r"\b(kayttaytyy|toimii) oudosti",
                                r"\b(acts|behaves|is acting|is behaving) (strangely|weird|oddly)", r"\bbeter sig konstigt", r"\bponnahdusikkun\w*",
                                r"\bpop-?ups?\b"],
    "monitoring_suspected": [r"\bex\b(?!-?(employee|tyontekija|anstalld))", r"\bexa(ni|lla|ltani)?\b", r"\bentinen (kumppani|puoliso|mies|vaimo|poikaystava|tyttoystava)",
                             r"\bex-?(partner|boyfriend|girlfriend|husband|wife)", r"\bformer partner", r"\bmin (fore detta|f\.d\.)",
                             r"\bseurantasovellu\w*", r"\bvakoilu\w*", r"\bstalkerware|\bspyware|\btracking app|\bspionapp\w*|\bovervakning\w*",
                             r"\b(tietaa|tuntuu tietavan|knows?|seems to know|vet)\b.{0,30}\b(mita kirjoitan|missa olen|what i (write|type|say)|where i (am|go)|vad jag skriver|var jag ar)"],
    "out_of_scope_request": [r"\b(selvit\w*|etsi|kerro|find out|tell me|look up|trace|track down|identify|jaljit\w*|ta reda pa|spara)\b.{0,40}\b(kuka omistaa|kenen numero|who owns|whose number|osoite|address|nimi|name|identity|henkilollisyy\w*|vem som ager|identitet)",
                             r"\b(julkaista|publish|post|expose|paljastaa|publicera|hanga ut)\b.{0,30}\b(nimen\w*|name|identity|henkilollisyy\w*|namn)",
                             r"\bhack (them|back|him|her)\b"],
    "verified_out_of_band": [r"\bsoitin\b.{0,80}\b(numeroon|sopimukse\w*|tuttuun|tunnettuun)", r"\b(vahvisti|vahvistivat) (muutoksen|asian)",
                             r"\btarkistin\b.{0,60}\bsoittamalla", r"\bi (called|phoned|rang)\b.{0,60}\b(number (in|on|from) (our|the) (contract|agreement|records)|known number|usual number)",
                             r"\b(she|he|they) confirmed the change", r"\bringde\b.{0,60}\b(avtal\w*|kant nummer|kanda nummer)", r"\bbekraftade (andringen|bytet)",
                             r"\bour usual it partner", r"\b(tavallinen|oma|meidan) it-kumppani", r"\bit-kumppani(mme|ltamme)\b", r"\btiketin tein itse",
                             r"\bwe booked remote support"],
}
SAFETY = {True: [r"\b(pelkaan|uhkaili\w*|uhkaa\w*)\b", r"\bi'?m (afraid|scared) of (him|her|them)\b", r"\bthreaten\w*", r"\bhurt me\b",
                 r"\bradd for (honom|henne|dem)\b", r"\bhota(r|de)\b"],
          False: [r"\bolen turvassa\b", r"\bi'?m safe\b", r"\bi am safe\b", r"\bjag ar trygg\b"]}

SENDER = [  # priority order
    ("tax_authority", r"\bvero(toimisto|hallinto|palautu\w*|virasto)|\bveronpalautu\w*|\btax (refund|office|authority|administration|agency)|\bskatte(verket|byran|aterbaring)"),
    ("police", r"\bpoliisi\w*|\bpolice\b|\bpolis(en)?\b"),
    ("family_or_friend", r"\b(aiti|isa|mummi|mummo|ukki|isoaiti|mom|mum|dad|mother|father|grandma|grandpa|mamma|pappa|farmor|mormor|morfar|farfar)\b|\b(uusi|new|nytt) (numero|number|nummer)\b|\b(poika|tytar|lapsi)(si|ni)\b|\byour (son|daughter|child)\b|\bmin (son|dotter)\b|\bpuhelin\w* (hajosi|meni rikki)|\bphone (broke|is broken)|\btelefonen (gick sonder|ar trasig)"),
    ("executive", r"\btoimitusjohtaja\w*|\bceo\b|\bpomo\w*|\bboss\b|\bmanaging director\b|\bvd\b|\bchefen\b|\bjohtaja\w*"),
    ("operator", r"\boperaattori\w*|\boperator\w*|\bliittym\w*|\b(phone|mobile) subscription|\babonnemang\w*|\bteidan asiakaspalvelu\w*|\byour customer service|\bsim[- ]?(paivity\w*|upgrade|uppgradering|kortti|card)|\boma-(tili|palvelu)"),
    ("prize_sender", r"\bvoit(it|tanut|taja|inko)\w*|\bpalkin\w*|\blahjakort\w*|\bonnittelu\w*|\bprize|\b(you('ve| have)|i) won\b|\bwinner|\bgift card|\bvinst\w*|\bvunnit|\bpresentkort"),
    ("investment_promoter", r"\bsijoit\w*|\binvest\w*|\bkrypto\w*|\bcrypto\w*|\bkaupankay\w*|\btrading\b|\bplacer\w*|\bavkastning|\btuotto\w*"),
    ("supplier", r"\btoimittaj\w*|\bsupplier\w*|\bleverantor\w*|\bvendor\w*"),
    ("delivery_company", r"\bpaketti\w*|\bpaket\w*|\bparcel\w*|\bdelivery (pending|company)|\bshipment|\blahetys\w*|\bkuriiri\w*|\btulli\w*|\bcustoms\b|\bnoutopiste\w*|\bpickup point|\butlamningsstallet"),
    ("it_support", r"\bit-(tuki|kumppani)\w*|\bit (support|partner)|\btietoturvatu\w*|\bsecurity support|\btech(nical)? support|\btekni(nen|sen) tu\w*|\bmicrosoft\b|\bvirus\w*|\bteknisk support"),
    ("payment_provider", r"\bmaksupaate\w*|\bkassapaate\w*|\bpayment terminal|\bcard terminal|\bbetalterminal\w*|\bkortterminal\w*|\bpayment provider"),
    ("bank", r"pankk|pankin\b|\bbank\w*"),
    ("online_service", r"\b(tilauksesi|subscription|prenumeration|jasenyy\w*|membership|suoratoisto\w*|streaming)\b"),
]
SENDER = [(k, rx(p)) for k, p in SENDER]

LURE = [  # priority order; "needs_link" lures only count when the artifact carries a link
    ("remote_access", False, r"\betatu\w*|\betayhte\w*|\betaohjelm\w*|\bremote (support|access|desktop|control|program|session)|\bfjarr\w*|\bscreen ?shar\w*|\bnaytonjak\w*|\bohjata (tietokonetta|konetta|puhelinta)|\bcontrol (my|your) (computer|screen)|\banydesk|\bteamviewer|\bquick ?support"),
    ("app_install", False, r"\basenna\w*|\basentamalla|\binstall\w*|\.apk\b|\blataa (sovellus|ohjelma)|\bdownload (the |our )?app|\bladda ner (appen|programmet)"),
    ("money_transfer", False, r"\b(siirra|siirtamaan|siirtaa|siirtamalla)\b.{0,40}\b(rahat|rahaa|saast\w*|varat|tilille|turvatili\w*)|\bturvatili\w*|\bsafe account|\bsakert konto|\b(move|transfer|wire|send)\b.{0,30}\b(money|savings|funds|euros?)\b|\bpay\b.{0,40}\bto a new (partner|account|recipient)|\bmaksa\w*\b.{0,40}\buudelle (yhteistyo)?kumppanille|\b(laheta|lahettaa|lahettamaan) (minulle )?rahaa|\bsend me (some )?money|\b(skicka|fora over|for over)\b.{0,20}\b(pengar|beloppet)|\b(lainaa|lend me|borrow)\b|\b(voisitko|voitko|could you|can you|kan du)\b.{0,30}\b(maksaa|pay|betala)\b.{0,30}\b(laskun|lasku|a bill|the bill|en faktura|rakningen)\b|\bi need you to pay\b|\btarvitsen etta maksat\b"),
    ("bank_detail_change", False, r"\btilinumero\w*\b.{0,40}\b(vaihtu\w*|muuttu\w*|uusi|on nyt)|\buusi tilinumero|\buudelle tilille|\bpankki(mme|yhteys)\b.{0,20}\b(vaihtu\w*|muuttu\w*)|\bnew (bank )?account( number)?\b|\b(bank|account) (details )?(has |have )?changed|\bour bank (has )?change|\bbank changes\b|\bnytt kontonummer|\bnya kontot|\bbyt(t|er) bank|\biban\b|\bfi\d{2}( ?\d{4}){3}"),
    ("one_time_code", False, r"(koodi|tunnuslu)\w*\b.{0,40}\b(lue|lukea|kerro|kertoa|anna|antaa|luettava|sano|syota)\b|\b(lue|lukea|kerro|kertoa|anna|antaa|pyysi|halusi|kysyi|kysyivat|pyysivat)\b.{0,40}(koodi|tunnuslu)|\b(read|tell|give|share|send|asked for|wanted|confirm)\b.{0,30}\b(codes?|pins?)\b|\b(codes?|pins?)\b.{0,40}\b(read (it |them )?(back|out)|to (him|her|them))|\b(las upp|lasa upp|ge|lamna|ville ha|bad om)\b.{0,30}kod|\bkod\w*\b.{0,40}\b(las|lasa|laste) (upp|den|dem)\b"),
    ("investment", False, r"\bsijoit\w*|\binvest\w*|\bkrypto\w*|\bcrypto\w*|\btuotto\w*|\b(guaranteed|taattu|garanterad) (return|tuotto|avkastning)|\bplacera\w*|\bavkastning|\btrading\b|\bkaupankayntialusta"),
    ("open_attachment", False, r"\bliitteena|\bliite\w*|\battach\w*|\bbilaga\w*|\.(zip|docm|xlsm|exe|iso|rar)\b|\bzip-tiedosto"),
    ("bank_credentials", True, r"\b(pankkitunnu\w*|verkkopankkitunnu\w*|tunnistaudu\w*|tunnistautu\w*|vahvista henkilollisyyte\w*|vahvista tietosi|henkilollisyy\w*|bank (credentials|codes|id|login)|bankkod\w*|bank-?id|identif(y|ication)|verify your identity|confirm (your )?(details|identity|information)|bekrafta (din )?(identitet|uppgifter)|identifiera dig|tunnuksiisi|tunnistautumisesi)\b|\bverkkopankki\w*\b.{0,30}\bsuljettu|\bonline banking\b.{0,20}\b(locked|closed|suspended)"),
    ("account_password", True, r"\b(kirjaudu\w*|kirjautumalla|log ?in|logging in|sign ?in|logga in|salasan\w*|password|losenord|reset|nollaa|aterstall\w*|suojaa tilisi|secure your account)\b"),
    ("card_details", False, r"\bkorttitie\w*|\bcard (details|number|information)|\bkortuppgift\w*|\bupdate (your )?(card|payment)|\bpaivita (kortti|maksu)\w*|\buppdatera (kortet|betalning)"),
]
LURE = [(k, needs_link, rx(p)) for k, needs_link, p in LURE]
MONEY_LURE = next(p for k, _, p in LURE if k == "money_transfer")
# No forwarded message: the user reports, in their own words, that someone asks them for an amount of money
# ("he needs 300 euros", "tarvitsee 300 euroa", "behover 300 euro"). Written for the phone demo's chat mode;
# no dev case lacks an artifact, so this pattern is not tuned on (or scored by) any dev family.
MONEY_ASK = rx(r"\b(needs?|wants?|asks? for|asking for|asked for|tarvitse\w*|tarvits\w*|pyyta\w*|pyysi|halua\w*"
               r"|behover|behovde|vill ha|ber om|bad om)\b.{0,20}?\d[\d ,.]*\s?(€|eur\w*)")
PAY_VERB = rx(r"\bmaksa\b|\bmaksamalla\b|\bmaksaa\b|\bpay\b|\bbetala\b")
FEE = rx(r"\b(toimitusmaksu|kasittelymaksu|tullimaksu|delivery fee|handling fee|customs fee|avgift)\w*")
AMOUNT = rx(r"(\d[\d ]*[,.]?\d*) ?(€|eur\b|euro)")
NO_ASK = rx(r"\b(ei (kysynyt|pyytanyt) mitaan|eivat (kysyneet|pyytaneet) mitaan|asked (for )?(nothing|no details)|asked for no details|didn'?t ask for anything|bad inte om (nagot|nagra)|fragade inte efter)")
THREAT = rx(r"\b\d+ (tunnin|hours?|timmar|h)\b|\b(heti|valittomasti|immediately|suljetaan|katkaistaan|locked|suspended|vanhenee|expires?|expiring|palautetaan|spärras|sparras|stangs)\b|\bon suljettu\b")
LINK = rx(r"https?://|www\.")
# The user says they were expecting this contact (positive evidence for appears_genuine; user text only).
EXPECTED = rx(r"\b(odotin|odotimme|odotinkin|odotan|odotamme)\b|\b(i|we) (was|were|am|are|have been) (expecting|waiting for)\b"
              r"|\b(jag|vi) (vantade|vantar) pa\b")
BREACH = rx(r"\b(tietomurto\w*|tietovuo\w*|vuot\w*|data (breach|leak)|breach\w*|leak\w*|dataintrang|lack\w*)\b")
CALL_WORDS = rx(r"\b(soitti|soitettiin|soittaja\w*|puhelu\w*|called|caller|phone call|ringde|samtal\w*|uppringare\w*)\b")
CRED_TYPE = [("work_account", rx(r"tyosahkopost|tyotunnu|work (email|account)|microsoft 365|office 365|\bm365\b|arbetsmejl|jobbmejl")),
             ("bank", rx(r"pankk|\bbank|bankkod")),
             ("email", rx(r"sahkopost|\bemail\b|e-mail|\bmejl|e-post")),
             ("national_id", rx(r"henkilollisyy|identity|identitet"))]


def _compile_group(g):
    return {k: [rx(p) for p in v] for k, v in g.items()}


P = {fact: _compile_group(g) for fact, g in P.items()}
EVENT = {fact: [rx(p) for p in v] for fact, v in EVENT.items()}
SAFETY = _compile_group(SAFETY)


def _first(pats, text):
    for p in pats:
        m = p.search(text)
        if m:
            return m
    return None


def _kw(value, evidence):
    return {"value": value, "source": "keyword", "evidence": injection.quote(evidence, 120) or "keyword match"}


def _input(value, evidence):
    return {"value": value, "source": "input", "evidence": evidence}


def _amounts(text):
    out = []
    for m in AMOUNT.finditer(text):
        try:
            out.append(float(m.group(1).replace(" ", "").replace(",", ".")))
        except ValueError:
            pass
    return out


BREACH_PASSWORD = rx(r"salasan|password|losenord|tunnuks|credentials|inloggningsuppgift")
BREACH_FINANCIAL = rx(r"\bkortti|\bcard\b|kortnummer|kortuppgift|\biban\b|tilinumero|maksutie|payment data|betalningsuppgift")
BREACH_EMAIL = rx(r"sahkoposti|e-?mail|\bmejl|e-post")
NEGATION = rx(r"\b(no|not|none|never|ei|eika|eivat|ilman|inga|inte|ingen|aldrig)\b|n't\b")
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def breach_kind(text):
    """What a breach notice says was exposed: password / financial / email_only / other.
    A sentence that negates a data type ("No passwords were affected", "Salasanoja ei vuotanut") does not
    count as that type being exposed. Read from the notice itself; the user's text only when nothing was
    forwarded (a user asking "do I need to change my passwords?" is not saying a password leaked)."""
    found = set()
    for sent in SENTENCE.split(text or ""):
        if NEGATION.search(sent) or sent.rstrip().endswith("?"):
            continue
        if BREACH_PASSWORD.search(sent):
            found.add("password")
        if BREACH_FINANCIAL.search(sent):
            found.add("financial")
        if BREACH_EMAIL.search(sent):
            found.add("email")
    if "password" in found:
        return "password"
    if "financial" in found:
        return "financial"
    return "email_only" if "email" in found else "other"


def extract_facts(case):
    """case (test-input fields only) -> facts dict (facts.schema.json, sources input/keyword)."""
    facts = {
        "audience": _input(case["audience"], "case.audience"),
        "journey": _input(case["journey"], "case.journey"),
    }
    art = (case.get("signals") or {}).get("artifact") or {}
    U = fold(case.get("opening_message"))
    A_sender = fold(art.get("sender"))
    A_body = fold(art.get("body"))
    A = A_sender + "\n" + A_body
    is_call = art.get("type") == "call" or bool(CALL_WORDS.search(U)) and art.get("type") in (None, "user_report")
    has_link = bool(art.get("links")) or bool(LINK.search(art.get("body") or ""))
    audience = case["audience"]

    # --- what the user says they did (user text only) ---------------------------------
    for fact, groups in P.items():
        m = _first(groups.get(True, []), U)
        if m:
            facts[fact] = _kw(True, m.group(0))
            continue
        neg = groups.get(False, []) + (groups.get("False_consumer", []) if audience == "consumer" else [])
        m = _first(neg, U)
        if m:
            facts[fact] = _kw(False, m.group(0))

    # --- events and situations described in user text or the notice ---------------------
    for fact, pats in EVENT.items():
        scope = U if fact in ("monitoring_suspected", "out_of_scope_request", "verified_out_of_band") else U + "\n" + A
        m = _first(pats, scope)
        if m:
            facts[fact] = _kw(True, m.group(0))
    m = _first(SAFETY[True], U)
    if m:
        facts["user_safety_concern"] = _kw(True, m.group(0))
    else:
        m = _first(SAFETY[False], U)
        if m:
            facts["user_safety_concern"] = _kw(False, m.group(0))

    # --- contact channel when there is no forwarded artifact ----------------------------
    if art.get("type") in (None, "user_report") and CALL_WORDS.search(U):
        facts["contact_channel"] = _kw("call", CALL_WORDS.search(U).group(0))

    # --- injection ------------------------------------------------------------------------
    hits = injection.detect(injection.artifact_text(case))
    facts["ai_instruction_in_content"] = _kw(bool(hits), hits[0]["match"] if hits else "no text addressed to an AI assistant")

    # --- claimed sender: artifact sender line, then body, then user text ---------------------
    for scope in (A_sender, A_body, U):
        hit = next(((k, m) for k, p in SENDER if (m := p.search(scope))), None)
        if hit:
            facts["claimed_sender"] = _kw(hit[0], hit[1].group(0))
            break

    # --- lure: what the message / caller asks for (artifact, plus user text for calls) -----------
    scope = A + ("\n" + U if is_call or art.get("type") == "user_report" else "")
    lure = None
    for kind, needs_link, p in LURE:
        if needs_link and not has_link:
            continue
        m = p.search(scope)
        if m:
            lure = (kind, m.group(0))
            break
    if lure is None and PAY_VERB.search(A) and (FEE.search(A) or _amounts(A)) and has_link:
        # a named fee is a small payment; otherwise a large amount to pay is a money transfer
        amts = [] if FEE.search(A) else _amounts(A)
        lure = ("money_transfer" if amts and max(amts) >= 200 else "small_payment", PAY_VERB.search(A).group(0))
    if lure is None and not art:
        # nothing forwarded: a money request the user describes is still the lure (same fact as the call path)
        m = MONEY_LURE.search(U) or MONEY_ASK.search(U)
        if m:
            lure = ("money_transfer", m.group(0))
    if art.get("type") == "user_report" and not is_call:
        lure = ("none", "no message was forwarded; the user describes what happened")
    threat = THREAT.search(A)
    if lure is None and (NO_ASK.search(scope) or not threat):
        m = NO_ASK.search(scope)
        lure = ("none", m.group(0) if m else "no request for details, codes or payment found")
    if lure:
        facts["lure_ask"] = _kw(*lure)
    lure_v = lure[0] if lure else "unknown"

    # a request to pay invoices to a new account comes from a (claimed) supplier or payee
    if lure_v == "bank_detail_change" and facts.get("claimed_sender", {}).get("value") not in ("executive", "family_or_friend", "supplier"):
        facts["claimed_sender"] = _kw("supplier", "request to pay invoices to a new account")

    # --- credential type -------------------------------------------------------------------------
    if facts.get("credentials_entered", {}).get("value") is True or lure_v in ("bank_credentials", "id_credentials", "account_password"):
        for kind, p in CRED_TYPE:
            m = p.search(U) or p.search(A)
            if m:
                facts["credential_type"] = _kw(kind, m.group(0))
                break

    # --- breach notice ------------------------------------------------------------------------
    b = BREACH.search(A) or BREACH.search(U)
    if b:
        val = breach_kind(A_body if A_body.strip() else U)
        facts["breach_exposed_data"] = _kw(val, b.group(0))
        if has_link and lure_v in ("account_password", "bank_credentials", "id_credentials"):
            facts["breach_notice_genuine"] = _kw(False, "notice asks to log in through its link")
        elif not has_link and not hits:
            facts["breach_notice_genuine"] = _kw(True, "notice names the service and has no login link")

    # --- appears genuine (text only; the policy also folds in the link verdict) -----------------------
    if hits:
        facts["appears_genuine"] = _kw(False, "text addressed to an AI assistant")
    elif lure_v not in ("none", "unknown"):
        facts["appears_genuine"] = _kw(False, "asks for: %s" % lure_v)
    elif lure_v == "none" and not threat and not has_link and art.get("type") != "user_report" and EXPECTED.search(U):
        # Fail-closed: finding no lure is NOT evidence that a message is genuine. Only positive evidence sets
        # appears_genuine = true: here, the user saying they expected it (the policy adds a clean link check;
        # self_initiated and verified_out_of_band are separate facts). Otherwise it stays unknown.
        facts["appears_genuine"] = _kw(True, "expected: " + EXPECTED.search(U).group(0))

    # --- journey default: a received message, no action reported ------------------------------------
    if case["journey"] == "suspicious_message":
        for fact in USER_DID:
            facts.setdefault(fact, _input(False, "case.journey == suspicious_message: a received message, no action reported"))
    elif case["journey"] == "clicked_link" and has_link and "link_opened" not in facts:
        facts["link_opened"] = _input(True, "case.journey == clicked_link and the message carries a link")
    if is_call and "contact_channel" not in facts and art.get("type") != "call":
        facts["contact_channel"] = _kw("call", "the user describes a call")
    return facts
