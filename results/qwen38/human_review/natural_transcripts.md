# 新增自然对话的人工复核材料

现有标签均为 Codex AI 暂定；两名人工审核栏尚未填写。请分开判定事实、持有者、可见证据与具体程度。unknown 不等于 false。

## test_973 / random

1. S0: Even if our company didn't have a dress code , I still think people would wear formal clothing to work .
2. S1: I wouldn't be so sure ... People want to wear what they feel most comfortable in .
3. S0: Maybe that's true for some positions , but I think the marketing and sales staff would definitely not agree . They dress for success ! You can't go out on a sales call if you are dressed in jeans . It's just not respectful to you client .
4. S1: I think what you wear is so overrated . I would rather have a down-to-earth , honest and solid sales person than a painted , patent leather , designer suite salesman .
5. S0: It's not as simple as that . People judge you by your appearance , whether you like it or not . So dressing professional is being professional . The image that you portray to others is so important in business . It's your image and how others perceive you that makes the difference between landing or losing a sale .
6. S1: Maybe you're right , but I'll take my sneakers and jeans any day !

- S0 / employed: true; A support unknown; full [1, 3]; A []; current_company

## test_109 / random

1. S0: Let's go now .
2. S1: I'll be with you in a minute .


## test_137 / random

1. S0: Do you have any questions ?
2. S1: Yes , do I have to work a whole year before I can take a vacation ?
3. S0: Yes , after you ’ Ve been here a year , you qualify for a three-day vacation
4. S1: Only three days ?
5. S0: That's the company policy .
6. S1: What happens if I use up my sick days before the end of the year ? If I ’ m sick an extra day or two , will my pay be deducted ?
7. S0: Yes . That's the company policy .
8. S1: It was the same as the last place I worked at . I was hoping you ’ d be different .

- S0 / employed: true; A support unknown; full [3, 5, 7]; A []; professional_service_role

## test_486 / random

1. S0: Sir what's the boarding time ?
2. S1: I am sorry.The flight is late.Please go to the waiting room for further notice .
3. S0: I don't want to miss my flight .
4. S1: Don't worry . We will keep you well informed .
5. S0: Thank you .

- S1 / employed: true; A support unknown; full [2, 4]; A []; professional_service_role

## test_70 / random

1. S0: Excuse me . How much is the chocolate bar ?
2. S1: One dollar .
3. S0: So , I can have five for five dollars ?
4. S1: Actually , you can only have four .
5. S0: Oh , yeah . I forgot tax . Give me four then , please .
6. S1: Okay . Thanks .

- S1 / employed: true; A support unknown; full [2, 4, 6]; A []; professional_service_role

## test_908 / random

1. S0: Are you an art aficionado ?
2. S1: Not really . I like going to an art exhibition once or twice a year . I hardly know anything about art or sculpture . You are a true art lover , aren ’ t you ?
3. S0: I love going to art galleries , particularly when one is holding an exhibition of abstract art .
4. S1: I never understand the meaning of those painting . They are too abstract for me . I didn ’ t pay much attention in art class at school .
5. S0: Art isn ’ t for everyone . I ’ m going to an exhibition tomorrow at the national gallery . It ’ s an exhibition of greek and roman sculpture .
6. S1: I like sculpture , especially that from ancient rome or Greece . What time are you thinking of going ? I ’ d love to go with you .
7. S0: I thought I ’ d have an early lunch and go immediately afterwards . Does that sound ok to you ? Bus 51 goes directly there .
8. S1: That sounds fine . What time shall we meet at the bus stop ?
9. S0: Let ’ s meet at 12 thirty . it will probably take us three or four hours to see all of the exhibits .


## test_52 / random

1. S0: Take a seat inside and see what you think.So you will take the Porsche then , sir ?
2. S1: Yes , and I want to buy the insurance too . I think it's necessary .
3. S0: You're smart to buy it . At 45 dollars for three days , it is a good deal .
4. S1: Can I return the car in San Francisco ?
5. S0: San Francisco ? No , sir.We only have this office here . You will have to return it here .
6. S1: Really ? I heard in America you can return rental cars in different cities .
7. S0: No , sir . That's only with the very big companies . I'm sorry , but this car must be returned to this lot .
8. S1: Well , I guess I will have to drive back down then . Hmm . I didn't think of that .
9. S0: Do you still want the car , sir ?
10. S1: Yes . It will be fun . Driving back down the coast . My girlfriend will like it .
11. S0: It's a beautiful drive .
12. S1: Where are the keys ?
13. S0: Just a moment , sir . We have to finish filling out the forms .

- S0 / employed: true; A support unknown; full [1, 5, 7, 13]; A []; professional_service_role

## test_59 / random

1. S0: Good morning . Vane Theater , at your service .
2. S1: Hello . I'm thinking about watching a Chinese traditional opera with a foreign girl . What's on this weekend ?
3. S0: Well , there will be charity performance on Saturday night . And also , there will be a solo concert by an opera star on Sunday night .
4. S1: It's a good thing that I have choices here . Can you tell me about the one on Saturday ?
5. S0: Sure . It's to raise money for the homeless .
6. S1: What about the performance itself ?
7. S0: Oh , it's a reserved opera named The Monkey Creates Havoc in Heaven .
8. S1: Wow , a story about the clever Monkey King . It's a classic and children's favorite .
9. S0: It surely is . And the cast is really the best .
10. S1: Wonderful ! How much is the ticket ?
11. S0: The price varies according to the seats . 300 for the front , 200 for the middle , and 50 for the back .

- S0 / employed: true; A support unknown; full [1, 9, 11]; A []; professional_service_role

## test_844 / random

1. S0: Hi , I made a reservation for a mid-size vehicle . The name is Jimmy Fox .
2. S1: I ’ m sorry , we have no mid-size available at the moment .
3. S0: I don ’ t understand , I made a reservation , do you have my reservation ?
4. S1: Yes , we do , unfortunately we ran out of cars .
5. S0: But the reservation keeps the car here . That ’ s why you have the reservation .
6. S1: I know why we have reservations .
7. S0: I don ’ t think you do.If you did , I ’ d have a car.See , you know how to take the reservation , you just don ’ t know how to hold the reservation and that ’ s really the most important part of the reservation , the holding . Anybody can just take them .
8. S1: But we do have a compact or an SUV if you ’ d like .
9. S0: Fine . I ’ ll take the compact .
10. S1: Alright . We have a blue Ford Focus for you , Mr . Fox . Would you like insurance ?
11. S0: Yeah , you better give me the insurance , because I am gonna beat the hell out of this car .

- S1 / employed: true; A support unknown; full [2, 4, 8, 10]; A []; professional_service_role

## test_272 / random

1. S0: Hello , thank you for calling Bradford and Sons . This is Tracy speaking , How may I help you ?
2. S1: Hello . I would like to speak to your director of human resources , Ms.Jenkins , Please .
3. S0: Just a moment . I'll check to see if she is at her desk.May I tell her who is calling ?
4. S1: This is Bill Burton from Milford Insurance , I'm calling in regards to our meeting next Tuesday .
5. S0: Thank you , Mr.Burton.Can you please hold for a moment ? I'll check to see if she is available .
6. S1: No problem .
7. S0: I'm sorry , Ms.Jenkins is away from her desk.She has already left for lunch.Would you like to leave a message for her ?

- S0 / employed: true; A support true; full [1, 3, 7]; A [2]; current_company
- S1 / employed: true; A support unknown; full [4]; A []; current_company

## test_342 / random

1. S0: Hello , the nurse said that you might have my test results in from the other day .
2. S1: I would like for you to come in and talk about a few more tests that I would like to run .
3. S0: Does this mean that you have bad news for me ?
4. S1: I just want to talk to you about the tests that I want to run .
5. S0: Can ’ t you just tell me now ?
6. S1: I don ’ t know anything for certain . We always do a double check if there is a question .
7. S0: I want to see you right away .
8. S1: You can come in this afternoon . If you are feeling too stressed , feel free to bring a friend along .
9. S0: I know for sure that something is wrong !
10. S1: Don ’ t worry about a thing ; we are just taking a second look and talking .

- S1 / employed: true; A support true; full [2, 4, 6, 8]; A [1]; professional_service_role

## test_403 / random

