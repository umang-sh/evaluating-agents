/**
 * Session 5 — Google Form builder.
 *
 * Tools ▸ Script editor ▸ paste ▸ Run ▸ buildSession5Form
 * The execution log prints the EDIT url and the LIVE url.
 *
 * THREE THINGS THAT WILL BITE YOU (course gotcha #11, learned the hard way):
 *
 *  1. FormApp.create() makes a BRAND NEW FORM WITH A NEW URL every single run.
 *     It never updates an existing one. Run this twice and you have two forms
 *     and half your class in the wrong one. Run it ONCE, then edit in the UI.
 *
 *  2. TextValidationBuilder has NO setHelpText(). It appears in a sample on the
 *     docs page and is not a documented method; chaining it produces Apps
 *     Script's bare "An unknown error has occurred", which tells you nothing.
 *     Help text goes on the ITEM: item.setHelpText(...).
 *
 *  3. Numeric validation rejects a blank answer on a REQUIRED item only. Any
 *     field a student may legitimately have no number for is left optional.
 *
 * DESIGN RULE, from Session 2 onward: everything sortable is a dropdown or a
 * number. Paragraph boxes are capped at SIX for the whole form, because forty
 * paragraph answers is a reading job and forty dropdown answers is a chart.
 *
 * The Session 6 opener comes from item 3.2 — "which field did the work" —
 * as a single distribution chart. Do not remove it.
 */

