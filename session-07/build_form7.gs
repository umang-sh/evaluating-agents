/**
 * Session 7 — Google Form builder.
 *
 * Tools ▸ Script editor ▸ paste ▸ Run ▸ buildSession7Form
 * The execution log prints the EDIT url and the LIVE url.
 *
 * THREE THINGS THAT WILL BITE YOU (course gotcha #11, learned the hard way):
 *
 *  1. FormApp.create() makes a BRAND NEW FORM WITH A NEW URL every single run.
 *     It never updates an existing one. Run this ONCE, then edit in the UI.
 *
 *  2. TextValidationBuilder has NO setHelpText(). It appears in a sample on the
 *     docs page and is not a documented method; chaining it produces Apps
 *     Script's bare "An unknown error has occurred". Help text goes on the
 *     ITEM: item.setHelpText(...).
 *
 *  3. Numeric validation rejects a blank answer on a REQUIRED item only. Any
 *     field a student may legitimately have no number for is left optional.
 *
 * DESIGN RULE, from Session 2 onward: everything sortable is a dropdown or a
 * number. Paragraph boxes are capped at SIX for the whole form, because forty
 * paragraph answers is a reading job and forty dropdown answers is a chart.
 *
 * SECTION 2 EXISTS BECAUSE THE IN-CLASS HANDS-ON DID NOT LAND. Most pairs got
 * one row to DISCRIMINATING and almost nobody got both. The suspected cause is
 * HW-001: two traps stacked (a DECORATIVE machine id and a WRONG manual
 * section) and a file header that listed six section ids with no titles, so
 * picking between MAN-CONVEYOR-4.2 and -5.0 was a guess. That is a HYPOTHESIS.
 * Item 2.1 and 2.2 are there to test it rather than assume it -- if the wrong
 * verdicts cluster on HW-001/WRONG, the diagnosis holds; if they cluster on
 * DECORATIVE across both rows, the traps were not the problem and the teaching
 * was. Do not rewrite the exercise for Session 10 before reading those two.
 *
 * WHAT SESSION 8 TAKES FROM THIS FORM
 *   · item 2.1 (verdict per row) -> the class distribution of DECORATIVE
 *     assertions, sorted, as the Session 8 opener. One chart.
 *   · item 4.1 ("which failure would a judge catch that code cannot") -> the
 *     starting list of things an LLM judge is FOR. That is Session 8's whole
 *     subject, and this question is where its material comes from.
 *   · section 3 (a delegation row of their own) -> rows 13..n of the benchmark,
 *     which Sessions 9 and 12 inherit.
 *
 * Nothing in Session 8 may DEPEND on these submissions. Session 6's homework
 * was skipped and Session 7 still opened fine. Keep it that way.
 */

/**
 * ----------------------------------------------------------------------
 * updateSession7Form()  —  RUN THIS ONE IF THE LINK IS ALREADY OUT.
 * ----------------------------------------------------------------------
 * buildSession7Form() below CREATES A NEW FORM WITH A NEW URL. If the email
 * has already gone out, running it silently orphans every student who clicks
 * the old link. This function edits the EXISTING form in place, so the URL
 * does not move.
 *
 * HOW TO RUN
 *   1. Open the form you already sent, copy its URL from the address bar
 *      (either the /edit one or the /viewform one — both work).
 *   2. Paste it into FORM_URL below.
 *   3. Select updateSession7Form in the function dropdown ▸ Run.
 *   4. The log prints every change it made. It changes NOTHING else, and it
 *      touches no responses that have already come in.
 *
 * It is idempotent: running it twice is the same as running it once.
 */
var FORM_URL = 'PASTE_THE_FORM_URL_HERE';