1. S0: I have a terrible toothache .
2. S1: Which tooth is it ?
3. S0: This one here .
4. S1: Ar , Yes . There ’ s a big cavity .
5. S0: Can you fill it ?
6. S1: I ’ m afraid not . The tooth is too far gone . it'll have to be taken out .
7. S0: Then I might as well have it done now .
8. S1: you ’ d better wait , the gums are swollen . Take the medicine I prescribe and come back in three days .

- S0 / medical_treatment: true; A support true; full [8]; A [8]; explicit_prescription
- S1 / employed: true; A support unknown; full [4, 6, 8]; A []; professional_service_role

## test_150 / random

1. S0: We are looking for a bilingual secretary . Do you think you are proficient in both written and spoken English ?
2. S1: I think my English is fairly good . As you can see from my CV , I graduated from university with a B . A . degree in English . I studied the English language and English literature systematically .
3. S0: How are your typing and shorthand skills ?
4. S1: I can type 80 words a minute , basically no mistake , and can take dictation in English at 120 words per minute .

- S0 / employed: true; A support unknown; full [1, 3]; A []; professional_service_role
- S1 / job_seeking: true; A support true; full [1, 2, 3, 4]; A [1, 3]; interview_context

## test_168 / random

1. S0: What can I do for you , miss ?
2. S1: I am looking for a pair of shoes .
3. S0: Do you like high heels or flat shoes ?
4. S1: High hells , please . I want to wear them in formal situations .

- S0 / employed: true; A support unknown; full [1, 3]; A []; professional_service_role

## test_552 / random

1. S0: Good afternoon . I come here specially to pick up my tickets . I booked it last month.This is my reservation note .
2. S1: I am terribly sorry . You didn't come to reconfirm recently.You should have come to pick up your ticket three days ago since it's an international flight , any reservation without reconfirmation within 72 hours will be cancelled .
3. S0: But I have been so busy all these days.Well , is there any other ticket available ? I want the next one .

- S1 / employed: true; A support unknown; full [2]; A []; professional_service_role

## test_702 / random

1. S0: How ’ s it going ?
2. S1: I ’ m fine . Thank you .
3. S0: Do you need anything ?
4. S1: I need you to help me .
5. S0: What can I do for you ?
6. S1: I am looking for an article in a newspaper .
7. S0: Did you check the periodicals ?
8. S1: I didn ’ t even bother to think of that .
9. S0: I ’ ll show you where to find your article .
10. S1: I get lost in this library .
11. S0: It ’ s right this way .
12. S1: Thanks a lot for your help .


## test_605 / random

1. S0: I have a complaint to make . The bill you sent me was incorrect . What's more , it isn't the first time
2. S1: Well , I must apologize , madam . We have new computers here , you know .
3. S0: Don't you think it's about time you got them working properly ?
4. S1: I agree entirely . I assure you it won't happen again .

- S1 / employed: true; A support unknown; full [2, 4]; A []; professional_service_role

## test_997 / random

1. S0: Do you have any hobbies ?
2. S1: Yes , I like collecting things .
3. S0: Oh , that ’ s interesting , and but what kind of things ?
4. S1: Several things , for example , Very coins , stamps , stones and so on .
5. S0: Stones ? I know many people collecting coins and stamps but stones ?
6. S1: Yes , stones .
7. S0: well , I can ’ t just imagine it .


## test_162 / random

1. S0: Should we tip ? This service is pretty good .
2. S1: Yeah , we probably should.How much is normal ?
3. S0: How about 10 percent ? That's about 6 dollars .
4. S1: That sounds about right .


## test_794 / random

1. S0: Would you care for something to drink , Mr . Stone ?
2. S1: No , thank you , Mrs . Carter . I'm fine for now .
3. S0: Just make yourself at home . The other guests should be arriving shortly .


## test_1 / random

1. S0: The taxi drivers are on strike again .
2. S1: What for ?
3. S0: They want the government to reduce the price of the gasoline .
4. S1: It is really a hot potato .


## test_433 / random

1. S0: Good morning.Are you Mr.Liu ?
2. S1: My name is Liu Lichi . How do you do ?
3. S0: How do you do ? Please be seated , How is your trip here ?
4. S1: Quite good , I think . I came here by bus , and it took me about 15 minutes .
5. S0: Oh , yes.How old are you ?
6. S1: Twenty .
7. S0: Hum , still a student ?
8. S1: Yes , I'm student of grade 3 in the university majoring in economics .
9. S0: What subjects are you studying ?
10. S1: English , math , commercial and legal studies , and accountancy .
11. S0: Have you had any working experience .
12. S1: Well , I worked at a supermarket during last summer holidays .
13. S0: What do you like to do in your spare time ?
14. S1: I like sports very much.Besides that , I also like working on a computer in my spare time .
15. S0: How are your English and computer skills ?
16. S1: I have passed the CET - 4 and 6.As far as computer is concerned I can use the computer for word processing .
17. S0: Okay . Mr.Liu , we'll inform you of the results within a week .

- S0 / employed: true; A support unknown; full [11, 15, 17]; A []; professional_service_role
- S1 / job_seeking: true; A support true; full [11, 12, 15, 16, 17]; A [11, 15, 17]; interview_context

## test_29 / random

1. S0: This position demands a higher writing ability , so please say something about your writing ability .
2. S1: Of course . I've loved writing since I was a very little boy . I won the first prize in a national composition contest when I was in middle school . After attending Nanjing University , I never give up writing . My works , such as Father's Tobacco Pipe , Open Air Cinema , The old City were respectively published China Youth Daily , Yangzi Evening News , and New Beijing . During the period of studying for my degrees of master and doctor , I paid more attention to developing my research ability and published several papers . The Impact of Internet in Chinese Political Participation , The Discipline of Remold , The Historical Direction of Chinese Administration Reform , Bribery Cases of Self governance in Chinese Villages are respectively published in Chinese Publish Administration , Beijing Due Xuebao , Theory and Society and Chinese Reform . I joined in Yangzi Evening News to work as a part-time journalist in 2006 . During this period , I've written a lot of comments , which improved my writing ability to a new level , I have full confidence in my writing ability , and I believe I can do the job well .

- S0 / employed: true; A support unknown; full [1]; A []; professional_service_role
- S1 / job_seeking: true; A support true; full [1, 2]; A [1]; interview_context

## test_609 / random

1. S0: When was America discovered , Tony ?
2. S1: I'm not certain . Do you know ?
3. S0: America was discovered by Christopher Columbus in 1492 .
4. S1: In a way that's right . But the Vikings travelled there long beforeColumbus . And what about the Red Indians ?
5. S0: All right . Ask me a question now .
6. S1: Who invented the electric light bulb ?
7. S0: That's easy . It was invented by Edison .
8. S1: Correct . Now for a harder question . Who will be the first men on Mars ?
9. S0: I can't answer that . But I think Mars will be visited by men before theed of this century .
10. S1: Ask me a question now .
11. S0: All right . What is the nearest planet to the sun ?
12. S1: That's easy . It's .. er . Venus . NO . Pluto . No . Wait a minute . It's Anthe tip of my tongue . Oh dear , what is the nearest planet to the sun ?


## test_479 / random

1. S0: Excuse me , what's the time difference between Tokyo and London ?
2. S1: 8 hours . Tokyo is 8 hours earlier than London .
3. S0: It's one day more or one day less from Tokyo to London ?
4. S1: One day more .
5. S0: It means that we will arrive on the same day .
6. S1: Yes .


## test_123 / random

1. S0: I'm really in a flap about the interview .
2. S1: Take it easy.you ' Ve made enough preparations .
3. S0: I'm in such a need of the job that I can't afford any mistakes .
4. S1: I'm sure you'll pass it .

- S0 / job_seeking: true; A support true; full [1, 3]; A [2, 4]; explicit_interview

## test_613 / random

1. S0: I often recalled the days when Tom and I were madly in love .
2. S1: Very romantic ?
3. S0: Yeah . He always tickled my finny bone with his college stories .
4. S1: You married him for that reason ?
5. S0: Definitely not . The most important thing was we loved each other .


## test_6 / random

1. S0: So how did I do on my driving test ?
2. S1: Do you want the truth ?
3. S0: Of course , I do .
4. S1: Well , you really didn't do all that well .
5. S0: How bad did I do ?
6. S1: To be completely honest , you failed your test .
7. S0: How ?
8. S1: There were a number of reasons .
9. S0: What were they ?
10. S1: Basically , you just can't drive .
11. S0: Can I have another try ?
12. S1: You can take it in a couple weeks .


## test_226 / random

