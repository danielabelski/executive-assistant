"""Phrasebank data — ~1,220 curated phrases/words, one tuple per row.

WHY THIS FILE EXISTS
---------------------
An executive assistant says 80% boilerplate ("Good morning", "3 unread",
"rain expected — bring an umbrella"). Generating that with an LLM every
time burns tokens, latency, and money for zero added intelligence. So the
boilerplate lives HERE as data; the LLM is reserved for genuine judgment
(ranking priorities, drafting sensitive replies) — see composer.py.

ROW FORMAT: (category, text, tone)
    text may contain {slots} filled at render time: {name} {count} {temp}
    {unit} {chance} {cond} {title} {sender} {subject} {source} {reason}
    {time} {city}
TONE: warm | neutral | formal | brief | playful — lets the assistant match
register to context without another LLM call.

CURATION RULE: every entry must be something a real PA would plausibly say.
No filler, no near-duplicates that differ only by punctuation.
"""

# fmt: off
# ---------------------------------------------------------------- greetings
GREETING_MORNING = [
    ("Good morning{name}!", "warm"), ("Good morning{name}! Ready when you are.", "warm"),
    ("Morning{name}!", "brief"), ("Morning{name}! Coffee's on the day.", "playful"),
    ("Rise and shine{name}!", "playful"), ("Hello{name} — good morning.", "neutral"),
    ("Good morning{name}. Here's your day at a glance.", "formal"),
    ("Morning{name}! Let's make today count.", "warm"),
    ("A very good morning to you{name}.", "formal"),
    ("Hey{name}! Fresh day, fresh start.", "playful"),
    ("Good morning{name}! Hope you slept well.", "warm"),
    ("Morning{name}! Your briefing is ready.", "neutral"),
    ("Top of the morning{name}!", "playful"),
    ("Good morning{name}! One page, whole day.", "neutral"),
    ("Morning{name}! Here's what matters today.", "neutral"),
    ("Good morning{name}. The day, organized.", "formal"),
    ("Sun's up{name} — briefing below.", "playful"),
    ("Good morning{name}! Here's the rundown.", "neutral"),
    ("Morning{name}! Straight to it:", "brief"),
    ("Good morning{name}! Your day, distilled.", "warm"),
]
GREETING_EVENING = [
    ("Good evening{name}!", "warm"), ("Evening{name}!", "brief"),
    ("Good evening{name} — let's close out the day.", "neutral"),
    ("Evening{name}! Time to wrap up.", "playful"),
    ("Good evening{name}. Here's how today went.", "formal"),
    ("Winding down{name}? Here's your wrap-up.", "warm"),
    ("Evening{name}! Day complete — summary below.", "neutral"),
    ("Good evening{name}! Let's review and reset for tomorrow.", "warm"),
    ("Evening{name}. The day in review.", "formal"),
    ("Hey{name} — evening check-in.", "playful"),
    ("Good evening{name}! Putting today to bed.", "warm"),
    ("Evening{name}! Your end-of-day report.", "neutral"),
]
SECTION_HEADER = [
    # calendar
    ("📅 Today's schedule", "neutral"), ("📅 On the calendar", "warm"),
    ("📅 Your appointments", "formal"), ("📅 Today", "brief"), ("📅 What's on", "playful"),
    # email
    ("📧 Unread email", "neutral"), ("📧 Inbox check", "warm"),
    ("📧 Messages awaiting you", "formal"), ("📧 Inbox", "brief"), ("📧 Who's knocking", "playful"),
    # tasks
    ("✅ Tasks", "neutral"), ("✅ Your to-do list", "warm"),
    ("✅ Action items", "formal"), ("✅ To do", "brief"), ("✅ The list", "playful"),
    # weather
    ("🌦 Weather", "neutral"), ("🌦 Outside your window", "warm"),
    ("🌦 Forecast", "formal"), ("🌦 Sky report", "playful"), ("🌦 What to wear for", "brief"),
    # github
    ("🐙 GitHub", "neutral"), ("🐙 Repo watch", "warm"),
    ("🐙 Repository activity", "formal"), ("🐙 Code", "brief"), ("🐙 Octocat report", "playful"),
    # evening: done
    ("✔ Accomplished today", "neutral"), ("✔ Done and dusted", "playful"),
    ("✔ Completed", "formal"), ("✔ Wins today", "warm"), ("✔ Checked off", "brief"),
    # evening: open
    ("◌ Still open", "neutral"), ("◌ Carried forward", "warm"),
    ("◌ Outstanding items", "formal"), ("◌ Remaining", "brief"), ("◌ On tomorrow's plate", "playful"),
    # evening: priorities
    ("🎯 Tomorrow's focus", "neutral"), ("🎯 Suggested priorities", "formal"),
    ("🎯 Hit these first", "playful"), ("🎯 Top of tomorrow", "warm"), ("🎯 Focus list", "brief"),
    # generic none-found lines live in *_STATUS; headers only here
    ("🗂 Notes", "neutral"), ("🗂 For your attention", "formal"),
    ("🗂 Worth knowing", "warm"), ("🗂 FYI", "brief"), ("🗂 In case you missed it", "playful"),
    ("📌 Pinned", "neutral"), ("📌 Don't forget", "warm"),
    ("📌 Reminder", "formal"), ("📌 Flagged", "brief"), ("📌 Eyes here", "playful"),
]
# ------------------------------------------------------------------ weather
WEATHER_REPORT = [
    ("{cond}, around {temp}°{unit}", "brief"),
    ("Expect {cond} — highs near {temp}°{unit}", "neutral"),
    ("{cond} today, {temp}°{unit}", "neutral"),
    ("It's {cond} out there, sitting at {temp}°{unit}", "warm"),
    ("{cond} on tap, thermometer reads {temp}°{unit}", "playful"),
    ("Currently {cond}, {temp}°{unit}", "formal"),
    ("{cond} with a high of {temp}°{unit}", "neutral"),
    ("Looks like {cond} — about {temp}°{unit}", "warm"),
    ("{cond}, topping out at {temp}°{unit}", "brief"),
    ("Skies say {cond}; {temp}°{unit} for a high", "playful"),
    ("{cond}, and a {chance}% chance of precipitation", "formal"),
    ("{cond} with precipitation at {chance}%", "neutral"),
    ("{cond} — rain likelihood {chance}%", "brief"),
    ("Keep an eye out: {cond}, {chance}% precip chance", "warm"),
    ("{cond}, {temp}°{unit}, {chance}% chance of rain", "neutral"),
]
WEATHER_ADVICE = [
    ("Rain likely — grab an umbrella on your way out", "neutral"),
    ("Wet weather ahead; the umbrella earns its keep today", "warm"),
    ("Pack a rain layer — showers expected", "brief"),
    ("Umbrella day. Trust the clouds on this one", "playful"),
    ("Sunny and clear — sunglasses suggested", "neutral"),
    ("Blue skies ahead; enjoy the bright one", "warm"),
    ("Sun's out — hats if you're outside midday", "brief"),
    ("Clear skies — a great day to walk between appointments", "warm"),
    ("Chilly start — layer up this morning", "neutral"),
    ("Cold out there; warm coat weather", "brief"),
    ("Bundle up — it's brisk", "playful"),
    ("Frost possible early; watch the sidewalks", "formal"),
    ("Hot day ahead — hydrate well", "neutral"),
    ("Heat on the rise; water bottle recommended", "brief"),
    ("Warm one today — light clothing wins", "warm"),
    ("Snow possible — allow extra travel time", "formal"),
    ("Snow in the forecast; drive gently", "neutral"),
    ("Flurries possible — cozy day to be indoors", "warm"),
    ("Windy conditions — secure anything loose outside", "formal"),
    ("Breezy out; hold onto your hat", "playful"),
    ("Fog expected — low visibility on the morning drive", "neutral"),
    ("Foggy start; headlights on", "brief"),
    ("Storm risk — keep plans flexible", "formal"),
    ("Thunderstorms possible; indoor backup plans wise", "neutral"),
    ("Mild and calm — no weather concerns today", "neutral"),
    ("Pleasant conditions — no gear required", "brief"),
    ("Classic Oregon drizzle — light rain shell suffices", "playful"),
    ("Overcast but dry — an easy weather day", "neutral"),
]
# --------------------------------------------------------------------- tasks
TASKS_STATUS = [
    ("{count} task(s) on your list", "brief"),
    ("You have {count} open task(s)", "neutral"),
    ("{count} item(s) awaiting your attention", "formal"),
    ("{count} thing(s) to knock out", "playful"),
    ("Your list holds {count} open item(s)", "warm"),
    ("OVERDUE: {title}", "formal"),
    ("Overdue and needs you: {title}", "warm"),
    ("{title} — past due", "brief"),
    ("{title} is overdue; today is a good day to clear it", "neutral"),
    ("Due soon: {title}", "neutral"),
    ("{title} — coming due", "brief"),
    ("{title} is due before you know it", "playful"),
    ("Deadline approaching for {title}", "formal"),
    ("Inbox zero — task list is clear!", "playful"),
    ("Nothing pending. A rare clear list", "warm"),
    ("All tasks complete — well done", "formal"),
    ("No open tasks. Enjoy the calm", "neutral"),
    ("List is empty — add something when ready", "brief"),
    ("Top of the list: {title}", "neutral"),
    ("Highest priority: {title}", "formal"),
    ("Start here: {title}", "brief"),
    ("{title} should get your first hour", "warm"),
]
EMAIL_STATUS = [
    ("{count} unread message(s)", "brief"),
    ("You have {count} new email(s)", "neutral"),
    ("{count} message(s) waiting in your inbox", "formal"),
    ("{count} email(s) came in — scan below", "warm"),
    ("{count} unread. Here are the highlights", "playful"),
    ("Inbox zero — nothing unread!", "playful"),
    ("No new mail. Quiet inbox", "neutral"),
    ("Inbox is clear", "brief"),
    ("All caught up on email", "warm"),
    ("⭐ From {sender}: {subject}", "neutral"),
    ("⭐ {sender} — flagged important", "brief"),
    ("⭐ Priority sender {sender} wrote: {subject}", "formal"),
    ("⭐ One from {sender} needs your eyes", "warm"),
    ("{sender} — {subject}", "neutral"),
    ("{sender}: {subject}", "brief"),
    ("Message from {sender} about {subject}", "formal"),
    ("{sender} wrote in — {subject}", "warm"),
    ("One of them, from {sender}, looks reply-worthy", "neutral"),
    ("Your client emailed — {subject}", "warm"),
    ("Nothing urgent among the unread", "neutral"),
    ("No flagged senders in today's batch", "brief"),
    ("Routine mail only — no fires", "playful"),
]
DRAFT_OFFER = [
    ("Want me to draft a reply to any of these?", "neutral"),
    ("Say the word and I'll draft responses", "brief"),
    ("I can prepare drafts for your review — just point", "warm"),
    ("Shall I draft replies to the important ones?", "formal"),
    ("Happy to draft replies; tell me which", "neutral"),
    ("Reply here and I'll prepare drafts for you to review", "neutral"),
    ("I can have drafts waiting in your inbox — name the emails", "warm"),
    ("Drafts on request — which messages deserve replies?", "playful"),
]
# Draft openers: 12 intents × 4 registers (formal/neutral/warm/brief)
DRAFT_OPENER_FORMAL = [
    ("Thank you for your message regarding {subject}.", "formal"),
    ("I am writing in response to your email about {subject}.", "formal"),
    ("Thank you for reaching out about {subject}.", "formal"),
    ("I appreciate your patience regarding {subject}.", "formal"),
    ("This confirms our arrangement for {subject}.", "formal"),
    ("I must respectfully decline your invitation regarding {subject}.", "formal"),
    ("I would like to reschedule our appointment concerning {subject}.", "formal"),
    ("Please accept my apologies for the delay regarding {subject}.", "formal"),
    ("I am following up on our previous correspondence about {subject}.", "formal"),
    ("Allow me to introduce myself regarding {subject}.", "formal"),
    ("I am writing to request information about {subject}.", "formal"),
    ("This serves as a friendly reminder concerning {subject}.", "formal"),
]
DRAFT_OPENER_NEUTRAL = [
    ("Thanks for your email about {subject}.", "neutral"),
    ("Getting back to you on {subject}.", "neutral"),
    ("Thanks for reaching out about {subject}.", "neutral"),
    ("Appreciate your patience on {subject}.", "neutral"),
    ("Confirming {subject} — all set.", "neutral"),
    ("Thanks for the invite to {subject}, but I'll have to pass.", "neutral"),
    ("Could we move {subject} to another time?", "neutral"),
    ("Sorry for the slow reply on {subject}.", "neutral"),
    ("Circling back on {subject}.", "neutral"),
    ("Quick introduction regarding {subject}.", "neutral"),
    ("A question about {subject}.", "neutral"),
    ("Friendly reminder about {subject}.", "neutral"),
]
DRAFT_OPENER_WARM = [
    ("So good to hear from you about {subject}!", "warm"),
    ("Thanks so much for writing about {subject} — happy to help.", "warm"),
    ("Lovely to hear from you! Re: {subject}.", "warm"),
    ("Thank you for your kindness re {subject}.", "warm"),
    ("Delighted to confirm {subject}!", "warm"),
    ("So sorry, but I can't make {subject} — wishing you the best with it.", "warm"),
    ("Would another day work for {subject}? Hope so!", "warm"),
    ("My apologies for the delay on {subject} — life got busy.", "warm"),
    ("Thinking of you — following up on {subject}.", "warm"),
    ("A warm hello before we talk {subject}.", "warm"),
    ("Hoping you can help with {subject} — thanks in advance!", "warm"),
    ("Gentle nudge about {subject} — no rush!", "warm"),
]
DRAFT_OPENER_BRIEF = [
    ("Re: {subject} — thanks.", "brief"), ("{subject}: got it.", "brief"),
    ("About {subject}…", "brief"), ("{subject} — noted, thanks.", "brief"),
    ("Confirmed: {subject}.", "brief"), ("Can't make {subject}. Sorry.", "brief"),
    ("Reschedule {subject}?", "brief"), ("Apologies for the delay re {subject}.", "brief"),
    ("Following up: {subject}.", "brief"), ("Quick intro re {subject}.", "brief"),
    ("Question re {subject}.", "brief"), ("Reminder: {subject}.", "brief"),
]
DRAFT_CLOSER_FORMAL = [
    ("Thank you for your time and consideration.", "formal"),
    ("Please do not hesitate to contact me with any questions.", "formal"),
    ("I look forward to your response at your earliest convenience.", "formal"),
    ("Thank you for your understanding in this matter.", "formal"),
    ("I appreciate your attention to this request.", "formal"),
    ("Please confirm receipt at your convenience.", "formal"),
    ("With gratitude for your assistance.", "formal"),
    ("Respectfully submitted for your review.", "formal"),
]
DRAFT_CLOSER_NEUTRAL = [
    ("Let me know if you need anything else.", "neutral"),
    ("Happy to answer any questions.", "neutral"),
    ("Looking forward to hearing back.", "neutral"),
    ("Thanks again.", "neutral"),
    ("Hope that helps — just say the word.", "neutral"),
    ("Talk soon.", "neutral"),
    ("More details on request.", "neutral"),
    ("Standing by for your reply.", "neutral"),
]
DRAFT_CLOSER_WARM = [
    ("With warm regards and thanks!", "warm"),
    ("So looking forward to it — see you then!", "warm"),
    ("Sending best wishes your way.", "warm"),
    ("Thanks a million — you’re the best.", "warm"),
    ("Hope your week treats you kindly.", "warm"),
    ("Can’t wait — thanks again!", "warm"),
    ("Grateful for you — talk soon.", "warm"),
    ("Warmly yours, always.", "warm"),
]
DRAFT_CLOSER_BRIEF = [
    ("Thanks.", "brief"), ("Best.", "brief"), ("Cheers.", "brief"),
    ("— W.", "brief"), ("Soon.", "brief"), ("Noted, thanks.", "brief"),
    ("Regards.", "brief"), ("Done.", "brief"),
]
SIGNOFF = [
    ("Best regards,", "formal"), ("Kind regards,", "formal"),
    ("Sincerely,", "formal"), ("Respectfully,", "formal"),
    ("Best,", "neutral"), ("Thanks,", "neutral"),
    ("Cheers,", "playful"), ("Warmly,", "warm"),
    ("Take care,", "warm"), ("All the best,", "neutral"),
    ("Talk soon,", "playful"), ("Yours,", "warm"),
]
ACKNOWLEDGMENT = [
    ("Done.", "brief"), ("On it.", "brief"), ("Got it.", "brief"),
    ("Understood.", "formal"), ("Noted.", "formal"),
    ("Consider it handled.", "neutral"), ("Will do.", "neutral"),
    ("Right away.", "neutral"), ("You got it.", "warm"),
    ("Happy to help.", "warm"), ("Leave it with me.", "warm"),
    ("Absolutely — give me a moment.", "playful"),
    ("Acknowledged.", "formal"), ("Working on it now.", "neutral"),
]
FALLBACK = [
    ("{source} is unavailable right now — {reason}", "neutral"),
    ("Couldn't reach {source}: {reason}", "brief"),
    ("{source} didn't answer ({reason}); skipping for now", "warm"),
    ("No data from {source} — {reason}", "formal"),
    ("{source} is being shy ({reason}). Moving on", "playful"),
    ("Temporarily unable to fetch {source}: {reason}", "formal"),
    ("{source} check failed — {reason}. Will retry next briefing", "neutral"),
    ("Missing: {source} ({reason})", "brief"),
]
ENCOURAGEMENT = [
    ("Solid progress today.", "neutral"), ("Well done getting through the list.", "formal"),
    ("Look at you — getting things done!", "playful"),
    ("Another day, another set of wins.", "warm"),
    ("You moved the needle today.", "warm"),
    ("Progress, not perfection. Nicely done.", "warm"),
    ("Every checked box counts. Good work.", "neutral"),
    ("That’s a wrap — rest well tonight.", "warm"),
    ("Quiet day or full tilt, you showed up. That counts.", "warm"),
    ("Tomorrow’s list is lighter because of today.", "neutral"),
    ("Chin up — unfinished lists are normal; you’re on it.", "warm"),
    ("Small steps still move you forward.", "neutral"),
]
PRIORITY_FRAME = [
    ("If you only do three things tomorrow:", "neutral"),
    ("Suggested focus for tomorrow:", "formal"),
    ("Tomorrow’s top three:", "brief"),
    ("Start tomorrow with these:", "warm"),
    ("Your best first moves tomorrow:", "playful"),
    ("Based on deadlines, I’d tackle:", "neutral"),
    ("Highest-leverage items for tomorrow:", "formal"),
    ("Tomorrow, front-load these:", "brief"),
]
OFFER = [
    ("Would you like me to draft replies?", "neutral"),
    ("Want the full text of any email?", "neutral"),
    ("Shall I add that to your task list?", "neutral"),
    ("Need me to reschedule anything?", "neutral"),
    ("Want a reminder before each event?", "neutral"),
    ("Should I keep an eye on that thread?", "neutral"),
    ("Want me to mark any tasks complete?", "neutral"),
    ("Shall I summarize the long ones?", "neutral"),
    ("Need directions or travel time for any appointment?", "neutral"),
    ("Want tomorrow’s briefing earlier or later?", "neutral"),
    ("Should I flag this sender as important?", "neutral"),
    ("Would you like a deeper look at any of these?", "formal"),
]
TIME_PHRASE = [
    ("today", "neutral"), ("tomorrow", "neutral"), ("tonight", "neutral"),
    ("this morning", "neutral"), ("this afternoon", "neutral"), ("this evening", "neutral"),
    ("later today", "brief"), ("first thing tomorrow", "neutral"),
    ("before your first appointment", "formal"), ("by end of day", "formal"),
    ("within the hour", "formal"), ("after lunch", "brief"),
    ("this week", "neutral"), ("next week", "neutral"),
    ("the coming days", "formal"), ("over the weekend", "neutral"),
    ("in a bit", "playful"), ("shortly", "formal"),
    ("when you have a moment", "warm"), ("at your convenience", "formal"),
]
APPROVAL_PROMPT = [
    ("May I send this reply to {sender}?", "neutral"),
    ("Draft ready for {sender} — send it? (yes / edit / no)", "neutral"),
    ("Shall I send the response to {sender}?", "formal"),
    ("Reply to {sender} is ready for your approval.", "formal"),
    ("I’ve drafted a note to {sender}. Your call: send or revise?", "warm"),
    ("Ready to go to {sender} — give the green light?", "playful"),
    ("Send to {sender}? One word and it’s on its way.", "brief"),
    ("Pending your approval: reply to {sender}.", "formal"),
]
CONFIRMATION = [
    ("Sent.", "brief"), ("Sent to {sender}.", "neutral"),
    ("Off it goes to {sender}.", "playful"),
    ("Your reply to {sender} has been sent.", "formal"),
    ("Delivered to {sender}.", "neutral"),
    ("Draft saved — review it in your email when ready.", "neutral"),
    ("Draft is waiting in your mailbox.", "warm"),
    ("Saved as a draft, per your settings.", "formal"),
    ("Added to your task list.", "neutral"),
    ("Marked complete. Nice.", "playful"),
    ("Calendar updated.", "neutral"),
    ("Event added to your calendar.", "formal"),
]
TRANSITION = [
    ("Meanwhile,", "neutral"), ("Also of note:", "neutral"),
    ("In other news:", "playful"), ("Additionally,", "formal"),
    ("Worth mentioning:", "warm"), ("Separately,", "formal"),
    ("On another front,", "neutral"), ("Heads up:", "playful"),
    ("Note:", "brief"), ("For context,", "formal"),
    ("And finally,", "neutral"), ("Lastly,", "formal"),
    ("Before you go:", "warm"), ("One more thing:", "playful"),
    ("Also:", "brief"), ("Plus,", "neutral"),
]
ERROR_APOLOGY = [
    ("Sorry — I couldn't complete that just now.", "neutral"),
    ("That didn't work on my end; details below.", "neutral"),
    ("Apologies, something failed: {reason}", "formal"),
    ("Hiccup on my side ({reason}) — want me to retry?", "warm"),
    ("Well, that broke ({reason}). I can try again.", "playful"),
    ("I hit a snag: {reason}.", "brief"),
]
# ----------------------------------------------------------- vocabulary sets
VOCAB_WEATHER = [
    ("sunny", "neutral"), ("clear", "neutral"), ("overcast", "neutral"),
    ("drizzle", "neutral"), ("showers", "neutral"), ("rain", "neutral"),
    ("downpour", "playful"), ("mist", "neutral"), ("fog", "neutral"),
    ("haze", "neutral"), ("breeze", "neutral"), ("windy", "neutral"),
    ("gusts", "formal"), ("calm", "neutral"), ("mild", "neutral"),
    ("chilly", "warm"), ("brisk", "playful"), ("frosty", "neutral"),
    ("freezing", "formal"), ("warm", "neutral"), ("hot", "neutral"),
    ("humid", "neutral"), ("dry", "neutral"), ("snow", "neutral"),
    ("flurries", "playful"), ("sleet", "formal"), ("hail", "formal"),
    ("thunderstorms", "formal"), ("lightning", "formal"), ("cloudy", "neutral"),
    ("partly cloudy", "neutral"), ("mostly sunny", "neutral"), ("gray", "playful"),
    ("bright", "warm"), ("damp", "neutral"), ("crisp", "warm"),
    ("scattered showers", "formal"), ("heavy rain", "formal"),
    ("light rain", "neutral"), ("sprinkles", "playful"),
]
VOCAB_STATUS = [
    ("done", "neutral"), ("complete", "formal"), ("finished", "neutral"),
    ("closed", "formal"), ("resolved", "formal"), ("pending", "formal"),
    ("open", "neutral"), ("outstanding", "formal"), ("in progress", "neutral"),
    ("underway", "formal"), ("blocked", "neutral"), ("waiting", "neutral"),
    ("deferred", "formal"), ("scheduled", "formal"), ("queued", "neutral"),
    ("overdue", "formal"), ("due", "neutral"), ("upcoming", "neutral"),
    ("urgent", "formal"), ("important", "neutral"), ("routine", "neutral"),
    ("optional", "neutral"), ("backlog", "neutral"), ("archived", "formal"),
    ("cancelled", "formal"), ("postponed", "formal"), ("confirmed", "formal"),
    ("tentative", "formal"), ("draft", "neutral"), ("sent", "neutral"),
    ("delivered", "formal"), ("read", "neutral"), ("unread", "neutral"),
    ("flagged", "neutral"), ("starred", "neutral"), ("snoozed", "playful"),
    ("active", "neutral"), ("paused", "neutral"), ("ready", "neutral"),
]
VOCAB_DAYPART = [
    ("dawn", "warm"), ("sunrise", "warm"), ("early morning", "neutral"),
    ("mid-morning", "neutral"), ("late morning", "neutral"), ("noon", "neutral"),
    ("midday", "neutral"), ("early afternoon", "neutral"),
    ("late afternoon", "neutral"), ("dusk", "warm"), ("sunset", "warm"),
    ("early evening", "neutral"), ("evening", "neutral"), ("night", "neutral"),
    ("late night", "neutral"), ("midnight", "neutral"), ("overnight", "formal"),
    ("daybreak", "playful"), ("twilight", "formal"), ("sundown", "playful"),
]
NUMBER_WORD = [
    ("zero", "neutral"), ("one", "neutral"), ("two", "neutral"), ("three", "neutral"),
    ("four", "neutral"), ("five", "neutral"), ("six", "neutral"), ("seven", "neutral"),
    ("eight", "neutral"), ("nine", "neutral"), ("ten", "neutral"), ("eleven", "neutral"),
    ("twelve", "neutral"), ("thirteen", "neutral"), ("fourteen", "neutral"),
    ("fifteen", "neutral"), ("sixteen", "neutral"), ("seventeen", "neutral"),
    ("eighteen", "neutral"), ("nineteen", "neutral"), ("twenty", "neutral"),
]
# ------------------------------------------------- second curation pass ----
GREETING_AFTERNOON = [
    ("Good afternoon{name}!", "warm"), ("Afternoon{name}!", "brief"),
    ("Good afternoon{name} — midday check-in.", "neutral"),
    ("Afternoon{name}! Hope the morning treated you well.", "warm"),
    ("Hello{name}, good afternoon.", "formal"),
    ("Midday hello{name}!", "playful"),
]
GREETING_GENERAL = [
    ("Hello{name}!", "neutral"), ("Hi{name}!", "brief"),
    ("Hey{name}!", "playful"), ("Hello{name}, at your service.", "formal"),
    ("Hi{name} — what can I do for you?", "warm"),
    ("Hey{name}! What's on your mind?", "playful"),
    ("Hello{name}. How may I help?", "formal"),
    ("Hi{name}! Ready when you are.", "warm"),
]
GOODBYE = [
    ("Goodbye{name}!", "neutral"), ("Bye for now{name}!", "brief"),
    ("Take care{name}!", "warm"), ("See you tomorrow{name}!", "warm"),
    ("Until next time{name}.", "formal"), ("Later{name}!", "playful"),
    ("Rest well tonight{name}.", "warm"), ("Signing off — good night.", "neutral"),
    ("That's all from me — good night{name}.", "formal"),
    ("Catch you later{name}!", "playful"), ("Good night{name}.", "neutral"),
    ("Over and out{name}.", "playful"),
]
THANKS = [
    ("Thank you!", "neutral"), ("Thanks!", "brief"), ("Much appreciated.", "warm"),
    ("Many thanks.", "formal"), ("You're welcome!", "warm"),
    ("Anytime.", "playful"), ("Happy to help.", "warm"),
    ("My pleasure.", "formal"), ("Glad I could assist.", "formal"),
    ("No trouble at all.", "warm"), ("Of course.", "neutral"), ("De nada.", "playful"),
]
APOLOGY = [
    ("Sorry about that.", "neutral"), ("My apologies.", "formal"),
    ("Apologies for the confusion.", "formal"), ("That one's on me.", "warm"),
    ("Oops — let me fix that.", "playful"), ("Sorry, I missed that.", "neutral"),
    ("Pardon the interruption.", "formal"), ("Forgive the delay.", "formal"),
    ("My mistake — correcting now.", "neutral"), ("Sorry for the bother.", "warm"),
]
TASK_VERB = [
    ("call", "neutral"), ("email", "neutral"), ("schedule", "neutral"),
    ("review", "neutral"), ("finish", "neutral"), ("start", "neutral"),
    ("draft", "neutral"), ("send", "neutral"), ("pay", "neutral"),
    ("order", "neutral"), ("renew", "neutral"), ("book", "neutral"),
    ("confirm", "neutral"), ("cancel", "neutral"), ("reschedule", "neutral"),
    ("prepare", "neutral"), ("submit", "formal"), ("file", "neutral"),
    ("sign", "neutral"), ("pick up", "brief"), ("drop off", "brief"),
    ("follow up", "neutral"), ("check", "brief"), ("write", "neutral"),
    ("read", "neutral"), ("plan", "neutral"), ("organize", "neutral"),
    ("clean", "neutral"), ("fix", "neutral"), ("update", "neutral"),
    ("print", "neutral"), ("scan", "neutral"), ("return", "neutral"),
    ("buy", "brief"), ("refill", "neutral"), ("restock", "neutral"),
    ("water", "brief"), ("feed", "brief"), ("walk", "brief"), ("stretch", "playful"),
]
MEETING_WORD = [
    ("appointment", "formal"), ("meeting", "neutral"), ("call", "neutral"),
    ("video call", "neutral"), ("consultation", "formal"), ("check-in", "warm"),
    ("standup", "neutral"), ("review", "neutral"), ("interview", "formal"),
    ("session", "neutral"), ("visit", "neutral"), ("follow-up", "neutral"),
    ("intake", "neutral"), ("walkthrough", "neutral"), ("demo", "playful"),
    ("briefing", "formal"), ("debrief", "formal"), ("sync", "playful"),
    ("one-on-one", "neutral"), ("roundtable", "formal"), ("office hours", "neutral"),
    ("house call", "warm"), ("site visit", "formal"), ("phone call", "neutral"),
]
EMAIL_SUBJECT_TEMPLATE = [
    ("Re: {subject}", "neutral"), ("Following up: {subject}", "neutral"),
    ("Quick question about {subject}", "warm"),
    ("Confirming {subject}", "formal"), ("Regarding {subject}", "formal"),
    ("{subject} — reschedule?", "brief"), ("{subject} — confirmed", "brief"),
    ("Update on {subject}", "neutral"), ("Reminder: {subject}", "neutral"),
    ("Thank you — {subject}", "warm"), ("Introduction: {subject}", "formal"),
    ("Action needed: {subject}", "formal"), ("FYI: {subject}", "brief"),
    ("{subject} — details inside", "neutral"), ("Checking in on {subject}", "warm"),
    ("{subject}: next steps", "formal"),
]
BRIEFING_INTRO = [
    ("Here's your day at a glance:", "neutral"),
    ("Your morning briefing:", "formal"),
    ("Everything that matters today:", "warm"),
    ("The day, distilled:", "playful"),
    ("One page, whole day:", "brief"),
    ("Here's what I found overnight:", "neutral"),
    ("Today's rundown, fresh off the wires:", "playful"),
    ("Your day, organized:", "formal"),
    ("Straight to it:", "brief"),
    ("Here's the shape of your day:", "warm"),
    ("Overnight summary below:", "neutral"),
    ("Good things to know this morning:", "warm"),
]
WRAPUP_INTRO = [
    ("Here's how today went:", "neutral"),
    ("Your evening wrap-up:", "formal"),
    ("The day in review:", "warm"),
    ("Closing time — summary below:", "playful"),
    ("Today, accounted for:", "brief"),
    ("Let's put today to bed:", "warm"),
    ("End-of-day report:", "formal"),
    ("Before you sign off:", "neutral"),
    ("Today's tally:", "playful"),
    ("Reviewing the day that was:", "warm"),
    ("Evening check-in — the numbers:", "neutral"),
    ("Wrapping up your day:", "formal"),
]
DATE_PHRASE = [
    ("{date:%A, %B %-d}", "neutral"), ("{date:%A %B %-d}", "brief"),
    ("{date:%m/%d}", "brief"), ("{date:%Y-%m-%d}", "formal"),
    ("{date:%A the %-d}", "warm"), ("{date:%a %b %-d}", "brief"),
    ("this {date:%A}", "neutral"), ("{date:%A} next", "formal"),
    ("{date:%B %-d, %Y}", "formal"), ("{date:%A}, {time}", "neutral"),
    ("{time} on {date:%A}", "neutral"), ("{date:%A} at {time}", "warm"),
]
DEADLINE_PHRASE = [
    ("due {time}", "neutral"), ("deadline: {time}", "formal"),
    ("due by {time}", "neutral"), ("must finish by {time}", "brief"),
    ("no later than {time}", "formal"), ("before {time} rolls around", "playful"),
    ("on the clock for {time}", "playful"), ("{time} at the latest", "brief"),
    ("needed by {time}", "neutral"), ("{time} deadline", "formal"),
    ("wrap up by {time}", "warm"), ("expires {time}", "formal"),
]
NUDGE_PHRASE = [
    ("Gentle nudge: {title} is still open.", "warm"),
    ("Friendly reminder about {title}.", "neutral"),
    ("{title} — still on your radar?", "playful"),
    ("Don't let {title} slip.", "warm"),
    ("{title} awaits your attention.", "formal"),
    ("Circling back on {title}.", "neutral"),
    ("{title} is patiently waiting.", "playful"),
    ("A nudge on {title}, whenever you're ready.", "warm"),
    ("Ping: {title}.", "brief"),
    ("{title} would love five minutes of your time.", "playful"),
    ("Reminder flagged: {title}.", "formal"),
    ("Still outstanding: {title}.", "neutral"),
]
CLARIFY_QUESTION = [
    ("Which one did you mean?", "neutral"),
    ("Could you clarify?", "formal"),
    ("A little more detail, please?", "warm"),
    ("Which email should I reply to?", "neutral"),
    ("Which task should I mark done?", "neutral"),
    ("What time works for that?", "neutral"),
    ("How long should it run?", "neutral"),
    ("Formal or casual tone?", "neutral"),
    ("Short reply or detailed?", "neutral"),
    ("Send now or save as draft?", "neutral"),
    ("Add a due date?", "brief"),
    ("High priority?", "brief"),
]
YES_NO = [
    ("yes", "brief"), ("no", "brief"), ("yes, please", "warm"),
    ("no, thanks", "warm"), ("absolutely", "playful"), ("definitely", "playful"),
    ("of course", "warm"), ("certainly", "formal"), ("affirmative", "formal"),
    ("negative", "formal"), ("not this time", "neutral"), ("maybe later", "neutral"),
    ("go ahead", "neutral"), ("hold off", "brief"), ("approved", "formal"),
    ("declined", "formal"), ("sounds good", "playful"), ("I'll pass", "neutral"),
    ("please do", "warm"), ("not yet", "neutral"),
]
SCHEDULING = [
    ("I'll find a time for that.", "neutral"),
    ("Let me check the calendar.", "neutral"),
    ("Adding it to your schedule.", "formal"),
    ("Penciling that in.", "playful"),
    ("Blocked out on your calendar.", "neutral"),
    ("Time reserved — it's yours.", "warm"),
    ("Scheduled and confirmed.", "formal"),
    ("I've slotted that in for {time}.", "neutral"),
    ("Your calendar has a new entry.", "neutral"),
    ("Consider it scheduled.", "formal"),
    ("Locked in for {time}.", "playful"),
    ("On the books for {time}.", "warm"),
]
TRAVEL = [
    ("Leave by {time} to arrive comfortably.", "neutral"),
    ("Budget extra travel time today.", "neutral"),
    ("Traffic may slow the commute.", "formal"),
    ("Allow a buffer for the drive.", "warm"),
    ("Roads might be wet — drive gently.", "warm"),
    ("Plan the route before you go.", "brief"),
    ("Consider leaving a touch earlier.", "warm"),
    ("Travel looks clear today.", "neutral"),
]
FOCUS = [
    ("Protect your focus time today.", "neutral"),
    ("Deep work window: guard it well.", "warm"),
    ("Consider batching the small tasks.", "neutral"),
    ("One thing at a time wins the day.", "warm"),
    ("Clear the deck for concentrated work.", "formal"),
    ("Silence notifications for this block?", "playful"),
    ("Your sharpest hours are ahead — use them.", "warm"),
    ("Focus block scheduled.", "brief"),
]
TRIAGE_LABEL = [
    ("needs reply", "neutral"), ("FYI only", "brief"),
    ("action required", "formal"), ("read later", "neutral"),
    ("newsletter", "neutral"), ("receipt", "neutral"),
    ("invitation", "formal"), ("reminder", "neutral"),
    ("notification", "neutral"), ("personal", "warm"),
    ("work", "neutral"), ("finance", "formal"),
    ("scheduling", "neutral"), ("question", "neutral"),
    ("urgent", "formal"), ("low priority", "brief"),
]
SENDER_KIND = [
    ("client", "neutral"), ("colleague", "neutral"), ("vendor", "formal"),
    ("newsletter", "neutral"), ("automated notice", "formal"),
    ("friend", "warm"), ("family", "warm"), ("unknown sender", "brief"),
    ("mailing list", "neutral"), ("service update", "formal"),
    ("billing department", "formal"), ("support team", "neutral"),
    ("new contact", "neutral"), ("regular correspondent", "formal"),
    ("no-reply address", "brief"), ("your bank", "neutral"),
]
URGENCY = [
    ("urgent", "formal"), ("high priority", "formal"), ("time-sensitive", "formal"),
    ("routine", "neutral"), ("when convenient", "warm"), ("low stakes", "playful"),
    ("at your leisure", "formal"), ("no rush", "warm"), ("important", "neutral"),
    ("critical", "formal"), ("soon-ish", "playful"), ("someday", "playful"),
    ("top of pile", "warm"), ("back burner", "playful"), ("asap", "brief"),
    ("by end of day", "formal"),
]
REACTION_POSITIVE = [
    ("Great news!", "warm"), ("Excellent.", "formal"), ("Wonderful!", "warm"),
    ("That's a win.", "playful"), ("Love to see it.", "playful"),
    ("Well done.", "formal"), ("Nicely handled.", "warm"),
    ("Perfect.", "brief"), ("Superb.", "formal"), ("Bravo.", "playful"),
    ("That worked beautifully.", "warm"), ("Success.", "brief"),
]
REACTION_SYMPATHY = [
    ("Sorry to hear that.", "warm"), ("That's frustrating — understood.", "warm"),
    ("Understood; these things happen.", "formal"),
    ("No worries — it happens.", "playful"),
    ("That's okay; we'll sort it out.", "warm"),
    ("I see — let's work around it.", "neutral"),
    ("Understood. Adjusting course.", "formal"),
    ("Ah well — onward.", "playful"),
]
REMINDER_PHRASE = [
    ("Reminder: {title}", "neutral"), ("Don't forget: {title}", "warm"),
    ("Heads up — {title}", "playful"), ("Note to self: {title}", "warm"),
    ("Flagged for you: {title}", "formal"), ("Keep {title} in view", "brief"),
    ("Pinging about {title}", "playful"), ("On your list: {title}", "neutral"),
    ("Marked: {title}", "brief"), ("Set a reminder for {title}?", "neutral"),
    ("I'll remind you about {title}", "warm"), ("Reminder noted: {title}", "formal"),
    ("Worth remembering: {title}", "neutral"), ("Tap on the shoulder: {title}", "playful"),
    ("Calendar reminder: {title}", "formal"), ("Mental note: {title}", "warm"),
]
ERRAND = [
    ("groceries", "neutral"), ("pharmacy run", "neutral"), ("post office", "neutral"),
    ("dry cleaning", "neutral"), ("hardware store", "neutral"), ("bank errand", "formal"),
    ("farmers market", "warm"), ("pet supplies", "neutral"), ("car wash", "brief"),
    ("oil change", "neutral"), ("package pickup", "neutral"), ("returns", "brief"),
    ("library books", "warm"), ("garden center", "warm"), ("office supplies", "neutral"),
    ("gift shopping", "warm"),
]
HOUSEHOLD = [
    ("laundry", "neutral"), ("dishes", "brief"), ("vacuuming", "neutral"),
    ("take out trash", "brief"), ("recycling", "neutral"), ("yard work", "neutral"),
    ("water plants", "warm"), ("change filters", "neutral"), ("grocery restock", "neutral"),
    ("meal prep", "neutral"), ("tidy desk", "brief"), ("organize closet", "neutral"),
    ("clean gutters", "neutral"), ("check smoke detectors", "formal"),
    ("rotate tires", "neutral"), ("defrost freezer", "playful"),
]
FINANCE = [
    ("invoice", "formal"), ("receipt", "neutral"), ("payment due", "formal"),
    ("bill", "neutral"), ("statement", "formal"), ("budget review", "formal"),
    ("expense report", "formal"), ("reimbursement", "formal"), ("subscription", "neutral"),
    ("renewal fee", "formal"), ("tax document", "formal"), ("refund", "neutral"),
    ("charge", "neutral"), ("balance", "formal"), ("transfer", "formal"), ("deposit", "neutral"),
]
HEALTH_APPOINTMENT = [
    ("patient appointment", "formal"), ("follow-up visit", "neutral"),
    ("lab results", "neutral"), ("annual physical", "neutral"),
    ("dental cleaning", "neutral"), ("eye exam", "neutral"),
    ("prescription refill", "neutral"), ("telehealth call", "neutral"),
    ("clinic rounds", "neutral"), ("chart review", "formal"),
    ("wellness check", "warm"), ("vaccination", "formal"),
    ("blood draw", "neutral"), ("specialist referral", "formal"),
    ("physical therapy", "neutral"), ("massage", "warm"),
]
CONGRATULATION = [
    ("Congratulations!", "warm"), ("Well deserved!", "warm"),
    ("Fantastic work!", "warm"), ("You earned this.", "warm"),
    ("Hats off!", "playful"), ("Kudos!", "playful"),
    ("A big well-done.", "formal"), ("Celebrations are in order!", "warm"),
    ("Champagne moment!", "playful"), ("Truly excellent.", "formal"),
    ("What an achievement!", "warm"), ("Three cheers!", "playful"),
]
WAITING = [
    ("Waiting on a reply.", "neutral"), ("Still pending.", "brief"),
    ("Awaiting response.", "formal"), ("In their court now.", "playful"),
    ("Nothing back yet.", "brief"), ("Holding pattern.", "neutral"),
    ("Response expected soon.", "formal"), ("Give it another day.", "warm"),
    ("No word yet — patience.", "warm"), ("Pending their confirmation.", "formal"),
    ("Ball's in their court.", "playful"), ("Watching the inbox for it.", "neutral"),
]
RESCHEDULE = [
    ("Move it to another day?", "neutral"), ("Push to next week?", "brief"),
    ("Reschedule for a later time?", "formal"), ("Find a better slot?", "warm"),
    ("Shuffle the calendar a bit?", "playful"), ("Postpone until tomorrow?", "neutral"),
    ("Slide it back an hour?", "playful"), ("Pick a new date?", "neutral"),
    ("Defer to a quieter day?", "warm"), ("Relocate in the schedule?", "formal"),
    ("Bump it to the afternoon?", "brief"), ("Rebook for another time?", "neutral"),
    ("Trade slots with something else?", "playful"), ("Move it up instead?", "neutral"),
    ("Same time next week?", "warm"), ("Rain check?", "playful"),
]
SEASON_WORD = [
    ("spring", "neutral"), ("summer", "neutral"), ("autumn", "formal"),
    ("fall", "neutral"), ("winter", "neutral"), ("rainy season", "neutral"),
    ("dry season", "neutral"), ("harvest time", "warm"), ("planting season", "warm"),
    ("holiday season", "warm"), ("early spring", "neutral"), ("late summer", "neutral"),
]
HOLIDAY_WORD = [
    ("New Year's Day", "neutral"), ("Valentine's Day", "warm"),
    ("Independence Day", "formal"), ("Halloween", "playful"),
    ("Thanksgiving", "warm"), ("Christmas", "warm"), ("Memorial Day", "formal"),
    ("Labor Day", "formal"), ("Veterans Day", "formal"), ("Mother's Day", "warm"),
    ("Father's Day", "warm"), ("Earth Day", "neutral"),
]
PRIORITY_WORD = [
    ("critical", "formal"), ("high", "neutral"), ("medium", "neutral"),
    ("low", "neutral"), ("top", "brief"), ("first", "neutral"),
    ("secondary", "formal"), ("minor", "neutral"), ("major", "formal"),
    ("pressing", "formal"), ("immediate", "formal"), ("eventual", "formal"),
    ("chief", "formal"), ("primary", "formal"), ("backup", "neutral"), ("spare", "brief"),
]
GRATITUDE = [
    ("Much obliged.", "formal"), ("Deeply appreciated.", "formal"),
    ("Thanks a bunch.", "playful"), ("Endless thanks.", "warm"),
    ("Couldn't have done it without you.", "warm"), ("Truly grateful.", "warm"),
    ("Thanks for everything.", "warm"), ("A thousand thanks.", "playful"),
    ("Gratitude incoming!", "playful"), ("Thank you kindly.", "formal"),
    ("Appreciate you.", "warm"), ("Thanks for being you.", "warm"),
]
SUMMARY_WORD = [
    ("overview", "formal"), ("recap", "playful"), ("summary", "neutral"),
    ("digest", "formal"), ("rundown", "playful"), ("synopsis", "formal"),
    ("highlights", "neutral"), ("lowdown", "playful"), ("brief", "formal"),
    ("snapshot", "warm"), ("tally", "playful"), ("breakdown", "neutral"),
]
WEEKDAY_WORD = [
    ("Monday", "neutral"), ("Tuesday", "neutral"), ("Wednesday", "neutral"),
    ("Thursday", "neutral"), ("Friday", "neutral"), ("Saturday", "neutral"),
    ("Sunday", "neutral"),
]
MONTH_WORD = [
    ("January", "neutral"), ("February", "neutral"), ("March", "neutral"),
    ("April", "neutral"), ("May", "neutral"), ("June", "neutral"),
    ("July", "neutral"), ("August", "neutral"), ("September", "neutral"),
    ("October", "neutral"), ("November", "neutral"), ("December", "neutral"),
]
CLOSING_LINE = [
    ("That's all for now.", "neutral"), ("That's the full picture.", "neutral"),
    ("Over to you.", "playful"), ("Anything else, just ask.", "warm"),
    ("At your service all day.", "formal"), ("Here if you need me.", "warm"),
    ("That's the briefing — go get 'em.", "playful"), ("End of report.", "formal"),
    ("All caught up now.", "neutral"), ("You're fully briefed.", "formal"),
    ("Back to your regularly scheduled day.", "playful"), ("Done and delivered.", "brief"),
]
OPENING_LINE = [
    ("Here's what I have for you.", "neutral"), ("Reporting for duty.", "playful"),
    ("At your service.", "formal"), ("Ready when you are.", "warm"),
    ("Let's get you organized.", "warm"), ("Bringing you up to speed.", "neutral"),
    ("The latest, just for you.", "playful"), ("Your update awaits.", "formal"),
    ("Fresh intel, coming up.", "playful"), ("Here are the essentials.", "formal"),
    ("Let's take stock.", "warm"), ("Setting the scene for your day.", "warm"),
]
CHECKLIST_MARKER = [
    ("[ ]", "neutral"), ("[x]", "neutral"), ("✓", "neutral"), ("•", "neutral"),
    ("→", "brief"), ("⭐", "warm"), ("❗", "formal"), ("📌", "warm"),
]
# ------------------------------------------------------- new: situational lines
WEEKEND = [
    ("It's the weekend — light agenda ahead.", "neutral"),
    ("Weekend mode: only the essentials below.", "brief"),
    ("The weekend is here. Enjoy the slower pace.", "warm"),
    ("Saturday-style rules: nothing urgent unless it says so.", "playful"),
    ("Weekend briefing — short and sweet.", "brief"),
    ("No weekday hustle today; here's the light version.", "warm"),
    ("Weekend ahead. Rest is on the agenda too.", "warm"),
    ("Kicking off the weekend — here's what little there is.", "playful"),
    ("A relaxed weekend rundown for you.", "formal"),
    ("Weekend! Calendar's quiet, inbox can wait.", "playful"),
    ("Two days off the treadmill — here's the view.", "neutral"),
    ("Weekend edition: minimal commitments, maximum recovery.", "neutral"),
    ("It's officially the weekend. Breathe easy.", "warm"),
    ("Weekend summary, at your leisure.", "formal"),
    ("Downshift complete — welcome to the weekend.", "playful"),
]
HOLIDAY = [
    ("Happy {holiday}! Enjoy the day.", "warm"),
    ("It's {holiday} — offices are quiet today.", "neutral"),
    ("{holiday} today. Expect slower replies everywhere.", "brief"),
    ("Wishing you a wonderful {holiday}.", "formal"),
    ("{holiday}! Emails can definitely wait.", "playful"),
    ("Today is {holiday}; the schedule reflects that.", "formal"),
    ("{holiday} greetings! Light briefing for a light day.", "warm"),
    ("Marking {holiday} — most of the world is off duty.", "neutral"),
    ("{holiday} on the calendar; plan festivities accordingly.", "neutral"),
    ("It's {holiday}. Go enjoy — I'll hold the fort.", "playful"),
    ("A very happy {holiday} to you{name}.", "formal"),
    ("{holiday} today — minimal agenda, maximum cheer.", "warm"),
    ("Observing {holiday}; expect closures and quiet inboxes.", "formal"),
    ("{holiday}! The only task today is to enjoy it.", "playful"),
    ("Holiday hours in effect for {holiday}.", "brief"),
]
STREAK = [
    ("That's {count} days in a row — keep it going!", "warm"),
    ("{count}-day streak and counting.", "brief"),
    ("Streak status: {count} days strong.", "neutral"),
    ("{count} consecutive days. Impressive consistency.", "formal"),
    ("{count} days straight! The streak is alive.", "playful"),
    ("You've shown up {count} days running — nicely done.", "warm"),
    ("Streak check: {count} days, no misses.", "neutral"),
    ("{count} days unbroken. A record in the making.", "formal"),
    ("Day {count} of the streak — don't break the chain!", "playful"),
    ("Consistency report: {count} days and holding.", "neutral"),
    ("{count}-day streak. Momentum is on your side.", "warm"),
    ("{count} days in a row — quietly excellent.", "brief"),
    ("The streak stands at {count} days.", "formal"),
    ("{count} straight days! Someone's on fire.", "playful"),
    ("Still going: {count} days consecutive.", "neutral"),
]
SNOOZE = [
    ("Snoozed until {until} — out of sight for now.", "neutral"),
    ("I'll remind you again {until}.", "brief"),
    ("Parked until {until}; it will resurface then.", "formal"),
    ("Okay, sleeping on it until {until}.", "playful"),
    ("Snoozed. Next appearance: {until}.", "brief"),
    ("Set aside until {until} — nothing lost.", "warm"),
    ("Deferred to {until} as requested.", "formal"),
    ("Snoozing that for now; back on {until}.", "neutral"),
    ("Tucked away until {until}.", "playful"),
    ("Reminder rescheduled to {until}.", "formal"),
    ("On ice until {until} — consider it handled.", "warm"),
    ("{until} it is. I'll bring it back then.", "neutral"),
    ("Snooze engaged; wakeup call {until}.", "playful"),
    ("Postponed to {until}, per your instruction.", "formal"),
    ("Quiet until {until}, then it returns.", "brief"),
]
QUIET_HOURS = [
    ("Quiet hours are on — holding non-urgent items.", "neutral"),
    ("Shh mode active; only critical alerts get through.", "playful"),
    ("Quiet hours in effect until {time}.", "brief"),
    ("Do-not-disturb window: I'll keep it down.", "warm"),
    ("Respecting quiet hours; summary will wait.", "formal"),
    ("Silent running until {time} — urgent only.", "brief"),
    ("Quiet hours observed. Nothing will ping you now.", "neutral"),
    ("Low-noise mode: collecting, not interrupting.", "warm"),
    ("Per your quiet-hours policy, this can wait.", "formal"),
    ("Muting the routine stuff until {time}.", "playful"),
]
HEADLINE = [
    ("Headline: {event}.", "brief"),
    ("Top story today: {event}.", "neutral"),
    ("If you remember one thing: {event}.", "warm"),
    ("The big item is {event}.", "formal"),
    ("Above the fold: {event}.", "playful"),
    ("Today's headline — {event}.", "neutral"),
    ("Leading with {event}.", "brief"),
    ("Front and center: {event}.", "warm"),
    ("Your day in one line: {event}.", "neutral"),
    ("The headline act is {event}.", "playful"),
    ("Priority one: {event}.", "formal"),
    ("First things first — {event}.", "neutral"),
    ("The one to watch: {event}.", "warm"),
    ("Banner item: {event}.", "formal"),
    ("Marquee today: {event}.", "playful"),
]
UMBRELLA = [
    ("Umbrella verdict: yes, take one.", "brief"),
    ("Bring the umbrella — rain is likely.", "neutral"),
    ("Umbrella recommended; showers are on the radar.", "formal"),
    ("Grab the brolly on your way out.", "playful"),
    ("Rain incoming — umbrella advised.", "warm"),
    ("No umbrella needed today; skies cooperate.", "neutral"),
    ("Leave the umbrella — dry all day.", "brief"),
    ("Umbrella optional; only a slight chance of rain.", "neutral"),
    ("Pack the compact umbrella just in case.", "warm"),
    ("Umbrella status: required equipment today.", "playful"),
]
CONFLICT = [
    ("Heads-up: {event} overlaps with {title}.", "neutral"),
    ("Scheduling conflict: {event} and {title} collide.", "formal"),
    ("Clash alert — {event} vs {title}.", "playful"),
    ("{event} conflicts with {title}; one may need to move.", "warm"),
    ("Double-booked: {event} and {title}.", "brief"),
    ("Calendar collision between {event} and {title}.", "neutral"),
    ("Two claims on the same slot: {event}, {title}.", "formal"),
    ("{event} runs into {title} — want me to suggest a fix?", "warm"),
    ("Overlap detected: {event} meets {title}.", "brief"),
    ("Uh-oh, {event} and {title} are fighting for the same hour.", "playful"),
]
VIP = [
    ("VIP alert: message from {sender}.", "neutral"),
    ("{sender} wrote — flagging as important.", "formal"),
    ("Important sender: {sender} is in your inbox.", "brief"),
    ("{sender} — that one's worth a fast reply.", "warm"),
    ("Priority mail from {sender} just landed.", "playful"),
    ("From your VIP list: {sender}.", "formal"),
    ("{sender} reached out; marked high-priority.", "neutral"),
    ("Don't miss this one — {sender}.", "warm"),
    ("{sender} (VIP) awaits your attention.", "formal"),
    ("Big-name sender spotted: {sender}.", "playful"),
]
NEXT_EVENT = [
    ("Next up: {event} at {time}.", "neutral"),
    ("Coming up next — {event}, {time}.", "brief"),
    ("Your next commitment is {event} at {time}.", "formal"),
    ("On deck: {event} at {time}.", "playful"),
    ("Next on the calendar: {event} ({time}).", "neutral"),
    ("{event} is next, starting {time}.", "brief"),
    ("Up next — {event}. You're on at {time}.", "warm"),
    ("The next item: {event}, scheduled {time}.", "formal"),
    ("Rolling into {event} at {time}.", "playful"),
    ("Next appointment: {event} at {time}.", "neutral"),
    ("{event} awaits — {time} start.", "brief"),
    ("Next in line: {event} at {time}. Plenty of time to prep.", "warm"),
    ("Following this: {event}, {time}.", "formal"),
    ("Queue position one: {event} at {time}.", "playful"),
    ("Then it's {event} at {time}.", "neutral"),
]
# ------------------------------------------- extra greeting/closing variety
GREETING_MORNING_EXTRA = [
    ("Good morning{name}! The kettle of productivity is on.", "playful"),
    ("Morning{name}! Priorities, weather, inbox — in that order if you like.", "neutral"),
    ("Good morning{name}. A calm start to a full day.", "warm"),
    ("Morning{name}. Your schedule, decoded.", "brief"),
    ("Good morning{name}! Small steps, big day.", "warm"),
    ("A bright morning to you{name}; briefing follows.", "formal"),
    ("Morning{name}! I've done the sorting so you don't have to.", "playful"),
    ("Good morning{name}! First coffee, then this.", "playful"),
    ("Morning{name} — the day in sixty seconds.", "brief"),
    ("Good morning{name}. Everything that matters, right here.", "formal"),
]
GREETING_EVENING_EXTRA = [
    ("Good evening{name}! Tomorrow's already queued up.", "neutral"),
    ("Evening{name}. Closing the books on today.", "formal"),
    ("Evening{name}! You survived — here's the proof.", "playful"),
    ("Good evening{name}. Tomorrow, previewed.", "brief"),
    ("Evening{name}! Let's put a bow on today.", "warm"),
    ("Good evening{name} — scores settled, plan made.", "playful"),
    ("Evening{name}. Your day, tallied.", "brief"),
    ("Good evening{name}! Rest well; the plan is ready.", "warm"),
]
CLOSING_LINE_EXTRA = [
    ("That's the lot — onwards.", "brief"),
    ("Consider yourself briefed. Go well.", "formal"),
    ("All squared away. Enjoy your day.", "warm"),
    ("Nothing else needs you right now.", "neutral"),
    ("That's everything — I'm on watch.", "playful"),
    ("Briefing complete. The day is yours.", "formal"),
    ("You know everything I know now.", "playful"),
    ("Wrapped up — ping me anytime.", "warm"),
    ("End of the list; start of the doing.", "playful"),
    ("That's all — make it a good one.", "warm"),
    ("Nothing further to report.", "formal"),
    ("All caught up. Carry on.", "brief"),
]
# fmt: on