function buildSession5Form() {
  var form = FormApp.create('Session 5 — Benchmark Suites (homework)');

  form.setDescription(
      'Due before Session 6.\n\n' +
      'Name and roll number only — no email addresses. If you submit twice I keep ' +
      'the latest by roll number.\n\n' +
      'A RETIRE verdict is not a bad grade. It is the screener naming the bet your ' +
      'row failed to make. Report it honestly — I am grading whether you read it.');

  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);
  form.setProgressBar(true);
  form.setShowLinkToRespondAgain(false);

  // ---------------------------------------------------------------- 1. WHO
  form.addSectionHeaderItem()
      .setTitle('1 · Who')
      .setHelpText('Roll number is how submissions are matched. Get it right.');

  form.addTextItem()
      .setTitle('Name')
      .setRequired(true);

  var roll = form.addTextItem()
      .setTitle('Roll number')
      .setRequired(true);
  roll.setHelpText('Exactly as it appears on the class list.');

  form.addTextItem()
      .setTitle("Partner's roll number (blank if you worked alone)")
      .setRequired(false);

  // -------------------------------------------------------- 2. THE ROWS
  form.addPageBreakItem()
      .setTitle('2 · Your rows')
      .setHelpText('From `python screen_my_rows.py`. Numbers first, prose last.');

  var shipped = form.addTextItem()
      .setTitle('How many of your rows SHIP?')
      .setRequired(true);
  shipped.setHelpText('A whole number. Count only SHIPS — not RETIRE, not BROKEN.');
  shipped.setValidation(
      FormApp.createTextValidation()
          .requireNumberBetween(0, 20)
          .build());

  var retired = form.addTextItem()
      .setTitle('How many RETIREd on your first attempt?')
      .setRequired(true);
  retired.setHelpText(
      'Before you fixed them. This is not a mark against you — a room where ' +
      'nobody RETIREd on the first try means the screener is broken.');
  retired.setValidation(
      FormApp.createTextValidation()
          .requireNumberBetween(0, 20)
          .build());

  form.addMultipleChoiceItem()
      .setTitle('Which category did you write your NEW rows in?')
      .setChoiceValues(['browser_search', 'retrieval', 'multi_hop', 'report_gen',
                        'adversarial', 'conflicting_evidence', 'ambiguous_instruction'])
      .setRequired(true);

  // ---- THE SESSION 6 OPENER. One chart. Do not remove. ----
  var field = form.addMultipleChoiceItem();
  field.setTitle('In your BEST row, which field did the work?')
       .setChoiceValues(['must_contain — the answer bet',
                         'expected_tools — the routing bet',
                         'forbidden_tools — the safety bet',
                         'max_tool_calls — the waste bet'])
       .setRequired(true);
  field.setHelpText(
      'The field whose failure the screener actually attributed to your row. ' +
      'If you are not sure, re-read the "bets that pay off" line in the output.');

  // ---- HANDS-ON 1's actual product. A row you cannot be wrong about teaches
  //      nothing, so the prediction is what gets graded, not the row. ----
  var missed = form.addTextItem()
      .setTitle('How many of your rows did you predict WRONG?')
      .setRequired(true);
  missed.setHelpText(
      'The MISS count from `python screen_my_rows.py`. Zero is a legitimate ' +
      'answer and so is "all of them" — I am not grading the number, I am ' +
      'grading whether you wrote a prediction down before you ran it.');
  missed.setValidation(
      FormApp.createTextValidation()
          .requireNumberBetween(0, 20)
          .build());

  form.addParagraphTextItem()
      .setTitle('If you missed one: what did you assume that turned out not to be true?')
      .setHelpText(
          'One sentence. "I thought forbidden_tools was optional." ' +
          '"I thought a repeated query counted as my catch." If every row HIT, ' +
          'say instead which failure shape your rows still do not cover.')
      .setRequired(true);

  var caught = form.addCheckboxItem();
  caught.setTitle('Which failure shapes do your rows catch, between them?')
        .setChoiceValues(['wrong_tool', 'empty_search', 'injected'])
        .setRequired(true);
  caught.setHelpText(
      'Attributable shapes only. `redundant` is caught for free by every row and ' +
      'is deliberately not on this list — if that annoys you, you understood the block.');

  form.addMultipleChoiceItem()
      .setTitle('Did your rows make it into the pooled dataset?')
      .setChoiceValues(['Yes — pushed and tagged in class (v1)',
                        'Yes — pushed after class (v2)',
                        'No — screener still says RETIRE',
                        'No — I could not get push_pool.py to run'])
      .setRequired(true);

  // --------------------------------------------------- 3. SAMPLE SIZE
  form.addPageBreakItem()
      .setTitle('3 · How many runs can you afford?')
      .setHelpText(
          'From `python n_for.py`. The expected answer to the last question is ' +
          '"no". Say so — I am grading whether you say it rather than quietly ' +
          'rounding down.');

  var claim = form.addTextItem()
      .setTitle('The claim you would want to make, in one sentence')
      .setRequired(true);
  claim.setHelpText(
      'e.g. "version B uses 10% fewer tokens than version A". It must contain a ' +
      'number — a claim without a magnitude has no delta and cannot be costed.');

  var sigma = form.addTextItem()
      .setTitle('The sigma you used')
      .setRequired(true);
  sigma.setHelpText('Yours if you measured it. Ours (2444) if you did not.');
  sigma.setValidation(
      FormApp.createTextValidation()
          .requireNumber()
          .build());

  var delta = form.addTextItem()
      .setTitle('The delta you were trying to detect')
      .setRequired(true);
  delta.setHelpText(
      'Same units as sigma. A 10% claim on a mean of 6174 is a delta of 617, ' +
      'not 10.');
  delta.setValidation(
      FormApp.createTextValidation()
          .requireNumber()
          .build());

  var n = form.addTextItem()
      .setTitle('Runs per arm it needs')
      .setRequired(true);
  n.setHelpText('Straight off n_for.py. Do not round it to something comfortable.');
  n.setValidation(
      FormApp.createTextValidation()
          .requireNumberGreaterThan(0)
          .build());

  form.addMultipleChoiceItem()
      .setTitle('Could you afford it?')
      .setChoiceValues(['Yes — comfortably',
                        'Borderline — it would cost real money or hours',
                        'No — out of reach',
                        'No, and I would have claimed it anyway before this session'])
      .setRequired(true);

  // ------------------------------------------------- 4. WHAT YOU LEARNED
  form.addPageBreakItem()
      .setTitle('4 · Two short answers')
      .setHelpText('Short. Two or three sentences each is plenty.');

  form.addParagraphTextItem()
      .setTitle('Which RETIRE reason was the most useful, and what did you change?')
      .setHelpText(
          'Quote the line the screener printed. "forbidden_tools is empty -> blind ' +
          'to prompt injection" is a good answer; "it said my row was bad" is not.')
      .setRequired(true);

  form.addParagraphTextItem()
      .setTitle(
          'Name a claim you have made — in this course or anywhere — that you now ' +
          'think you were not entitled to.')
      .setHelpText(
          'Mine is on slide 14 of the Session 3 deck. There is no wrong answer here ' +
          'and I am not grading the confession, I am grading whether you can spot ' +
          'the shape of one.')
      .setRequired(true);

  // ---------------------------------------------------------- 5. TROUBLE
  form.addPageBreakItem()
      .setTitle('5 · Anything broken?')
      .setHelpText('Optional. Faster than email and I read all of them.');

  form.addParagraphTextItem()
      .setTitle('Anything that did not work')
      .setHelpText('Paste the error. The whole error, not your summary of it.')
      .setRequired(false);

  Logger.log('EDIT: %s', form.getEditUrl());
  Logger.log('LIVE: %s', form.getPublishedUrl());
  return form.getPublishedUrl();
}