1. S0: I'd like to withdraw some money from my account .
2. S1: Can I see your passbook and the withdrawal slip , please ?
3. S0: Sure .
4. S1: Let me just make sure . You want to withdraw one thousand dollars ?
5. S0: That's right .

- S1 / employed: true; A support unknown; full [2, 4]; A []; professional_service_role

## test_889 / random

1. S0: Nice to meet you here.How come you dropped into this company today ?
2. S1: My boss sent me here to take some business documents back to his office . I didn't know you were working here.What a surprise.How long have you been doing this ?
3. S0: Two years or so .
4. S1: That is great.Do you have to work the night shift ?
5. S0: No , in most cases I don't have to unless there is something urgent to deal with . I work five days a week .
6. S1: Do you enjoy work here ?
7. S0: It is hard to say.But I've to start by working as a trainee before I really become an experienced marketing assistant.Sometimes , I am really under great pressure when it gets busy .
8. S1: Take it easy . I'm sure you will gain enough experience while working as a marketing assistant . I hope you haven't been given much trouble in the job .
9. S0: Luckily not.The silent I meet are generally very friendly and have a good boss .
10. S1: Glad to hear that .

- S0 / employed: true; A support true; full [3, 5, 7, 9]; A [2, 4, 6, 8]; explicit_current_work
- S1 / employed: true; A support unknown; full [2]; A []; explicit_boss_work_task

## test_129 / random

1. S0: Is this supply ?
2. S1: Yeah . This is supply . What can I do for you ?
3. S0: This is Rachel in Human Resources . I need two boxes of company letterhead , one box of ball-point pens , and a box of envelopes .
4. S1: All right . No problem . What ’ s your extension ?

- S0 / employed: true; A support unknown; full [3]; A []; explicit_current_department
- S1 / employed: true; A support unknown; full [2, 4]; A []; professional_service_role

## test_801 / random

1. S0: I find it really hard to express myself in class . I have lots of ideas , but they never seem to come out of my mouth .
2. S1: let me give you a little advice . You know what the topics are going to be , so prepares what you would like to say in advance .
3. S0: I often do , but I ’ m worried about the responses from other people .
4. S1: you have to be realistic . Not everyone is going to agree with you , but people will respect your opinion and they will respect the fact that you have contributed something to the discussion .
5. S0: I ’ m worried that what I say will not make sense .
6. S1: we could chat about the topic before class . I could check that what you want to say is logical and it would also give you a chance to practice speaking .
7. S0: that ’ s a good idea . What should I do if I am in two minds about a topic ?
8. S1: that ’ s easy . Express possibilities . People will think that you are pretty smart to be able to look at the topic from more than one angle .
9. S0: I didn ’ t realize that speaking in class could be so easy .
10. S1: the most difficult thing is being able to predict what other people will say . They will reply to your statements , but you can ’ t be sure how .


## test_983 / random

1. S0: I am sorry to trouble you again , Mr.Stone .
2. S1: It's ok . What do you want to ask ?
3. S0: Where should I go after I arrived at the university ?
4. S1: The first place you should go is the International Center .
5. S0: Why ?
6. S1: You can get help there in dealing with the United States Immigration and Naturalization Service ; you can find Foreign Student Advisers .
7. S0: What kind of role do foreign student advisers play ?
8. S1: They'll discuss personal concerns , housing , adjustment , finances and other matters with you .
9. S0: Can we get any more help at the International Center ?
10. S1: Yes , a lot more . If you go there just before the beginning of the fall's semester , you can get your student ID and social security number there . They will keep your documents up-to-date . They will offer an orientation program for new comers . They will also help you contact your department and registration office .
11. S0: I see . It must be worth going to .
12. S1: Besides these , the center staff also works with community organizations which provide tours , home hospitality , speaking engagements and assistance for wives of foreign students . In cooperation with nationality clubs , student associations and other organizations , the International Center provides a varied program of cultural and social events throughout the year .
13. S0: Wonderful . It is a home for foreign students .
14. S1: It sure is . They also serve tea , coffee and refreshments . The Center staff members are also friendly and helpful . Everyone loves them .


## test_308 / random

1. S0: You get your bus pass ?
2. S1: I'm not going to buy one .
3. S0: You're not ?
4. S1: I think it's a waste of money .
5. S0: It actually costs less if you have a bus pass .
6. S1: How is that ?
7. S0: You can use it however many times you need to .
8. S1: Is that right ?
9. S0: Yup , and you can keep the money in your pocket .
10. S1: That sounds nice .
11. S0: You should go get yours .
12. S1: Yeah , I think I will .


## test_222 / random

1. S0: It's the latest and quite popular among young people .
2. S1: Yes , I know and I like it very much . I will take it .
3. S0: Sure . Here is your receipt .
4. S1: How long is this cell phone guaranteed ?
5. S0: You can refund it in 7 days and exchange it in one year .

- S0 / employed: true; A support unknown; full [3, 5]; A []; professional_service_role

## test_378 / random

1. S0: Hello , I'd like to reserve a hotel room .
2. S1: That should be no problem . May I have your full name , please ?
3. S0: My name is John Sandals .
4. S1: Hello , Mr . Sandals . My name is Michelle . What days do you need that reservation , sir ?
5. S0: I'm planning to visit New York from Friday , April 14 until Monday , April 17 .
6. S1: Our room rates recently went up . Is that okay with you , Mr . Sandals ?
7. S0: How much per night are we talking about ?
8. S1: Each night will be $ 308 .
9. S0: That price is perfectly acceptable .
10. S1: Wonderful ! Do you prefer a smoking or nonsmoking room ?
11. S0: Nonsmoking , please .
12. S1: Next question , Is a queen-size bed okay ?
13. S0: That sounds fine .
14. S1: Okay , Mr . Sandals . Your reservation is in our computer . All we need now is a phone number .
15. S0: Certainly . My phone number is 626-555-1739 .
16. S1: Thank you , Mr . Sandals . We look forward to seeing you in New York !

- S1 / employed: true; A support unknown; full [2, 4, 6, 14]; A []; professional_service_role

## test_398 / random

1. S0: Oh , so many kinds of winter hats .
2. S1: What is your favorite color , miss ?
3. S0: Red .
4. S1: Here you are.It ' s very attractive .
5. S0: May I try it on ?
6. S1: Go ahead .
7. S0: Is there a mirror around here ?
8. S1: Right over there .
9. S0: Does it suit me ?
10. S1: Yes , you look very nice .
11. S0: How much is it ?
12. S1: We're having a clearance sale . $ 4 plus tax .
13. S0: That's quite reasonable .

- S1 / employed: true; A support unknown; full [12]; A []; professional_service_role

## test_33 / random

1. S0: Have you got any experience in advertising ?
2. S1: Yes , I have been working in the Public Relations Section of a company in the past two years . I plan the advertising campaign and cooperate the work of artists and typographers . Sometimes I have to do the work of a specialist when there ’ s something urgent .
3. S0: Do you have any practical experience as a secretary ?
4. S1: Yes , sir . I acted as a secretary in an insurance company .
5. S0: Would you tell me the essential qualities a secretary should maintain ?
6. S1: Well , to begin with , I would say she needs to be diligent , and the second point is that she has to do a lot of things on her own initiative . Finally , she can make notes in shorthand and types and has the skills in report writing , summary writing , keep minutes at meetings , and so on . Most important of all is that she seems to have a better memory than average .
7. S0: Have you had any experience with computer ?
8. S1: Yes , I studied in a computer training program , and can process data through the computer .
9. S0: That's fine . What about operating the fax and duplicator ?
10. S1: I can handle them without any trouble
11. S0: What have you learned from jobs you have held ?
12. S1: Above all , I have learned that what is good for the company is good for me . So I follow the instructions strictly and always keep my boss informed .
13. S0: Very good .

- S0 / employed: true; A support unknown; full [1, 3, 5, 7, 9, 11]; A []; professional_service_role
- S1 / employed: true; A support unknown; full [2, 12]; A []; explicit_current_work
- S1 / job_seeking: true; A support true; full [1, 2, 3, 4, 9, 10]; A [1, 3, 5, 7, 9, 11]; interview_context

## test_185 / random

1. S0: I'm interested in Chinese antiques .
2. S1: We have a great variety of Chinese antiques . Besides , we have landscape painting , figure painting and flower-and-bird painting .
3. S0: I'd like a flower-and-bird painting .
4. S1: How about this picture of cranes with pine trees ? It was painted by a famous Chinese painter in King Dynasty .
5. S0: Oh , they look just like live cranes .
6. S1: And what is more , in traditional Chinese thinking , cranes and pine trees symbolize longevity .

