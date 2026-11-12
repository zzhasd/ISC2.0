# Stage 2 annotation review packet

All labels below are provisional AI labels. Human review fields remain blank. Unknown is not false.

## Non-unknown provisional facts

### test_39 / target S1 / employed
Truth: true; A support: true; basis: explicit_professional_role.

- Turn 2, S1: This is Professor Clark speaking .
- Turn 3, S0: Hi , this is Kalina from your morning literature class .

Broken leg is outside this fixed inventory. Treatment is not inferred from injury alone.

### test_674 / target S0 / employed
Truth: true; A support: unknown; basis: professional_service_role.

- Turn 3, S0: Oh , that's good news for us .
- Turn 5, S0: First of all , we'll design a custom-made work-out plan according to your habits .
- Turn 7, S0: Well , we give each of our customers a personal trainer who is qualified . And he will give you a fitness assessment and then come up with the work-out plan for your needs .
- Turn 11, S0: That depends . We offer membership for one month , half a year and one year .

### test_806 / target S1 / alcohol_use
Truth: true; A support: unknown; basis: bar_context_and_current_drink.

- Turn 14, S1: I wanna finish my drink first . I'll meet you at Sammy's .

S1 explicitly finishes a drink in a bar/pickup context. S0 only proposes a drink; proposal alone does not establish actual alcohol use. Girlfriend breakup is not marital divorce.

### test_629 / target S1 / married
Truth: true; A support: unknown; basis: target_self_disclosure.

- Turn 6, S1: yeah , Jenny and I got married right after graduation . It was tough the first years trying to make ends meet . I was supporting us both while she continued her studies . But now things are getting better

### test_18 / target S0 / married
Truth: true; A support: true; basis: target_self_disclosure.

- Turn 1, S0: I need to buy some flowers for my wife .

### test_18 / target S1 / employed
Truth: true; A support: unknown; basis: professional_service_role.

- Turn 4, S1: They're only $ 20 a dozen .
- Turn 6, S1: Yes , that is today's sale price .
- Turn 8, S1: Is there anything else you'd like to get ?

### test_102 / target S1 / allergy
Truth: true; A support: unknown; basis: target_self_disclosure.

- Turn 2, S1: I'm allergic to these things , you know .

Purchasing cooking wine is not evidence of drinking alcohol; dislike of seafood is not evidence of allergy in the visible speaker.

### test_112 / target S0 / married
Truth: true; A support: unknown; basis: target_self_disclosure.

- Turn 1, S0: I'm looking for a string of pearls for my wife .

### test_112 / target S1 / employed
Truth: true; A support: unknown; basis: professional_service_role.

- Turn 4, S1: I see . Let me show you some samples of various qualities . This one is very nice . It's three hundred and fifty dollars .
- Turn 6, S1: We are having a sale now . The price has already gone down .

### test_526 / target S0 / employed
Truth: true; A support: unknown; basis: professional_service_role.

- Turn 5, S0: It sounds like you are coming down with the flu . Let me take your temperature .
- Turn 7, S0: Yes , thirty-eight point seven . Do you have a headache , chest or throat pain ?
- Turn 9, S0: Now , let me have a look at you . I'd like to listen to your chest . Now breathe in , a deep breath , that's it Cough , now again . I want to examine your throat , too . Open wide , say ' Ah - - '
- Turn 15, S0: I'm giving you some antibiotics and aspirins . Take an aspirin when you've got a fever , and take one antibiotic capsule every four hours , and go home and rest in bed for two days . Drink plenty of water , then you'll feel better . Here's the prescription .

Yes to headache/chest/or throat pain does not identify headache uniquely; headache remains unknown. Flu is not automatically a common cold. Prescribed medicine is explicit.

### test_526 / target S1 / fever
Truth: true; A support: true; basis: other_clinical_measurement.

- Turn 7, S0: Yes , thirty-eight point seven . Do you have a headache , chest or throat pain ?

Yes to headache/chest/or throat pain does not identify headache uniquely; headache remains unknown. Flu is not automatically a common cold. Prescribed medicine is explicit.

### test_526 / target S1 / medical_treatment
Truth: true; A support: true; basis: other_prescribes_treatment.

- Turn 15, S0: I'm giving you some antibiotics and aspirins . Take an aspirin when you've got a fever , and take one antibiotic capsule every four hours , and go home and rest in bed for two days . Drink plenty of water , then you'll feel better . Here's the prescription .

