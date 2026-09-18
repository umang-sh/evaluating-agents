/**
 * Session 8 — Google Form builder.
 *
 * Tools ▸ Script editor ▸ paste ▸ Run ▸ buildSession8Form
 * The execution log prints the EDIT url and the LIVE url.
 *
 * THREE THINGS THAT WILL BITE YOU (course gotcha #11, learned the hard way):
 *
 *  1. FormApp.create() makes a BRAND NEW FORM WITH A NEW URL every single run.
 *     It never updates an existing one. Run this ONCE, then edit in the UI, or
 *     use retitleSession8Form() below if the link is already out.
 *
 *  2. TextValidationBuilder has NO setHelpText(). Chaining it produces Apps
 *     Script's bare "An unknown error has occurred". Help text goes on the
 *     ITEM: item.setHelpText(...).
 *
 *  3. Numeric validation rejects a blank answer on a REQUIRED item only. Any
 *     field a student may legitimately have no number for is left optional.
 *
 * DESIGN RULE, from Session 2 onward: everything sortable is a dropdown or a
 * number. Paragraph boxes are capped at SIX for the whole form, because forty
 * paragraph answers is a reading job and forty dropdown answers is a chart.
 * This form uses exactly six.
 *
 * WHAT THIS FORM IS ACTUALLY FOR, AND IT IS NOT MARKS
 * ---------------------------------------------------
 * Session 8 shipped a negative result (two of four judges not usable) and a
 * hands-on that everybody loses. Both were measured on ONE model. Three
 * providers ran in that room. Section 4 is the only instrument this course has
 * for the question "is the finding about judges, or about claude-sonnet-5?",
 * and it is the reason section 4 asks for intervals rather than percentages.
 *
 * Section 5 is the second instrument. The human column on SLIDE 20 is one
 * rater, not an expert, with no inter-rater agreement measured — that caveat is
 * printed on the slide. Item 5.3 makes the class the second rater. Whatever the
 * agreement distribution comes to goes on a slide in Session 9, including if it
 * is bad. Do not quietly drop it if it is bad; that is the failure mode this
 * course spends twelve weeks on.
 *
 * WHAT SESSION 9 TAKES FROM THIS FORM
 *   · item 4.2 (which judges cleared the gate, by provider) -> the opener. One
 *     chart, split by provider, with the Session 8 ordering drawn behind it.
 *   · item 5.3 (agreement with my labels, 0-3) -> the inter-rater number.
 *   · item 6.1 (what a judge can tell you about a PATH) -> Session 9's subject
 *     list, in the students' own words, exactly as 5.1 on the Session 7 form
 *     became Session 8's subject list.
 *
 * Nothing in Session 9 may DEPEND on these submissions. Session 6's homework
 * was skipped and Session 7 still opened fine. Keep it that way.
 */

var ATTACK_VERDICTS = [
  'FOOLED — the judge passed a report that is still broken',
  'NO-EFFECT — the judge held, my edit did not move it',
  'COLLATERAL — a DIFFERENT judge fired instead',
  'REPAIRED — I removed the flaw, so there was nothing to fool',
  'NO BASELINE — the judge did not convict the untouched report either',
  'I did not get it to run at all'
];

var JUDGES = [
  'doc_relevance',
  'recommendation_safety',
  'diagnosis_soundness',
  'workflow_coherence'
];

var PROVIDERS = ['anthropic', 'openai', 'google'];

/**
 * ----------------------------------------------------------------------
 * retitleSession8Form()  —  RUN THIS ONE IF THE LINK IS ALREADY OUT.
 * ----------------------------------------------------------------------
 * buildSession8Form() CREATES A NEW FORM WITH A NEW URL. If the email has
 * gone out, running it silently orphans every student who clicks the old
 * link. This edits the EXISTING form's title, description and deadline in
 * place, touching nothing else and no submitted responses. It is idempotent.
 */
var FORM_URL = 'PASTE_THE_FORM_URL_HERE';

function retitleSession8Form() {
  if (FORM_URL.indexOf('docs.google.com') === -1) {
    throw new Error('Set FORM_URL to the form you already sent, first.');
  }
  var form = FormApp.openByUrl(FORM_URL);
  form.setTitle('Session 8 — LLM-as-a-Judge: homework');
  form.setDescription(DESCRIPTION);
  Logger.log('Retitled in place. URL unchanged: %s', form.getPublishedUrl());
}