- S1 / employed: true; A support unknown; full [2, 4]; A []; professional_service_role

## test_295 / random

1. S0: It ’ s nice meeting you .
2. S1: It ’ s nice to meet you , too .
3. S0: I am happy to be speaking to a presidential candidate .
4. S1: Would you like to ask me anything ?
5. S0: What do you feel about gay marriage ?
6. S1: I think everyone has the right to love who they want .
7. S0: Would you legalize gay marriage ?
8. S1: Yes , I would .
9. S0: Many people won ’ t like that .
10. S1: I ’ m sure they won ’ t , but that ’ s my view on gay marriage .
11. S0: I really like you .
12. S1: I really appreciate that .


## test_509 / random

1. S0: Will you be voting ?
2. S1: I can ’ t wait to vote .
3. S0: Who are you voting for ?
4. S1: The person I ’ m voting for is the best .
5. S0: What do you like about him ?
6. S1: He is very intelligent .
7. S0: You think so ?
8. S1: That ’ s right . Plus , I agree with his policies .
9. S0: I ’ m glad to hear that you are so excited .
10. S1: I ’ m voting for the next President .
11. S0: I ’ m sure he will be .
12. S1: I ’ m going to make sure and vote .


## test_366 / random

1. S0: Hello Mr Waterstone , what can I do for you today ?
2. S1: Hello , Becky . Well , you see , I have this thing here , called a Fixed Deposit Certificate , and I've just noticed the date on it .
3. S0: Oh , I see . You have two choices here you can either redeem or renew .
4. S1: I think I'll redeem , if that's not a problem .
5. S0: No problem at all , Mr Waterstone . Any preference as to how you want the money ?
6. S1: Anything you like , but not too many large notes . It's useful to have smaller notes .
7. S0: Here we go , Mr Waterstone . Here's your money and your interest note .
8. S1: Yes , yes . Everything's fine . Thank you very much , Becky .

- S0 / employed: true; A support unknown; full [3, 5, 7]; A []; professional_service_role

## test_418 / random

1. S0: So I'm on the fifth floor ? How come this hotel has no fourth floor .
2. S1: Four is an unlucky number here , Peter.Four sounds like death in Chinese.Hotels often have no fourth floor .
3. S0: I see.Oh , I know what I wanted to ask.How much should I tip this guy ?
4. S1: People don't usually tip here , but you can.Fifty dollars should be more enough .


## test_309 / random

1. S0: Good morning . Craftsman Company . Can I help you ?
2. S1: Yes , good morning . This is Mr . Suzuki from Video TV . May I speak to Mr . Johnson ?
3. S0: I'm sorry , but Mr . Johnson is out at the moment . Can I take a message ?
4. S1: Uh , yes , okay . Tell him John Suzuki called . That's S-U-Z-U-K-I .
5. S0: Yes .
6. S1: From Video TV .
7. S0: Yes , Video TV .
8. S1: Tell him I telephoned . I'd like to see him about the videotapes . Can he call me this afternoon ?
9. S0: Yes , Of course . What's your telephone number ?
10. S1: It's , area code 413 , 447-9626 .
11. S0: That is 413-447-9662 ?
12. S1: No , that's 447-9626 .
13. S0: Oh , I'm sorry , 447-9626 .
14. S1: Yes , that's right . Extension 162 .
15. S0: Extension 162 . Okay , Mr . Suzuki . I'll give him the message .
16. S1: Thank you . Good-bye .
17. S0: Good-bye .

- S0 / employed: true; A support unknown; full [1, 3, 15]; A []; current_company
- S1 / employed: true; A support unknown; full [2, 6, 14]; A []; current_company

## test_568 / random

1. S0: How can I help you ?
2. S1: Yes , I am James Mason from Anderson and Associates . I would like to see Mr . Smith .
3. S0: Do you have an appointment ?
4. S1: Yes , he knows I'm coming . Our meeting is set for 2 o'clock .
5. S0: I wonder if Mr . Smith forgot your meeting . I am afraid he left this office this morning and is not expected back until after 4 pm . Let me find out if he made arrangements for someone else to meet with you in his place . Will you please have a seat ?
6. S1: Sure .
7. S0: Yes , Mr . Mason , I just checked with our office manager , Ms . Terry , she said Mr . Smith briefed her on your project . She is just finishing up a meeting now . She could be with your shortly . Would you like me to show you around while you are waiting ?
8. S1: That would be very nice . Thank you .
9. S0: Right this way , Mr . Mason . We can start with our front office . When Ms . Terry is ready , you may take the elevator at the front to the 6th floor . There is a conference room already prepared

- S0 / employed: true; A support unknown; full [5, 7, 9]; A []; current_office
- S1 / employed: true; A support unknown; full [2]; A []; current_company

## test_504 / random

1. S0: Now , if I look here I see that you completed a BA in English ?
2. S1: Yes , that ’ s right . After graduating from high school in New York I attended York University in the UK . My major was English , and my minor was business studies . I completed my BA in 2004 .
3. S0: Yes , I ’ m pleased to see that you also got a distinction .
4. S1: Yes that ’ s right . I ’ Ve always enjoyed studying . My friends say I ’ m a bit of a bookworm , but my father always pushed us to succeed academically .
5. S0: Well , it looks like his encouragement paid off Rebecca . So how about extracurricular activities at University ?
6. S1: Well I ’ Ve always been keen on writing , so I became the editor for the University student magazine , which I really loved . Also I volunteered for a group called Shelter , to help the homeless in York .
7. S0: What did that involve ?
8. S1: Providing warm meals and shelter , especially in the winter months . I found it really fulfilling to be part of that group .
9. S0: I ’ m sure . Okay , now let ’ s move on to your work experience , shall we ?
10. S1: Yes , okay .

- S0 / employed: true; A support unknown; full [1, 3, 5, 9]; A []; professional_service_role
- S1 / job_seeking: true; A support true; full [1, 2, 3, 9, 10]; A [1, 3, 5, 9]; interview_context

## test_641 / random

1. S0: I ’ m pretty sure that Jim will turn out to be a good lawyer .
2. S1: How can you be so sure ?
3. S0: He knows a lot about law and he ’ s eloquent , too .


## test_57 / random

1. S0: Hello , Miao Li , Where are you going ?
2. S1: Hello , I am going to the store to buy some fruit .
3. S0: Oh , Would you do me a favor ?
4. S1: Yes ?
5. S0: Please mail this letter for me on your way to the store .
6. S1: Sure . Do you want it to be registered ?
7. S0: Yes , I think so . There are some pictures in it . It would be a great pity if they were lost .
8. S1: Yes , I will be glad to mail your letter .
9. S0: Thanks .
10. S1: you are welcome .


## test_764 / random

1. S0: are you a blogger ?
2. S1: sure I am . I've been writing a blog for almost three years .
3. S0: oh , it seems that I'm the only one who never blogs . When did you get started ?
4. S1: I began blogging when I first went to the US for my graduate strides .
5. S0: what do you usually write about ?
6. S1: at first , I'll write about my life there . Like interesting things on the campus , travel stories , special English words that I come across . Sometimes , I'll post my pictures on my blog so my family an
7. S0: that's interesting . How often do you write a blog ?
8. S1: it's random . If there happen to be a lot of things going on , I may add several new entries in a week , and if I've got nothing to share , I may leave my blog untouched for weeks .
9. S0: got it . Are you still updating your blog ?
10. S1: sure , since I came back from the US , I've been keeping the habit of blogging , simply to share my personal insights on any topic I like .
11. S0: good for you . I know many people just leave their blogs alone after the first few months .


## test_71 / random

1. S0: House keeping.May I come in ?
2. S1: Come in please .
3. S0: Good evening , sir . I come to make the bed . Shall I do it now or later ?
4. S1: Well , since you have come , do it now please ?
5. S0: That's all . Have a nice stay here .
6. S1: Thank you.Please get some soap for us .
7. S0: Just a moment . I will do it right now .

- S0 / employed: true; A support unknown; full [1, 3, 7]; A []; professional_service_role

## test_980 / random