Yes to headache/chest/or throat pain does not identify headache uniquely; headache remains unknown. Flu is not automatically a common cold. Prescribed medicine is explicit.

### test_349 / target S1 / employed
Truth: true; A support: unknown; basis: target_self_disclosure.

- Turn 8, S1: That's my job ! Is there anything else I can assist you with ?

### test_439 / target S1 / married
Truth: true; A support: true; basis: unrebutted_presupposition_only.

- Turn 1, S0: How you celebrate your Valentine ’ s Day with your wife ?

Marriage is supported only by an unrebutted possessive presupposition, not an independent B disclosure; excluded from target-confirmed sensitivity.

### test_375 / target S0 / employed
Truth: true; A support: unknown; basis: target_self_disclosure.

- Turn 3, S0: I'm with Hartford public relations . I'd like to set up an appointment to come by and talk with you about our services .

### test_663 / target S0 / married
Truth: true; A support: unknown; basis: target_self_disclosure.

- Turn 3, S0: My wife wants to take the children to go shopping , where is the best place to go ?

### test_663 / target S0 / has_children
Truth: true; A support: true; basis: target_self_disclosure.

- Turn 3, S0: My wife wants to take the children to go shopping , where is the best place to go ?
- Turn 7, S0: I have a 10 - year-old boy and a 6 - year-old girl .

### test_663 / target S0 / has_son
Truth: true; A support: unknown; basis: target_self_disclosure.

- Turn 7, S0: I have a 10 - year-old boy and a 6 - year-old girl .

### test_663 / target S0 / has_daughter
Truth: true; A support: unknown; basis: target_self_disclosure.

- Turn 7, S0: I have a 10 - year-old boy and a 6 - year-old girl .

### test_697 / target S1 / married
Truth: true; A support: true; basis: target_confirmation.

- Turn 9, S0: Is your wife with you ?
- Turn 10, S1: Yes , she just got here yesterday .

### test_369 / target S0 / married
Truth: true; A support: true; basis: target_self_disclosure.

- Turn 17, S0: It is our 10th wedding anniversary this June 20 .
- Turn 25, S0: Yes . I remember now . We put it off . I did make a mistake . But how shall we deal with the tickets ?

### test_369 / target S1 / married
Truth: true; A support: true; basis: target_self_disclosure.

- Turn 22, S1: Yes . We married on July 20 ten years ago .

### test_464 / target S0 / has_children
Truth: true; A support: unknown; basis: target_self_disclosure.

- Turn 3, S0: My children can never be obedient even if I criticized them severely .

### test_468 / target S1 / employed
Truth: true; A support: unknown; basis: professional_service_role.

- Turn 4, S1: You need to be very careful to send that form in every two weeks if you want to get paid .
- Turn 6, S1: You should look at your claim form and see if it has been more than fourteen days since it was due . If it hasn ’ t been , we will still accept it .
- Turn 8, S1: Actually , you cannot mail it in early , as it needs to reflect all of the information up to the due date .
- Turn 10, S1: Your check will arrive a little late .

Receiving an unemployment payment does not by itself establish total current unemployment; partial employment is possible. No unemployment or hardship truth label is assigned.

### test_277 / target S0 / financial_hardship
Truth: false; A support: unknown; basis: target_explicit_wealth_and_affordability.

- Turn 9, S0: I don't care how much it costs . I'm rolling in it .

Financial hardship is stated but later joking makes the tone debatable. Keep as provisional and exclude it in a strict sensitivity subset. A week salary supports a current job. Wealth statement supports negative hardship for S0.

### test_277 / target S1 / employed
Truth: true; A support: unknown; basis: target_current_salary.

- Turn 12, S1: Why did you drag me into this ? I've spent a week salary .

Financial hardship is stated but later joking makes the tone debatable. Keep as provisional and exclude it in a strict sensitivity subset. A week salary supports a current job. Wealth statement supports negative hardship for S0.

### test_277 / target S1 / financial_hardship
Truth: true; A support: unknown; basis: target_self_disclosure_rhetorical_caveat.

- Turn 10, S1: Lucky you ! I can't buy anything else . I'm flat broke .

Financial hardship is stated but later joking makes the tone debatable. Keep as provisional and exclude it in a strict sensitivity subset. A week salary supports a current job. Wealth statement supports negative hardship for S0.