# Flatten into the (category, text, tone) rows the builder consumes.
ENTRIES: list[tuple[str, str, str]] = (
    [("greeting_morning", *r) for r in GREETING_MORNING]
    + [("greeting_evening", *r) for r in GREETING_EVENING]
    + [("greeting_afternoon", *r) for r in GREETING_AFTERNOON]
    + [("greeting_general", *r) for r in GREETING_GENERAL]
    + [("section_header", *r) for r in SECTION_HEADER]
    + [("weather_report", *r) for r in WEATHER_REPORT]
    + [("weather_advice", *r) for r in WEATHER_ADVICE]
    + [("tasks_status", *r) for r in TASKS_STATUS]
    + [("email_status", *r) for r in EMAIL_STATUS]
    + [("draft_offer", *r) for r in DRAFT_OFFER]
    + [("draft_opener", *r) for r in (DRAFT_OPENER_FORMAL + DRAFT_OPENER_NEUTRAL
                                      + DRAFT_OPENER_WARM + DRAFT_OPENER_BRIEF)]
    + [("draft_closer", *r) for r in (DRAFT_CLOSER_FORMAL + DRAFT_CLOSER_NEUTRAL
                                      + DRAFT_CLOSER_WARM + DRAFT_CLOSER_BRIEF)]
    + [("signoff", *r) for r in SIGNOFF]
    + [("acknowledgment", *r) for r in ACKNOWLEDGMENT]
    + [("fallback", *r) for r in FALLBACK]
    + [("encouragement", *r) for r in ENCOURAGEMENT]
    + [("priority_frame", *r) for r in PRIORITY_FRAME]
    + [("offer", *r) for r in OFFER]
    + [("time_phrase", *r) for r in TIME_PHRASE]
    + [("approval_prompt", *r) for r in APPROVAL_PROMPT]
    + [("confirmation", *r) for r in CONFIRMATION]
    + [("transition", *r) for r in TRANSITION]
    + [("error_apology", *r) for r in ERROR_APOLOGY]
    + [("vocab_weather", *r) for r in VOCAB_WEATHER]
    + [("vocab_status", *r) for r in VOCAB_STATUS]
    + [("vocab_daypart", *r) for r in VOCAB_DAYPART]
    + [("number_word", *r) for r in NUMBER_WORD]
    + [("goodbye", *r) for r in GOODBYE]
    + [("thanks", *r) for r in THANKS]
    + [("apology", *r) for r in APOLOGY]
    + [("task_verb", *r) for r in TASK_VERB]
    + [("meeting_word", *r) for r in MEETING_WORD]
    + [("email_subject_template", *r) for r in EMAIL_SUBJECT_TEMPLATE]
    + [("briefing_intro", *r) for r in BRIEFING_INTRO]
    + [("wrapup_intro", *r) for r in WRAPUP_INTRO]
    + [("date_phrase", *r) for r in DATE_PHRASE]
    + [("deadline_phrase", *r) for r in DEADLINE_PHRASE]
    + [("nudge_phrase", *r) for r in NUDGE_PHRASE]
    + [("clarify_question", *r) for r in CLARIFY_QUESTION]
    + [("yes_no", *r) for r in YES_NO]
    + [("scheduling", *r) for r in SCHEDULING]
    + [("travel", *r) for r in TRAVEL]
    + [("focus", *r) for r in FOCUS]
    + [("triage_label", *r) for r in TRIAGE_LABEL]
    + [("sender_kind", *r) for r in SENDER_KIND]
    + [("urgency", *r) for r in URGENCY]
    + [("reaction_positive", *r) for r in REACTION_POSITIVE]
    + [("reaction_sympathy", *r) for r in REACTION_SYMPATHY]
    + [("reminder_phrase", *r) for r in REMINDER_PHRASE]
    + [("errand", *r) for r in ERRAND]
    + [("household", *r) for r in HOUSEHOLD]
    + [("finance", *r) for r in FINANCE]
    + [("health_appointment", *r) for r in HEALTH_APPOINTMENT]
    + [("congratulation", *r) for r in CONGRATULATION]
    + [("waiting", *r) for r in WAITING]
    + [("reschedule", *r) for r in RESCHEDULE]
    + [("season_word", *r) for r in SEASON_WORD]
    + [("holiday_word", *r) for r in HOLIDAY_WORD]
    + [("priority_word", *r) for r in PRIORITY_WORD]
    + [("gratitude", *r) for r in GRATITUDE]
    + [("summary_word", *r) for r in SUMMARY_WORD]
    + [("weekday_word", *r) for r in WEEKDAY_WORD]
    + [("month_word", *r) for r in MONTH_WORD]
    + [("closing_line", *r) for r in CLOSING_LINE]
    + [("opening_line", *r) for r in OPENING_LINE]
    + [("weekend", *r) for r in WEEKEND]
    + [("holiday", *r) for r in HOLIDAY]
    + [("streak", *r) for r in STREAK]
    + [("snooze", *r) for r in SNOOZE]
    + [("quiet_hours", *r) for r in QUIET_HOURS]
    + [("headline", *r) for r in HEADLINE]
    + [("umbrella", *r) for r in UMBRELLA]
    + [("conflict", *r) for r in CONFLICT]
    + [("vip", *r) for r in VIP]
    + [("next_event", *r) for r in NEXT_EVENT]
    + [("greeting_morning", *r) for r in GREETING_MORNING_EXTRA]
    + [("greeting_evening", *r) for r in GREETING_EVENING_EXTRA]
    + [("closing_line", *r) for r in CLOSING_LINE_EXTRA]
    + [("checklist_marker", *r) for r in CHECKLIST_MARKER]
)

CATEGORIES = sorted({cat for cat, _, _ in ENTRIES})

#: Every slot a template may reference. validate_slots() flags any template
#: using a name outside this set — a typo'd slot would render as a silent ''.
KNOWN_SLOTS = sorted({
    "name", "count", "temp", "unit", "chance", "cond", "title", "sender",
    "subject", "source", "reason", "time", "city", "streak", "date",
    "project", "minutes", "event", "limit", "holiday", "until",
})