function updateSession7Form() {
  if (FORM_URL.indexOf('docs.google.com') === -1) {
    throw new Error('Set FORM_URL to the form you already sent, first.');
  }
  var form = FormApp.openByUrl(FORM_URL);
  var changed = [], missing = [];

  // --- the description ---------------------------------------------------
  form.setDescription(
      'Due before Session 8.\n\n' +
      'ONE SUBMISSION PER STUDENT. If you worked in a pair in class, you still ' +
      'submit separately, in your own words.\n\n' +
      'Name and roll number only — no email addresses. If you submit twice I keep ' +
      'the latest by roll number.\n\n' +
      'A DECORATIVE verdict is not a bad grade. It is the screener telling you your ' +
      'assertion cannot fail. Report it honestly — I am grading whether you read it, ' +
      'not whether you got it right first time.');
  changed.push('description');

  // --- retitle the two identity fields -----------------------------------
  // Matched by title, and the OLD title is accepted as well as the new one so
  // that a second run is a no-op rather than a failure.
  var RETITLE = [['Name(s)', 'Name'], ['Roll number(s)', 'Roll number']];
  var items = form.getItems(FormApp.ItemType.TEXT);
  RETITLE.forEach(function (pair) {
    var from = pair[0], to = pair[1], hit = null;
    for (var i = 0; i < items.length; i++) {
      var t = items[i].getTitle();
      if (t === from || t === to) { hit = items[i]; break; }
    }
    if (!hit) { missing.push(from); return; }
    if (hit.getTitle() !== to) { hit.setTitle(to); changed.push(from + ' -> ' + to); }
  });

  // --- section 1 help text -----------------------------------------------
  var heads = form.getItems(FormApp.ItemType.SECTION_HEADER);
  var found1 = false;
  for (var j = 0; j < heads.length; j++) {
    if (heads[j].getTitle().indexOf('1 · Who') === 0) {
      heads[j].asSectionHeaderItem().setHelpText(
          'One submission per student. You may have worked in a pair in class — ' +
          'still submit separately, in your own words.');
      changed.push('section 1 help text');
      found1 = true;
    }
  }
  if (!found1) missing.push('section header "1 · Who"');

  Logger.log('FORM : %s', form.getPublishedUrl());
  Logger.log('EDIT : %s', form.getEditUrl());
  Logger.log('CHANGED (%s): %s', changed.length, changed.join(' · '));
  if (missing.length) {
    Logger.log('!! NOT FOUND, fix by hand in the UI: %s', missing.join(' · '));
  } else {
    Logger.log('Nothing else was touched. Responses already submitted are unaffected.');
  }
}