1. S0: It's quiet everywhere in winter .
2. S1: Yes . I like winter .
3. S0: Me too .
4. S1: It's snowing heavily . What about taking a walk ?
5. S0: That's a good idea . Let's go !
6. S1: What a heavy snow ! Look ! The water is frozen .
7. S0: Take care ! Don't slip on the ground .
8. S1: I've got it . I like the feeling of stepping on the ice .
9. S0: Yes . Very wonderful .
10. S1: There is a snowman over there .
11. S0: How lovely it is !


## test_549 / random

1. S0: Excuse me . How long has it been since the business was founded ?
2. S1: It has been 12 years since it was founded in 1998 .
3. S0: So , it has a history for more than a decade ?
4. S1: Yes . And it was incorporated with other businesses in 2008 due to the global financial crisis .


## test_188 / random

1. S0: I am calling to ask about the position of an usher .
2. S1: Anything you would like to know ?
3. S0: What qualities do you expect the applicants to have ?
4. S1: We expect the usher girl to be good-looking , no less than 165 centimeters high , and love smiling .

- S0 / job_seeking: true; A support unknown; full [1, 3]; A []; position_enquiry
- S1 / employed: true; A support true; full [4]; A [3]; professional_service_role

## test_409 / random

1. S0: Hello ! How do I get more amenities ?
2. S1: I'm sorry , sir . I'm not sure I understand .
3. S0: I'm talking about the free stuff , like soap and shampoo .
4. S1: Oh , I see . So , you're saying that you've already run out of your amenities .
5. S0: No , no . I've got plenty left .
6. S1: Now I'm confused again ! What is the problem ?
7. S0: What am I going to do about souvenirs ?
8. S1: Oh , I get it ! You want souvenirs !
9. S0: Yes , I've got enough soap for my use , but no extra soap for souvenirs .
10. S1: Sir , our souvenir shop carries all those items , and as a guest you get a discount .
11. S0: Please ! Free souvenirs are the only true souvenirs .
12. S1: I understand completely , sir . Housekeeping will bring you souvenirs in just a moment .

- S1 / employed: true; A support unknown; full [10, 12]; A []; professional_service_role

## test_843 / random

1. S0: I must be going .
2. S1: Okay . Keep in touch .


## test_603 / random

1. S0: I can't believe how hot it is .
2. S1: It's not even noon yet .
3. S0: That means it will get hotter .
4. S1: I am dying from the heat .
5. S0: Turn on the air conditioner .
6. S1: It doesn't work .
7. S0: What happened ?
8. S1: I don't know .
9. S0: Did you call the repairman ?
10. S1: Of course .
11. S0: When is he coming ?
12. S1: He's busy . He said next week .


## test_224 / random

1. S0: Hello . Can you tell me what the procedures of applying for a job are ?
2. S1: Yes , of course . There are many steps . You can apply for the job on the Internet and then send your resume to the e-mail address of the company . And wail the feedback of the company .
3. S0: What is the qualification needed by the position ?
4. S1: You must have over 2 years'experience first .


## test_615 / random

1. S0: I'm looking forward to summer vacation .
2. S1: Me too .


## test_565 / random

1. S0: Good morning , sir . Sorry to disturb you . May I make up the room now ?
2. S1: Yes , please . We're on our way out , so we put the ' make up ' sign on . Could you bring us some towels and hangers ?
3. S0: No problem , sir . Everything will be ready when you come back .

- S0 / employed: true; A support unknown; full [1, 3]; A []; professional_service_role

## test_128 / random

1. S0: Good afternoon ! Trans Pacific Airline . How can I help you ?
2. S1: I ’ m calling to cancel my reservation for Trans Pacific Flight 8 on July 19 from Taipei to Minneapolis . Could you please make it for the same flight on August 2 instead of July 19 ?
3. S0: What ’ s your name , please ?
4. S1: My name is Judy Wang .
5. S0: How do you spell your name , please ?
6. S1: My first name is J-U-D-Y , and my last name is W-A-N-G .
7. S0: Please note that this ticket has a penalty of $ 75 for any change or cancellation .
8. S1: It ’ s OK . Where should I pay for the penalty ?
9. S0: At the airport . OK , Miss . Wang , your Flight 8 on July 19 from Taipei to Minneapolis is canceled . Your new reservation is Trans Pacific Flight 8 from Taipei to Minneapolis at 9 thirty a . m . on August 2 .
10. S1: That ’ s 1POJ7403 .
11. S0: That ’ s correct .
12. S1: Thank you !
13. S0: Is there anything else I can do for you ?
14. S1: No , thanks . I ’ m all set . Good-bye .

- S0 / employed: true; A support unknown; full [1, 7, 9]; A []; professional_service_role

## test_462 / random

1. S0: Good morning , Sir . Where are you going ?
2. S1: I ’ m going to England by flight BE987 .
3. S0: When is your flight ?
4. S1: 10:00 AM . When am I supposed to check in ?
5. S0: we are checking in . May I have your ticket and your health certificate and your luggage please .
6. S1: Here you are .
7. S0: Are you keeping the small bag as carry-on luggage , sir ?
8. S1: Yes .
9. S0: You must weigh that as well .
10. S1: all right .
11. S0: Your luggage is two pounds over . I ’ m afraid They'll be in excess luggage charge , Sir .
12. S1: How much must I pay ?
13. S0: It ’ s ten yuan .
14. S1: Here you are .
15. S0: This is your luggage check Which You must show when you disembark at your destination and here is your boarding pass and your ticket .
16. S1: Thanks .
17. S0: Now , please wait until your flight is called . There's about twenty-five minutes to go .
18. S1: I ’ m a little nervous . I ’ Ve never flown before .
19. S0: There ’ s nothing at all to worry about . Once you are in the air , it ’ s just like sitting at your sitting room . It ’ s going to be a very pleasant flight .

- S0 / employed: true; A support unknown; full [5, 9, 11, 13, 15]; A []; professional_service_role

## test_169 / random

1. S0: Hi Jim . Do you have a minute ?
2. S1: Sure , what ’ s up ?
3. S0: Some of us are going to start a soccer team . Would you like to join us ?
4. S1: I don ’ t know anything about it . Soccer isn ’ t as popular in my country as it is here .
5. S0: That ’ s all right . We ’ ll teach you .
6. S1: Is it anything like American football ?
7. S0: Not very much . It ’ s something like hockey , except that you use a big ball and no stick .
8. S1: I ’ ll come down and watch you play some day , and see what it ’ s like .
9. S0: Good idea . I think you ’ ll like it if you give it a chance .


## test_870 / random

1. S0: I had a big argument with david yesterday . I hope he ’ s not still mad at me .
2. S1: What did you argue about ?
3. S0: He borrowed some money from me and I needed it back . He said he didn ’ t have the money yet .
4. S1: Well , he should pay you back . It ’ s only fair .
5. S0: Yes , but I got angry with him too quickly . He probably thought that I mistrusted him . I shouldn ’ t have got angry .
6. S1: Did you lend him a lot of money ?
7. S0: Not much . I had to pay an unexpected bill , so I needed the money back .
8. S1: Well , talk to him about it next time you see him . He probably feels as bad about it as you do . Close friends sometimes have disagreements . It ’ s nothing unusual . Neither of you said anything really nasty , did you ?
9. S0: No , we didn ’ t . I guess you ’ re right . We should patch things up .
10. S1: Of course you should . You wouldn ’ t want a silly argument to ruin a long friendship , would you ?


## test_690 / random

1. S0: Hey , what's new ?
2. S1: Not much . Just sitting here eating some Chinese food . Is that the paper ? Why don't you open it and tell me my horoscope ?
3. S0: Ok , wait a minute ... let's see . I'm a Taurus , and it says , Mars is in the third house , and is soon to eclipse Venus . I don't know what that means , but then it says , Your charm and drive will win others over to your way of thinking . Remember to be positive . Sounds good to me .
4. S1: What about Gemini ? What's the prediction ?
5. S0: Since Mercury has crossed paths with Jupiter , your fortunes are falling . Bad luck will follow you today , and you will lose that which you value . Be careful .
6. S1: That sounds bad ! I'm really worried , what should I do ? Maybe I should go home and stay in the rest of the day .
7. S0: But we have a date tonight ! You can't stay at home because of a stupid horoscope .


## test_921 / random

1. S0: I had an accident .
2. S1: That's terrible !


## test_965 / random