var DESCRIPTION =
    'Due before Session 9.\n\n' +
    'ONE SUBMISSION PER STUDENT. If you worked in a pair in class, you still ' +
    'submit separately, in your own words.\n\n' +
    'Name and roll number only — no email addresses. If you submit twice I keep ' +
    'the later one.\n\n' +
    'SECTION 4 COSTS MODEL CALLS (about 88, on your own key). Everything else ' +
    'is free. If section 4 fails for you, say so in 4.5 and skip it — nothing ' +
    'later depends on it.\n\n' +
    'A FOOLED verdict is the expected outcome of the hands-on, not a bad grade. ' +
    'A NO-EFFECT is data. Report what the screener said, whatever it said.';


function buildSession8Form() {
  var form = FormApp.create('Session 8 — LLM-as-a-Judge: homework');
  form.setDescription(DESCRIPTION);
  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);
  form.setProgressBar(true);

  // --------------------------------------------------------- 1. WHO
  form.addPageBreakItem()
      .setTitle('1 · Who')
      .setHelpText('One submission per student. You may have worked in a pair in class — \n' +
                   'still submit separately, in your own words.');

  form.addTextItem().setTitle('Name').setRequired(true);
  form.addTextItem().setTitle('Roll number').setRequired(true);

  // ------------------------------------------ 2. THE ATTACK FROM CLASS
  form.addPageBreakItem()
      .setTitle('2 · The attack you started in class')
      .setHelpText(
          'my_attack8.py, PREDICT filled in BEFORE you ran anything, then:\n\n' +
          '    python screen_my_attack.py\n\n' +
          'EIGHT model calls per run — four judges on the untouched broken report, ' +
          'four on yours. The baseline is re-measured live every time, because ' +
          'comparing your attempt against last night\'s verdict is comparing two ' +
          'coin flips and calling the difference your work.');

  form.addMultipleChoiceItem()
      .setTitle('2.1 · Which broken report did you attack first?')
      .setChoiceValues([
        'wrong_section — it cites MAN-CONVEYOR-5.0, the vibration limits TABLE, as the basis for a bearing replacement',
        'unsafe_action — it recommends four more weeks of monitoring on a bearing at its 72 C alarm limit'])
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('2.2 · The verdict on your FINAL attempt')
      .setChoiceValues(ATTACK_VERDICTS)
      .setRequired(true);

  var tries = form.addTextItem()
      .setTitle('2.3 · How many attempts did it take to reach that verdict?')
      .setRequired(true);
  tries.setHelpText('A number, 1 to 20. Count every time you ran the screener.');
  tries.setValidation(FormApp.createTextValidation()
      .requireNumberBetween(1, 20).build());

  form.addMultipleChoiceItem()
      .setTitle('2.4 · Which of these did your winning edit actually do?')
      .setHelpText('If you got NO-EFFECT, pick what you tried hardest.')
      .setChoiceValues([
        'stated the conclusion more assertively, and earlier',
        'added a sentence that SOUNDS like corroboration and is not',
        'quoted a real number from the equipment record that is true but irrelevant',
        'buried the flaw in the middle of a long, correct paragraph',
        'made the report much longer without adding anything false'])
      .showOtherOption(true)
      .setRequired(true);

  form.addParagraphTextItem()   // paragraph 1 of 6
      .setTitle('2.5 · Paste the judge\'s TWO comment lines — baseline, then yours')
      .setHelpText('The screener prints both. The judge\'s own stated reason for changing ' +
                   'its mind is the finding; the verdict on its own is not.')
      .setRequired(true);

  // ------------------------------------------------ 3. THE OTHER TARGET
  form.addPageBreakItem()
      .setTitle('3 · The other target')
      .setHelpText(
          'You attacked one of wrong_section / unsafe_action. Do the other.\n\n' +
          'wrong_section attacks a RELEVANCE judgement: does the cited manual ' +
          'section answer THIS fault?\n' +
          'unsafe_action attacks a RISK judgement: is the recommended action safe ' +
          'given what the report itself says?\n\n' +
          'Write down which you expect to be harder BEFORE you run it.');

  form.addMultipleChoiceItem()
      .setTitle('3.1 · Before running it, which did you expect to be harder to fool?')
      .setChoiceValues([
        'wrong_section — the relevance judgement',
        'unsafe_action — the risk judgement',
        'I expected no difference'])
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('3.2 · The verdict on the second target')
      .setChoiceValues(ATTACK_VERDICTS)
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('3.3 · Were you right about which was harder?')
      .setChoiceValues([
        'Yes — the one I predicted took more attempts',
        'No — the other one was harder',
        'Neither — both took about the same',
        'I could not fool either one'])
      .setRequired(true);

  form.addParagraphTextItem()   // paragraph 2 of 6
      .setTitle('3.4 · What is the difference between the two judges, in one or two sentences?')
      .setHelpText('Not which is harder — WHY. What is each one keying on that the other is not?')
      .setRequired(true);

  // ------------------------------- 4. THE MEASUREMENT ON YOUR PROVIDER
  form.addPageBreakItem()
      .setTitle('4 · The measurement, on your provider')
      .setHelpText(
          'Every number on the slides came from claude-sonnet-5. Run the same ' +
          'measurement on yours:\n\n' +
          '    python judge_bench8.py --live --wobble 5 --save my_runs8.json\n' +
          '    python agree8.py my_runs8.json\n\n' +
          '!! --save my_runs8.json, NOT the default. With no filename it overwrites ' +
          'judge_runs8.json, which is the measured file the notebook and deck read.\n\n' +
          'COST: 28 separation verdicts + 60 wobble verdicts = 88 calls on your key, ' +
          'about 5-7 minutes. It is the largest spend all term and it buys the one ' +
          'thing the slides cannot give you.');

  form.addMultipleChoiceItem()
      .setTitle('4.1 · Which provider are you on?')
      .setChoiceValues(PROVIDERS)
      .setRequired(true);

  var cleared = form.addCheckboxItem()
      .setTitle('4.2 · Which judges CLEARED THE GATE on your provider?');
  cleared.setChoiceValues(JUDGES.concat(['none of them']));
  cleared.setHelpText('Cleared the gate = separation lower bound above wobble upper bound. ' +
                      'agree8.py prints both. Ours: doc_relevance and recommendation_safety ' +
                      'cleared; diagnosis_soundness and workflow_coherence did not.');
  cleared.setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('4.3 · Did the ORDERING hold?')
      .setHelpText('The ordering is what should survive a change of model. The percentages ' +
                   'will not. If your two usable judges are a different two, that is the most ' +
                   'interesting single result anyone can send me this week.')
      .setChoiceValues([
        'Yes — the same two cleared, the same two did not',
        'Partly — one judge moved sides',
        'No — a different set cleared entirely',
        'I could not tell — every interval overlapped'])
      .setRequired(true);

  var fa = form.addTextItem()
      .setTitle('4.4 · Your workflow_coherence false-alarm count, out of 15')
      .setRequired(false);
  fa.setHelpText('How many reports it fired on that it should have passed. Ours was 8 of 15. ' +
                 'Leave blank if you skipped section 4.');
  fa.setValidation(FormApp.createTextValidation()
      .requireNumberBetween(0, 15).build());

  form.addMultipleChoiceItem()
      .setTitle('4.5 · Did section 4 run?')
      .setChoiceValues([
        'Yes — my_runs8.json and agree8.py both worked',
        'No — rate limit',
        'No — key or package problem',
        'No — something else (say in 7.2)',
        'I chose not to spend the calls'])
      .setRequired(true);

  form.addParagraphTextItem()   // paragraph 3 of 6
      .setTitle('4.6 · Report ONE judge properly: its separation and its wobble, with intervals')
      .setHelpText('Do not send me a percentage without the interval next to it. agree8.py ' +
                   'prints both. Pick whichever judge you found most interesting and say why ' +
                   'in one sentence. Leave blank if you skipped section 4.')
      .setRequired(false);

  // ---------------------------------------------- 5. THE HUMAN COLUMN
  form.addPageBreakItem()
      .setTitle('5 · The human column — you are the second rater')
      .setHelpText(
          '    python human_labels8.py --blind\n\n' +
          'Five run-instances across three rows where the pipeline recommended ' +
          'something real and the benchmark wanted something else. Computed from ' +
          'Session 7\'s own runs, not typed by me.\n\n' +
          '--blind HIDES MY LABELS. Write your own verdicts first, then run it ' +
          'again without --blind. A verdict you formed after reading mine measures ' +
          'nothing.\n\n' +
          'The slide says our human column is one rater, not a maintenance ' +
          'engineer, no second opinion, no inter-rater agreement measured. You are ' +
          'the fix for exactly one of those.');

  form.addMultipleChoiceItem()
      .setTitle('5.1 · HW-006 — your verdict (agent monitored; benchmark wanted replace)')
      .setChoiceValues([
        'agent — the agent was right and the benchmark row is wrong',
        'benchmark — the benchmark was right and the agent was wrong',
        'neither — genuinely ambiguous, both defensible'])
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('5.2 · HW-011 — your verdict (agent recommended replace; benchmark wanted no action)')
      .setChoiceValues([
        'agent — the agent was right and the benchmark row is wrong',
        'benchmark — the benchmark was right and the agent was wrong',
        'neither — genuinely ambiguous, both defensible'])
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('5.3 · HW-010 — your verdict (a stock-and-price question; the agent produced a work order)')
      .setChoiceValues([
        'agent — the agent was right and the benchmark row is wrong',
        'benchmark — the benchmark was right and the agent was wrong',
        'neither — genuinely ambiguous, both defensible'])
      .setRequired(true);

  var agree = form.addTextItem()
      .setTitle('5.4 · Having now read mine — on how many of the three did we agree?')
      .setRequired(true);
  agree.setHelpText('A number, 0 to 3. This number, across the class, is the inter-rater ' +
                    'agreement this course has never had. It goes on a slide in Session 9 ' +
                    'whatever it comes to.');
  agree.setValidation(FormApp.createTextValidation()
      .requireNumberBetween(0, 3).build());

  form.addParagraphTextItem()   // paragraph 4 of 6
      .setTitle('5.5 · Your one sentence of reasoning for the row we disagreed on')
      .setHelpText('If we agreed on all three, take the one you found hardest. The sentence ' +
                   'is the graded part: a verdict with no reasoning is unreadable next to a ' +
                   'judge\'s verdict, and that comparison is why Session 8 exists.')
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('5.6 · Given one rater and no second opinion, what is the honest claim you ' +
                'can make from a human column like ours?')
      .setHelpText('It is not "none" and it is not "it is ground truth".')
      .setChoiceValues([
        'It shows the cases exist and are real disagreements — it does not settle any of them',
        'It is a hypothesis about what an engineer would say, with a sample size of one',
        'It is enough to claim the benchmark has errors in it, but not how many',
        'It is only usable as a tie-break where the judge and the code already agree'])
      .showOtherOption(true)
      .setRequired(true);

  // ----------------------------------------------- 6. FEEDS SESSION 9
  form.addPageBreakItem()
      .setTitle('6 · What we judged, and what we did not')
      .setHelpText('Everything judged this session was a FINISHED REPORT — the thing at the ' +
                   'end. Session 9 judges the PATH: which agent ran, in what order, how many ' +
                   'times, and what it cost.');

  form.addMultipleChoiceItem()
      .setTitle('6.1 · Which of these can only be seen in the path, never in the final report?')
      .setChoiceValues([
        'the pipeline called the same tool four times with the same arguments',
        'the planner delegated to an agent that had nothing to contribute',
        'the diagnosis contradicts the documentation section cited',
        'the run cost nine times what an equivalent run cost',
        'the maintenance agent answered before diagnostics had finished'])
      .showOtherOption(true)
      .setRequired(true);

  form.addParagraphTextItem()   // paragraph 5 of 6
      .setTitle('6.2 · One thing a judge could tell you about a TRAJECTORY that it cannot ' +
                'tell you about the final answer')
      .setHelpText('Your own words. These answers open Session 9, the same way the last ' +
                   'question on the Session 7 form opened this one.')
      .setRequired(true);

  // ------------------------------------------------------ 7. FRICTION
  form.addPageBreakItem().setTitle('7 · Friction');

  form.addMultipleChoiceItem()
      .setTitle('7.1 · Did you have to switch provider or fix your .env at any point?')
      .setChoiceValues([
        'No — it worked from the start',
        'Yes — and the [PROVIDER] cell told me exactly what to paste',
        'Yes — and I had to work it out myself',
        'Yes — and I forgot to restart the kernel, which cost me time'])
      .setRequired(true);

  form.addParagraphTextItem()   // paragraph 6 of 6
      .setTitle('7.2 · Anything that cost you more than ten minutes')
      .setHelpText('Environment, imports, the screener, rate limits, the notebook. Be ' +
                   'specific — this is the fastest way to get it fixed for everyone.')
      .setRequired(false);

  Logger.log('EDIT: %s', form.getEditUrl());
  Logger.log('LIVE: %s', form.getPublishedUrl());
  Logger.log('Paragraph items used: 6 of the 6 allowed. Sections: 7.');
}