// DANGER: creates a NEW form with a NEW URL. Do not run this once the email
// has gone out -- use updateSession7Form() above instead.
function buildSession7Form() {
  var form = FormApp.create('Session 7 — Evaluating Multi-Agent Systems (homework)');

  form.setDescription(
      'Due before Session 8.\n\n' +
      'ONE SUBMISSION PER STUDENT. If you worked in a pair in class, you still ' +
      'submit separately.\n\n' +
      'Name and roll number only — no email addresses. If you submit twice I keep ' +
      'the latest by roll number.\n\n' +
      'A DECORATIVE verdict is not a bad grade. It is the screener telling you your ' +
      'assertion cannot fail. Report it honestly — I am grading whether you read it, ' +
      'not whether you got it right first time.');

  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);
  form.setProgressBar(true);
  form.setShowLinkToRespondAgain(false);

  var VERDICTS = ['DISCRIMINATING (pass / fail)',
                  'DECORATIVE (pass / pass)',
                  'WRONG (fail / fail)',
                  'INVERTED (fail / pass)'];
  var EVALUATORS = ['delegation_accuracy',
                    'handoff_integrity',
                    'agent_no_redundancy',
                    'no_delegation_loop',
                    'outcome_match',
                    'none of them — a human would have to read it'];

  // ---------------------------------------------------------------- 1. WHO
  form.addSectionHeaderItem()
      .setTitle('1 · Who')
      .setHelpText('One submission per student. You may have worked in a pair in class — \n' +
                   'still submit separately, in your own words.');

  form.addTextItem().setTitle('Name').setRequired(true);
  form.addTextItem().setTitle('Roll number').setRequired(true);

  // --------------------------------------- 2. WHAT HAPPENED IN CLASS
  form.addPageBreakItem()
      .setTitle('2 · The two rows from class')
      .setHelpText(
          'HW-001 and HW-003, finished. git pull first — my_handoffs7.py now has ' +
          'the worked example and the manual sections with their titles.\n\n' +
          'Answer 2.1 and 2.2 about your FIRST attempt in class, honestly. Nothing ' +
          'here is graded on getting it right; it is how I find out whether the ' +
          'exercise or the explanation was at fault.');

  form.addMultipleChoiceItem()
      .setTitle('2.1 · HW-001 — the verdict on your FIRST attempt, in class')
      .setChoiceValues(VERDICTS.concat(['I did not get it to run at all']))
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('2.2 · HW-003 — the verdict on your FIRST attempt, in class')
      .setChoiceValues(VERDICTS.concat(['I did not get it to run at all']))
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('2.3 · If a row came back WRONG, which string was the screener ' +
                'unable to find?')
      .setChoiceValues([
        'MAN-CONVEYOR-5.0 — I asserted the limits table, not the procedure',
        'both conveyor sections at once',
        'a manual section on the diagnostics->documentation edge',
        'something else',
        'no row came back WRONG'])
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('2.4 · Both rows DISCRIMINATING now?')
      .setChoiceValues([
        'Yes — both',
        'HW-001 only',
        'HW-003 only',
        'Neither — say what is still happening in 5.3'])
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('2.5 · What made the difference the second time?')
      .setChoiceValues([
        'the worked example at the top of my_handoffs7.py',
        'the manual sections having titles',
        'reading the string the screener said it could not find',
        'the two traps being named in the homework email',
        'nothing — I had it in class'])
      .showOtherOption(true)
      .setRequired(true);

  // ------------------------------------------------ 3. THE TWO ASSERTIONS
  form.addPageBreakItem()
      .setTitle('3 · Two more handoff assertions')
      .setHelpText(
          'In my_handoffs7.py, add HW-002 (the rinse-water pump) and HW-005 ' +
          '(the air-knife blower). ' +
          'Write predict BEFORE you run the screener. Then run:\n\n' +
          '    python screen_my_handoffs.py\n\n' +
          'Report what it actually said, not what you meant.');

  form.addMultipleChoiceItem()
      .setTitle('3.1 · HW-002 — verdict from the screener')
      .setChoiceValues(VERDICTS)
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('3.2 · HW-005 — verdict from the screener')
      .setChoiceValues(VERDICTS)
      .setRequired(true);

  var firstTry = form.addTextItem()
      .setTitle('3.3 · Across all four rows, how many were DECORATIVE on the first attempt?')
      .setRequired(true);
  firstTry.setHelpText('A number, 0 to 4. HW-001, HW-003, HW-002, HW-005.');
  firstTry.setValidation(FormApp.createTextValidation()
      .requireNumberBetween(0, 4).build());

  form.addParagraphTextItem()   // paragraph 1 of 6
      .setTitle('3.4 · Paste the exact fact strings you ended up asserting for HW-005')
      .setHelpText('One per line, in the form  edge : fact   e.g.  diagnostics->documentation : IMBALANCE')
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('3.5 · HW-005 is the row whose correct answer is "do nothing". Which fact ' +
                'does the maintenance agent need in order to justify doing nothing?')
      .setChoiceValues([
        'the fault code, IMBALANCE',
        'the manual section MAN-BLOWER-3.4 (the G6.3 balance criterion)',
        'the measured vibration, 4.2 mm/s',
        'the machine id'])
      .setRequired(true);

  // ------------------------------------------------ 3. A ROW OF YOUR OWN
  form.addPageBreakItem()
      .setTitle('4 · One delegation row of your own')
      .setHelpText(
          'Write a request for Halvard Works that you believe the four-agent pipeline ' +
          'gets WRONG — a path it takes that it should not. Run it (impl="stub" is free) ' +
          'and report what happened.\n\n' +
          'The best rows join the benchmark and are inherited by Sessions 9 and 12, ' +
          'with your name on them.');

  form.addParagraphTextItem()   // paragraph 2 of 6
      .setTitle('4.1 · Your request, exactly as you would type it')
      .setRequired(true);

  form.addTextItem()
      .setTitle('4.2 · The path you EXPECTED (expected_agents)')
      .setHelpText('e.g.  planner -> diagnostics')
      .setRequired(true);

  form.addTextItem()
      .setTitle('4.3 · The path you actually GOT')
      .setHelpText('Copy it from the output of run_pipeline.')
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('4.4 · Which evaluator caught it?')
      .setChoiceValues(EVALUATORS)
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('4.5 · Did the pipeline still produce the RIGHT final answer?')
      .setChoiceValues(['Yes — right answer, wrong path',
                        'No — the path error changed the answer',
                        'Partly — right fault code, wrong recommendation'])
      .setRequired(true);

  // ------------------------------------------------ 4. FEEDS SESSION 8
  form.addPageBreakItem()
      .setTitle('5 · What code cannot check')
      .setHelpText('Every evaluator this session was code. Next session builds judges.');

  form.addMultipleChoiceItem()
      .setTitle('5.1 · Which of these could an LLM judge assess that none of today\'s ' +
                'code-based evaluators can?')
      .setChoiceValues([
        'whether the diagnosis was actually correct, not just present',
        'whether the maintenance recommendation was safe',
        'whether the documentation agent quoted the RELEVANT part of the manual',
        'whether the planner\'s subtask wording was clear enough to act on',
        'whether the four reports contradict each other'])
      .showOtherOption(true)
      .setRequired(true);

  form.addParagraphTextItem()   // paragraph 3 of 6
      .setTitle('5.2 · In one or two sentences: what would you have to give that judge ' +
                'so that its verdict could be checked?')
      .setHelpText('Session 1: give it ground truth, or read the trajectory — ideally both.')
      .setRequired(true);

  form.addMultipleChoiceItem()
      .setTitle('5.3 · A loop and a redundant call both fire agent_no_redundancy. Is that ' +
                'a bug in the evaluators?')
      .setChoiceValues([
        'No — a loop IS a kind of redundancy; the categories overlap',
        'Yes — each failure should have exactly one evaluator',
        'No, but only because we gate on "caught by its designated evaluator"',
        'I am not sure'])
      .setRequired(true);

  // ------------------------------------------------ 5. TRACE + FRICTION
  form.addPageBreakItem().setTitle('6 · Evidence and friction');

  var url = form.addTextItem()
      .setTitle('6.1 · A LangSmith trace URL from your own workspace')
      .setRequired(false);
  url.setHelpText('From `python replay7.py`, or from a live run if you spent your own key. ' +
                  'Optional. The script prints YOUR link as its last line — the dataset is in your \n' +
                  'own workspace, so there is no shared URL. Say below if it did not work.');
  url.setValidation(FormApp.createTextValidation().requireTextIsUrl().build());

  form.addMultipleChoiceItem()
      .setTitle('6.2 · Did replay7.py work?')
      .setChoiceValues([
        'Yes — experiments are in my workspace',
        'No — LANGSMITH_API_KEY problem',
        'No — something else (say below)',
        'I did not try it'])
      .setRequired(true);

  form.addParagraphTextItem()   // paragraph 4 of 6
      .setTitle('6.3 · Anything that cost you more than ten minutes')
      .setHelpText('Environment, imports, the screener, the notebook. Be specific — this is ' +
                   'the fastest way to get it fixed for everyone. If a row is still not ' +
                   'DISCRIMINATING, paste the screener line here.')
      .setRequired(false);

  Logger.log('EDIT: %s', form.getEditUrl());
  Logger.log('LIVE: %s', form.getPublishedUrl());
  Logger.log('Paragraph items used: 4 of the 6 allowed. Sections: 6.');
}