1. S0: Hey Nick , what are you up to ?
2. S1: Not much , just heading over to the shooting range . You wanna come ?
3. S0: Seriously ? You mean to fire a real weapon ? I don ’ t know man .
4. S1: Yeah , it will be fun ! I have a 9mm pistol that is really easy to shoot . I also have a revolver that ’ s really fun too ! They have big targets at the range that we could use to practice and improve your aim .
5. S0: Yeah that would be cool ! Maybe I can also have a try at other weapons like a machine gun or a shotgun ! Maybe even a rocket launcher or an anti tank missile ! Or what about a flame thrower !
6. S1: Whoa , take it easy there Rambo . Don ’ t get carried away . These weapons are not toys , and you must first learn how to handle them properly . There are basic rules that you must abide by in order to be safe . For example , never handle a weapon that you haven ’ t inspected yourself . Always make sure there isn ’ t anything in the chamber , and never put your finger on the trigger unless you are ready to shoot !
7. S0: Wow , I didn ’ t know ! It always looks so cool and easy in the movies !
8. S1: The reality is different you know , running and firing a weapon is a lot harder than in the movies ! So are you ready ?
9. S0: Let ’ s do it !


## test_744 / random

1. S0: Hello , are you Chinese ?
2. S1: No , I'm Korean . Where are you from ?
3. S0: I'm from America . Are you settling in all right ?
4. S1: I've already found a flat and it's quite comfortable . What about you ?
5. S0: I live in my uncle's house . He came here ten years ago .
6. S1: What do you think of the local accent here ? Has it been causing you any problems ?
7. S0: I think it's just a matter of getting used to it .
8. S1: I can't agree more .


## test_815 / random

1. S0: You've heard of Bruce Jenner , haven't you ?
2. S1: He won the decathlon in the 1976 Olympics , right ?
3. S0: I read that he trained so much that he used to dream about jumping hurdles .
4. S1: I can think of better things to dream about ...
5. S0: Sometimes he would wake up covered in sweat , with his legs pumping away .
6. S1: That's crazy .


## test_4 / random

1. S0: What are your personal weaknesses ?
2. S1: I ’ m afraid I ’ m a poor talker . I ’ m not comfortable talking with the people whom I have just met for the first time . That is not very good for business , so I have been studying public speaking .
3. S0: Are you more of a leader or a follower ?
4. S1: I don ’ t try to lead people . I ’ d rather cooperate with everybody , and get the job done by working together .
5. S0: Do you think you can make yourself easily understood in English ?
6. S1: Yes , in most circumstances .
7. S0: Are you available for travel ?
8. S1: Yes , I like travelling . I am young , and unmarried . It ’ s no problem for me to travel frequently .

- S0 / employed: true; A support unknown; full [1, 3, 5, 7]; A []; professional_service_role
- S1 / married: false; A support unknown; full [8]; A []; explicit_unmarried
- S1 / job_seeking: true; A support true; full [1, 2, 3, 4, 7, 8]; A [1, 3, 5, 7]; interview_context

## test_136 / random

1. S0: I need help using the washer and dryer .
2. S1: Tell me what the problem is .
3. S0: I can't figure out how to turn them on .
4. S1: Do you have some quarters ?
5. S0: I didn't know I needed change .
6. S1: The washer costs 50 cents and the dryer costs a dollar .
7. S0: Where do I put the change ?
8. S1: The quarters go into the slot . You have to push the slot in , and the machine will turn on .
9. S0: Is that everything that I have to do ?
10. S1: That's all there is .
11. S0: I appreciate you helping me with this .
12. S1: If you need anything else , just let me know .


## test_896 / random

1. S0: I hear that Mary got mad .
2. S1: So I heard .
3. S0: What ’ s wrong with her ?
4. S1: She went over the edge after her son was killed in an accident .


## test_177 / random

1. S0: I ran it against that fence pole as I crashed . What do you think ? Damn , it hurts !
2. S1: We'll have to get you to a hospital . I can ride you on the back of my bike .
3. S0: I'm lucky I wasn't killed . I must have been going around forty-five miles an hour.There was too much gravel on that corner . I slid out .
4. S1: Yes , I almost slid too.Alright . This tourniquet is tight . How does it feel ?
5. S0: Make it tighter . I want the blood stopped.Then wrap some bandages around the cut . Then we can go . Ouch ! I hope I can walk .
6. S1: Alright , I'm twisting it around . You tell me when to stop .
7. S0: There . Stop !


## test_666 / random

1. S0: Could you please help me to check out the book ?
2. S1: Sure , what's the author's name , please .
3. S0: I can't remember that clearly . It probably be Charles ...
4. S1: Charles Dickens ?
5. S0: No , no , no . I'm not interested in literature .
6. S1: OK , do you know the title of the book ?
7. S0: Oh , sorry . I'm always absent-minded . I remember that I've put a note in my pocket .
8. S1: So , show me the note please .
9. S0: I can't find it now .
10. S1: Oh , such bad luck , sir . Can you please name the category of the book ?
11. S0: Let me see . It's not fiction . It's biography .
12. S1: OK , I'll search it for you . A moment , please .
13. S0: Thanks .

- S1 / employed: true; A support true; full [2, 6, 8, 10, 12]; A [1]; professional_service_role

## test_176 / random

1. S0: Look , how grand magnificent the Tiananmen Gate tour is !
2. S1: What's Tiananmen famous for ?
3. S0: It is largest pop square in the world.you see that is monument for the people's hero , and the Chairman Mao memorial hall on the south.there is great hall of the people on the west.there are two museums on the east .
4. S1: What's that ?
5. S0: That's the Forbidden city on the north of Gate building .
6. S1: All the sightseeing in china is very attractive and crescive.travelling to China is very worth one.thank you so much for your guides , and I'll miss you .


## test_753 / random

1. S0: What is life ?
2. S1: Don't ask such a question . You know it has no certain answer . Everyone knows it is in his heart .
3. S0: Then do you think that life is arranged by something above us .
4. S1: Maybe , the whirligig of time , who knows ?
5. S0: Right .


## test_583 / random

1. S0: Excuse me , Mr . Emory ? Mr . Macmillan , would like to know if you have the completed schedule for next week ?
2. S1: Yes , I do , Susan . Just a moment . Here it is .
3. S0: Thank you , sir . Sorry to trouble you .
4. S1: Not at all , Susan . Just tell him to leave it with my secretary when he ’ s finished with it

- S1 / employed: true; A support unknown; full [4]; A []; explicit_secretary_possession

## test_257 / random

1. S0: Did you hear about the robbery ?
2. S1: Did I hear about it ? I saw it happen .
3. S0: Are you serious ?
4. S1: I was there .
5. S0: What happened ?
6. S1: A man came into the bank with a gun .
7. S0: That's insane .
8. S1: I was so scared when I saw the gun .
9. S0: Then what happened ?
10. S1: He took the money and tried to get away .
11. S0: Did the cops show up in time ?
12. S1: He didn't even make it out the door .


## test_599 / random

1. S0: Do you have experience in advertising ?
2. S1: Yes , I used to have a part-time job in advertising company .
3. S0: What were you mean duties there ?
4. S1: I mostly did advertising planning .
5. S0: What qualities do you think an advertising planner should have ?
6. S1: I think an advertising planner should have active thoughts , creative talent , and be sensitive to the changes in the market .
7. S0: What was the most important thing you have learned at work ?
8. S1: The most important thing I learned was that I must continuously improve my abilities . Advertising is a constantly evolving trade and creativity is an important fact to success . If I want to make in marking in advertising industry , I can ’ t stop studying and creating .

- S0 / employed: true; A support unknown; full [1, 3, 5, 7]; A []; professional_service_role
- S1 / job_seeking: true; A support true; full [1, 2, 3, 4, 5, 6, 7, 8]; A [1, 3, 5, 7]; interview_context

## test_574 / random

1. S0: Hello . This is Mrs . Wilson . I'd like to buy a new car . Could you offer me a new type of the car , please ?
2. S1: Oh , Madam , buy what ?
3. S0: A new car . And I've got a small family , two children , and I haven't got a lot of money and ...
4. S1: Oh , oh , Madam , Madam , I'm afraid you have the wrong number .
5. S0: Isn't this the car store ?
6. S1: No . It's Mike's Sporting Goods .
7. S0: Oh , sorry . Do you know the number for a car store , then ?
8. S1: No . I don't . I suggest you look in the phone book .
9. S0: I'm sorry to have bothered you .
10. S1: No problem .

- S0 / has_children: true; A support unknown; full [3]; A []; explicit_children
- S1 / employed: true; A support unknown; full [6]; A []; professional_service_role

## test_215 / random

1. S0: Do you need a guide ?
2. S1: Yes , we are just looking for one . What's the charge per day ?
3. S0: It's $ 20 . If you are staying for more than 3 days in the city , the charge is $ 16 per day .
4. S1: That's reasonable .

- S0 / employed: true; A support true; full [1, 3]; A [2]; professional_service_role

## test_265 / random

1. S0: Hey , could you help me try and figure out how to get ready for my job interview ?
2. S1: The most important thing to do is to make sure you know the company and what services or products it provides . Do you know all about them ?
3. S0: Yes , I pretty much understand the company .
4. S1: Well , after you've done your research , you have to decide whether the company is casual or formal . Have you decided what they are yet ?
5. S0: Yes , I've been observing them .
6. S1: When you are choosing what to wear , keep all of that in mind . Have you chosen what to wear ?
7. S0: I already have something to wear .
8. S1: I would always be ready to go shopping with you ! Should we talk about other basics ?
9. S0: OK , I am ready to think of other things .
10. S1: You need to make sure you arrive on time , smile , be pleasant and friendly , look the person in the eye and answer all questions to the best of your ability . You'll do great !

- S0 / job_seeking: true; A support true; full [1, 3, 5, 7, 9]; A [2, 4, 6, 10]; explicit_interview

## test_653 / random

1. S0: Have you seen the new James Bond movie ?
2. S1: Oh , yes . You ?
3. S0: Yes . What did you think of it ?
4. S1: I thought it was better than the others-I really liked it . What did you think of it ?
5. S0: Yes , I liked it , too . It was exciting , but not over the top . Do you know what I mean ?
6. S1: Mmm . That's what I thought too . I really liked the car chase , and the opening credit sequence was very exciting . And I always enjoy watching Pierce Brosnan .
7. S0: Oh , yes . He's brilliant . Did you like the title song ?
8. S1: Not as much as last time , actually . What's the name of the American actor who was in the supporting role ?
9. S0: Hum , Edward Norton , or something like that . Did you like him ?
10. S1: Yes . He was excellent . They worked well together , don't you think ?
11. S0: I don't know . I think the woman was better . She provided a good love interest . Lucky James Bond !
12. S1: Yes !


## test_45 / random

1. S0: excuse me , could you tell me which line I ’ m supposed to stand in to buy bubble wrap and to post a package ?
2. S1: you can buy the bubble wrap here , but you ’ ll have to stand in line over here to post your passage .
3. S0: that ’ s a really long line . How long do you think it ’ ll take to get through all those people ?
4. S1: it takes about 3 minutes per person , so it ’ ll probably be about an hour ’ s wait .
5. S0: can I buy stamps here ?
6. S1: sure . How many would you like ?
7. S0: I need 30 for my Christmas cards .
8. S1: are you sending them abroad ?
9. S0: twenty of them are going abroad to China and America .
10. S1: do you have any going anywhere in the EU ? If you do , those are less expensive .
11. S0: no .
12. S1: ok , here you go . That will be 18 pounds and seventy two pence .
13. S0: and the bubble wrap ?
14. S1: that ’ s another quid .
15. S0: thanks a lot . You ’ Ve been very helpful .

- S1 / employed: true; A support unknown; full [6, 12, 14]; A []; professional_service_role

## test_201 / random

1. S0: Good morning , sir . May I see your passport ?
2. S1: Yes , of course . Here it is .
3. S0: Thank you . Are all these yours ?
4. S1: No , some of them are my friend's . Do you want her passport , too ?
5. S0: Yes , please . Do you have any carry-on items ?
6. S1: Do you want me to put it on the belt , too ?
7. S0: Yes , please . Would you please open this big suitcase ?
8. S1: OK . Just a moment . It's just some clothes and toiletries .
9. S0: OK . Do you have anything to declare ?
10. S1: I think there is nothing .
11. S0: Any fresh food , live plants , or animals ?
12. S1: Oh , no . None of that .
13. S0: Thank you . You may lock up your suitcase . Here are your passports .
14. S1: Thanks a lot .

- S0 / employed: true; A support unknown; full [1, 5, 7, 9, 11, 13]; A []; professional_service_role

## test_922 / random

1. S0: I found a new job after all , and I like this one even better than the last .
2. S1: You see ? Every cloud has a silver lining .

- S0 / employed: true; A support unknown; full [1]; A []; explicit_new_job

## test_357 / random

1. S0: I find that you spend little on handset charge every month . Have you any trick ?
2. S1: It's simple . You can use call transfer .
3. S0: Is it so simple ?
4. S1: Sure . You know , we spend most of our time at home or in the office every day , so I receive handset calls with the hand-free telephone , so I need pay little for receiving calls .
5. S0: It's true .
6. S1: Call transfer has many other advantages . When I am in places where network can't cover , such as the high building , I also use call transfer function , which transfers my calls to the hand-free telephone and I will not miss any call .
7. S0: That's all ?
8. S1: In hospitals or on planes , handsets will interfere with some equip-ment , so we must close our handsets . If you set call transfer , the problem will be solved .


## test_994 / random

1. S0: Every time when heroes came back from the battlefield , we took our hats off to them .
2. S1: You were showing respect and admiration for them .
3. S0: I wish I were a hero .


## test_650 / random

1. S0: Well , I'm afraid I must be going now . I have no idea it was so late .
2. S1: Stay for dinner with us .
3. S0: I'm afraid I can't . I have a dinner party at seven tonight . You see , I am going to England the day after tomorrow .
4. S1: Well , I won't keep you then . It was very nice of you to come to see me .
5. S0: It has been a pleasure . Goodbye .
6. S1: Goodbye . Thank you again for coming .


## test_515 / random

1. S0: Do you get the news that our company is trying to find out new tactics to test us ?
2. S1: I know something about it . Our company often organizes all kinds of lectures to improve our professional skills .
3. S0: It takes most of our weekends to listen to these boring lectures , so I can not bear it anymore . It is said that they think out some tests to check our management skills .
4. S1: Is that true ?
5. S0: Definitely !
6. S1: If that information is exact , I guess our company is willing to promote someone .

- S0 / employed: true; A support true; full [1, 3]; A [2, 6]; current_company
- S1 / employed: true; A support true; full [2, 6]; A [1, 3]; current_company

## test_830 / random

1. S0: Would you care to join for the picnic tomorrow ?
2. S1: Much to my regret , I'll have to meet my girlfriend at the airport then .
3. S0: We'd like to invite you for our dress party tomorrow evening , are you free ?
4. S1: Much as we'd like to , but we've booked up already for that time .
5. S0: What a pity ! You can't join us .
6. S1: So sorry . Next time we'll go , thanks anyway .


## test_417 / random

1. S0: I've come to hear about your offer .
2. S1: We have the offer ready for you . Let me check . 10 boxes with 50 brooches per box , at 20,000 yuan ; 20 boxes with 50 waistbands per box , at 30,000 yuan ; 15 boxes with other ornaments per box , at 7 , 500 yuan , for shipment in June . The offer is valid for five days .
3. S0: I can tell you right now that your prices are a little higher than we expected .
4. S1: You know that the prices of the ornaments have been rising in recent years . The prices we offer this time compare favorably with quotations you can get else where .
5. S0: I am afraid I can't agree with you there . I must point out your prices are higher than the quotations we've received from other companies .
6. S1: But you must take the design and quality into consideration . You know we are superior to others in design and quality . We have various styles , which the other companies cannot catch up with .
7. S0: I agree that yours are of the top .
8. S1: Well , since your order is large enough , can you give me a rough idea ?
9. S0: To have this business concluded , I should say a reduction of least 10 % would help .
10. S1: Impossible . How about 5 % off ?
11. S0: Right . A reduction of 5 % is acceptable .

- S0 / employed: true; A support unknown; full [3, 5, 9, 11]; A []; professional_service_role
- S1 / employed: true; A support unknown; full [2, 4, 6, 8, 10]; A []; professional_service_role

## test_69 / random

1. S0: 911 emergency . What is the problem ?
2. S1: I would like to report a break-in .
3. S0: When was this break-in ?
4. S1: I believe it happened last night .
5. S0: Where was the break-in ?
6. S1: It happened at my house .
7. S0: Was anything stolen ?
8. S1: I haven't checked yet .
9. S0: Why do you think there was a break-in ?
10. S1: My front window was broken .
11. S0: We'll send a squad car shortly .
12. S1: I'd appreciate that .

- S0 / employed: true; A support unknown; full [1, 11]; A []; professional_service_role

## test_147 / random

1. S0: Were you in a leadership position when you were a college student ?
2. S1: Yes . I was president of the Student Council of our university .
3. S0: Did you get any honors or awards at your university ?
4. S1: Yes . I was elected Excellent Party Member for four academic years .
5. S0: Were you involved in any club activities at your university ?
6. S1: Yes . I was a member of the Student Poetry Society . I like writing poems in my spare time .
7. S0: What extracurricular activities did you usually take part in at your college ?
8. S1: I sometimes played table tennis and sometimes played basketball .


## test_949 / random

1. S0: Hello , Ken .
2. S1: Hello , George .
3. S0: Have you just been to the cinema ?
4. S1: Yes , I have .
5. S0: What ’ s on ?
6. S1: Paris in the Spring .
7. S0: Oh , I ’ Ve already seen it . I saw it on television last year . It ’ s an old film , but it ’ s very good .
8. S1: Paris is a beautiful city . I have never been there . Have you ever been there , Ken ?
9. S0: Yes , I have . I was there in April .
10. S1: Paris in the spring , eh ?
11. S0: It was spring , but the weather was awful . It rained all the time .
12. S1: Just like dear old London !


## test_315 / random

1. S0: John , I was looking through some magazines for ideas about where we might go on vacation this year .
2. S1: I've already told my buddy , Mark , that I am going hunting with him in Alaska .
3. S0: You can't be serious !
4. S1: Hey , I've always gone hunting or fishing on vacation . I am sorry that bothers you .
5. S0: After a year together , I thought it pretty safe to assume that we would automatically spend our vacation together .
6. S1: Says who ? I don't think that is necessarily the case .
7. S0: You know , now that I think about it , I really don't have much more to say to you at all !
8. S1: Whatever you say !


## test_373 / random

1. S0: After the financial crisis , many industries are in incredibly cloudy situations . How do you think about our company ?
2. S1: The outlook in the future is very positive . Because we have been in this field for hundreds of years and we know how to survive this crisis safely .
3. S0: As the department I am applying for is expanding , I would like to contribute by effort .
4. S1: Great . Welcome to our company .

- S0 / job_seeking: true; A support true; full [3]; A [4]; explicit_application
- S1 / employed: true; A support true; full [2, 4]; A [1]; current_company

## test_72 / enriched

1. S0: Ms . Montgomery ? This is Richard Thomas . I ’ m sorry to bother you at home , but I ’ Ve got a bit of a problem .
2. S1: Oh ? What ’ s wrong ?
3. S0: My daughter ’ s just banged up her knee pretty badly and I ’ m going to have to take her to the hospital . I ’ ll be about two hours late .

- S0 / has_children: true; A support unknown; full [3]; A []; explicit_daughter
- S0 / has_daughter: true; A support unknown; full [3]; A []; explicit_daughter

## test_113 / enriched

1. S0: Can I help you ?
2. S1: Yes , I would like to buy a Walkman . Can you tell me about the models you have ?
3. S0: Well , we have a lot of models here.Did you want to listen to CD's or cassettes or the radio ?
4. S1: Mostly cassette tapes .
5. S0: Alright . There are several models you may want to look at.This Kreng portable cassette player is very good .
6. S1: Kreng ? I've never heard of that company .
7. S0: It's a German company.This unit has auto-reverse , recording capability , and an AM / FM radio band.It also has a built-in microphone .
8. S1: I suppose I don't want that one then . I don't like auto-reverse . It breaks too easily .
9. S0: Really ? Have you had an auto-reverse break before ?
10. S1: Yes , twice now . I think it's too high-tech , and so it's the first part that breaks .
11. S0: Hmm . You know , the problem might be dust . Did you clean the unit often ?
12. S1: Well . No , I didn't clean it.But still , I only had the last one two months , and it broke . I don't trust auto-reverse .
13. S0: Alright . Well . We have many units without auto-reverse.Here is a good unit . Very reliable.It has an AM / FM band , built-in microphone , recording capability , and no auto-reverse .
14. S1: How much is it ?
15. S0: This one sells for $ 39.99 .
16. S1: Can I test it out ?
17. S0: Of course .
18. S1: It sounds great . I'll take it .
19. S0: Fine . I think you'll be happy with it . It's a very good unit . Very reliable . I'll go get you a new one in a box . I will be back in just a moment .
20. S1: Thanks .

- S0 / employed: true; A support unknown; full [3, 5, 13, 15, 19]; A []; professional_service_role

## test_160 / enriched

1. S0: Mr.Chen , do you mind if I smoke ?
2. S1: I'm sorry , Mrs . Lin . We don't allow smoking in the office .


## test_742 / enriched

1. S0: Doris , Helen Mall is having a big sale this weekend . Do you wanna go ?
2. S1: Don't feel like it . I'm broke .
3. S0: Well , we can still do some window shopping , can we ?
4. S1: Just look around ? Nah , that ’ s boring .
5. S0: I'll go by myself then .

- S1 / financial_hardship: true; A support unknown; full [2]; A []; explicit_broke

## test_749 / enriched

1. S0: Hi , Becky , what's up ?
2. S1: Not much , except that my mother-in-law is driving me up the wall .
3. S0: What's the problem ?
4. S1: She loves to nit-pick and criticizes everything that I do . I can never do anything right when she ' s around .
5. S0: For example ?
6. S1: Well , last week I invited her over to dinner . My husband and I had no problem with the food , but if you listened to her , then it would seem like I fed her old meat and rotten vegetables . There's just nothing can please her .
7. S0: No , I can't see that happening . I know you're a good cook and nothing like that would ever happen .
8. S1: It's not just that . She also criticizes how we raise the kids .
9. S0: My mother-in-law used to do the same thing to us . If it wasn't disciplining them enough , then we were disciplining them too much . She also complained about the food we fed them , the schools we sent them too , and everything else under the sun .

- S0 / married: true; A support unknown; full [9]; A []; presupposition_only
- S0 / has_children: true; A support unknown; full [9]; A []; explicit_past_parenting
- S1 / married: true; A support unknown; full [6]; A []; explicit_husband
- S1 / has_children: true; A support unknown; full [8]; A []; explicit_parenting

## test_791 / enriched

1. S0: Hey Stacy . What's going on ?
2. S1: I'm pretty tired these days .
3. S0: Why ? You're not working so don't you have a lot of time on your hands ?
4. S1: I have so much house work to do . I have to take care of the kids , cook , clean , laundry , and the cycle never ends .
5. S0: How about your husband . Does he help much ?
6. S1: Not at all . He comes home and complains about his hard day at work . He expects me to do everything . He even wants me to feed him sometimes . Can you believe that ?
7. S0: That sucks .
8. S1: If he wasn't so lazy , I think I wouldn't have any complaints . He mows the lawn , but can you believe he tried to convince me to do it ?
9. S0: That's crossing the line .
10. S1: Oh well . I'll have to live with it . What else can I do ?

- S1 / married: true; A support true; full [5, 6]; A [5]; explicit_husband
- S1 / has_children: true; A support unknown; full [4]; A []; explicit_parenting
- S1 / unemployed: true; A support true; full [3, 4]; A [3]; not_working_homemaker_policy
- S1 / employed: false; A support false; full [3, 4]; A [3]; not_working_homemaker_policy

## test_800 / enriched

1. S0: Do you consider yourself a good mother ?
2. S1: Yes , I'm a very good mother and successful career woman .
3. S0: How can you manage to do both ? I mean , it is so hard to be a working mother .
4. S1: I think the most important thing is that you should be nice to yourself , like keeping housework simple , spending money on things that make life easier , buying yourself things you like , and so on . You can only be nice to others when you can be nice to yourself .
5. S0: Does your husband feel the same ?
6. S1: Yes . He is very understanding and supportive .

- S1 / married: true; A support true; full [5, 6]; A [5]; confirmed_husband
- S1 / has_children: true; A support true; full [1, 2, 3]; A [1, 3]; explicit_mother
- S1 / employed: true; A support true; full [2, 3]; A [3]; explicit_career_working

## test_822 / enriched

1. S0: Lee , I'm going to get married next month .
2. S1: Good news ! And congratulations !
3. S0: You are invited to my wedding .
4. S1: Thank you . I'll certainly be there .

- S0 / marriage_planned: true; A support unknown; full [1, 3]; A []; explicit_upcoming_wedding
