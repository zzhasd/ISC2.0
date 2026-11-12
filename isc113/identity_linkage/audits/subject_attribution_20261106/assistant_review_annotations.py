"""Explicit annotations made by the primary assistant after reading all four
blind review packets. These are assistant judgments, NOT human gold labels.
Unflagged means 'no clear strict transfer confirmed', NOT 'fully correct'.
No automatic screening labels were read before these annotations were fixed.
"""
from isc113.identity_linkage.subject_audit import OUT, STRICT
from isc113.identity_linkage.core import load, freeze, digest

GROUPS = [
 # case, IDs, source A turn, literal quote, explanation, optional labels
 ('36a0f7906df78c6204f8_D6',[2,3,7,13],8,'去年まではほとんどオンラインでした。','A 讲述自己的学校和线上学习经历；把这些经历或相应学生身份转给 B，A 的附和并不确立 B 也经历了这些事。'),
 ('36a0f7906df78c6204f8_D6',[4,12],14,'弟も修学旅行がなくなってしまってかわいそうでした。','A 无他人领属标记的弟弟自述，被写成 B 的弟弟及其经历。'),
 ('36a0f7906df78c6204f8_D6',[9],12,'大学でも毎日感染者が出ているみたいです。もうオンライン100％は嫌ですね。','A 所在大学的情况及 A 不想全面上网课的想法被归给 B。'),
 ('36a0f7906df78c6204f8_D6',[10],13,'入学式は中止だったので卒業式は全員でやりたいです。','A 自己入学式取消、希望一起毕业的经历和愿望被归给 B。'),
 ('8f3f6d0e2bc20c97f8d7_D5',[2,5],7,'自炊です！','A 回答自己做饭，被写成 B 自己做饭。'),
 ('8f3f6d0e2bc20c97f8d7_D5',[6],11,'そうです、調味料使って','A 继续说明自己做饭使用调味料，被归给 B。'),
 ('8f3f6d0e2bc20c97f8d7_D5',[7],12,'てきとうですよ！','A 评价自己的做饭方式随意，被归给 B。'),
 ('8f3f6d0e2bc20c97f8d7_D5',[8],6,'シチューでした','A 回答自己的午餐是炖菜，被归给 B。'),
 ('8f3f6d0e2bc20c97f8d7_D5',[9],9,'中華ですかね！','A 在自己的烹饪话题中回答中餐，被写成 B 的选择。'),
 ('8f3f6d0e2bc20c97f8d7_D5',[10],10,'それは使わないです！','A 回答自己不用该物品，被归给 B。'),
 ('cf7811ce17df3c33d22e_D5',[9],13,'最初のが一番好きかな！','最喜欢第一部是 A 的个人评价；不能从中推成 B 也最喜欢第一部。'),
 ('cf7811ce17df3c33d22e_D5',[12],7,'私も好きですね。カラーズとか光あたりが好きです。','私も可支持共享某位艺人的喜好，但具体 Colors/Hikari 是 A 接着补充的歌曲偏好；短属性 favorite_artists 转成 B 的偏好。claim 的 familiar 分支另属支持不足。','OTHER_UNSUPPORTED','A_TO_B'),
 ('4a12330f1e0b3b610697_D10',[18],10,'あと一番部活の練習時間が他の部活より長かったです','上下文 A 刚说自己小中高参加吹奏乐部，这个练习时间是 A 的部活经历。'),
 ('005cf100a6e854518035_D2',[6,12],10,'ろ過できるグッズもあるとか。','这是 A 补充过滤用品的信息，没有把这句话报告为 B 说过，输出却写 B mentioned。','SPEAKER_REVERSAL','SPEAKER_REVERSAL'),
 ('2cebfc428fe6267991e2_D3',[9,24],14,'私はヨガで伸ばしてるのですが','明确是 A 用瑜伽拉伸，输出写成 B 做瑜伽或拉伸。'),
 ('2cebfc428fe6267991e2_D3',[10,19],14,'YouTube見ながらやると続きますよ！','A 介绍自己的 YouTube 瑜伽方法；A15 只说试过未指明的事情，不足以把这个具体方法给 B。'),
 ('2cebfc428fe6267991e2_D3',[18],13,'でも運動不足はよくないなあと少し筋トレしてますね。','A 先认同不爱运动，再转折介绍自己的少量力量训练，不能把转折后的行为给 B。'),
 ('2cebfc428fe6267991e2_D3',[21],6,'私もそうだと思います！','整条可见第 6 行是 A；claim 明写 B 的 response in turn 6，错误标注了说话人。笼统的 shared opinion 属性本身不因此被判错。','SPEAKER_REVERSAL','NO_CONFIRMED_STRICT_TRANSFER'),
 ('7f22565852d990bd9564_D2',[1,2],10,'ネトフリとか、ユーチューブプライムとか入っています。','A 回答自己的订阅服务，被写成 B 订阅 Netflix/YouTube Premium。'),
 ('7f22565852d990bd9564_D2',[3,17],14,'今やってるアニメとか、もう録画する必要がなくて。','A 接着介绍自己 Netflix 订阅的用途，被写成 B 的订阅及观看体验。'),
 ('7f22565852d990bd9564_D2',[4],15,'あとはオリジナルドラマがおもしろいです。','A 在自己订阅服务的话题中介绍原创剧用途和评价，被归给 B。'),
 ('7f22565852d990bd9564_D2',[5],13,'あとネトフリは必須ですね。','Netflix 必须是 A 对自己服务的评价，被归给 B。'),
 ('7f22565852d990bd9564_D2',[6,15],11,'オフラインで見れるのいいです。','上下文 A 刚介绍自己的订阅，离线观看是 A 对其服务的说明，被变成 B 的服务。'),
 ('7f22565852d990bd9564_D2',[7,16],12,'音楽聴くのに使えるんですよ。','A 说明自己上一句提及服务的听音乐用途，被归给 B 的服务/发言。'),
 ('7f22565852d990bd9564_D2',[18],15,'あとはオリジナルドラマがおもしろいです。','A 自己说原创剧有趣，被写成 B mentioned；短属性也把这项评价归给 B。','SPEAKER_REVERSAL','A_TO_B'),
 ('38beec98f14114faf8df_D4',[6],12,'季節が変わると新しいものが欲しくなります。','A 回答自己喜欢时尚、换季想买新衣，被写成 B 的愿望。'),
 ('38beec98f14114faf8df_D4',[7],15,'好きなものには投資したいって思っています。','A 对自己购物支出的说明，被写成 B 的投资偏好。'),
 ('df73a6571cfbbfaf67c1_D5',[8,9,15],2,'最近タイドラマにはまっており推し俳優を追っかけるのを楽しんでます。','A 开场讲自己的泰剧及追星爱好，随后 A7 才转问 B 的爱好，不能把前面的 A 爱好给 B。'),
 ('df73a6571cfbbfaf67c1_D5',[16,17],3,'youtubeで見てます！あとはユネクとかですね','A 回答自己的泰剧观看平台，被写成 B 的观看平台。'),
 ('df73a6571cfbbfaf67c1_D5',[11,12,20],13,'一応防災グッズは買って玄関に準備してるんですけど地震が多いの怖いので海外移住したいです。','A 讲自己买的防灾用品、放置位置及因害怕地震而移居海外的愿望，被给了 B。'),
 ('df73a6571cfbbfaf67c1_D5',[13,14,21],14,'幸福の国の北欧には憧れます。','A 延续自己的海外移居话题，表示憧憬北欧，不能改为 B 的偏好或观点。'),
 ('2394679f4c065d867bba_D6',[2],3,'ゲーム配信動画が多いですね！','A 回答自己看的视频类别是游戏直播，被写成 B 的观看行为。'),
 ('f948b39b8a6a8a0ca243_D2',[1,17,19],2,'それが飲まないんですよ。','A 回答自己不喝某种饮品，被给了 B。'),
 ('f948b39b8a6a8a0ca243_D2',[11,18],4,'麦茶です。ノンカフェインの。','A 回答自己的饮品是无咖啡因麦茶，被给了 B。'),
 ('da5b83a508afe80e1a15_D8',[19],1,'こんばんは','这句实际是 A 的招呼，claim 却写成 B greeted A；conversation evening 短属性不因此判主体错。','SPEAKER_REVERSAL','NO_CONFIRMED_STRICT_TRANSFER'),
 ('da5b83a508afe80e1a15_D8',[20],5,'ちょっと夏が恋しいです。','A 自己说怀念夏天；前面的附和不足以确立 B 也说过怀念夏天。'),
 ('da5b83a508afe80e1a15_D8',[22],14,'そうなんですね、残念','claim 明写 B said something at turn 14，但这条可见 14 行是 A 的回应；短属性的负面结果推断另行讨论。','SPEAKER_REVERSAL','NO_CONFIRMED_STRICT_TRANSFER'),
 ('6d0b9fc8db9f687d1397_D6',[14],3,'私も珈琲好きで毎日飲みますよ。','私も可支持 B 也喜欢咖啡，但不能把 A 随后说的每天喝这一频率直接给 B。'),
 ('24de896ada0d15bf853a_D8',[10],2,'こっちさむいです！','こっち指 A 这边，A4 再说明风冷，输出却把这个环境位置给了 B。'),
 ('6f2e518f7d0c86e96095_D2',[2],6,'良いですよー。安いし！','A 向对方介绍电扇好用便宜，被写成 B 表达的正面评价。'),
 ('6f2e518f7d0c86e96095_D2',[9],3,'扇風機ももうかたづけようかと。','A 自己准备收起风扇，被写成 B 拥有并准备收起风扇。'),
 ('6f2e518f7d0c86e96095_D2',[13],10,'お風呂上りとかに扇風機は必須だと思っていました。','A 说自己原本认为洗澡后电扇必不可少，不能转成 B 的使用或考虑。'),
 ('e126873898a5d71b7573_D3',[19],12,'文鳥も飼いましたよ。手乗りでとても可愛かったです。','A10-12 正在讲自己照顾猫、小鸟、仓鼠及文鸟的经历，被给了 B 的小宠物经验。'),
]


def write():
    sample=load(OUT/'review_sample.json')
    cases={c['case_id']:c for c in load(OUT/'cases.json')}
    flags={}
    for item in GROUPS:
        case_id,ids,turn_id,quote,reason,*labels=item
        assert case_id in sample['case_ids']
        turn=next(t for t in cases[case_id]['visible_turns'] if t['turn_id']==turn_id)
        assert quote in turn['text'],(case_id,quote)
        claim_label,attribute_label=labels if labels else ('A_TO_B','A_TO_B')
        for index in ids:
            key=(case_id,f'c{index}')
            assert key not in flags
            flags[key]=dict(claim_label=claim_label,attribute_label=attribute_label,turn_id=turn_id,quote=quote,reason=reason)
    reviewed=[]
    for case_id in sample['case_ids']:
        for c in cases[case_id]['candidates']:
            key=(case_id,c['claim_id'])
            flag=flags.get(key)
            reviewed.append(dict(case_id=case_id,claim_id=c['claim_id'],claim=c['claim'],attribute=c['attribute'],
                                 strict_transfer_confirmed=flag is not None,
                                 review=flag or dict(status='NO_CONFIRMED_STRICT_TRANSFER',note='Does not certify overall support/correctness; may still be ambiguous, generic or unsupported.')))
    assert len(reviewed)==349
    assert sum(r['strict_transfer_confirmed'] for r in reviewed)==65
    freeze(OUT/'assistant_review_conservative_v2.json',dict(reviewer='primary assistant, not a human annotator',
                                           blinded_to_automatic_screening=True,
                                           refinement_before_unblinding={'excluded':[{'case_id':'005cf100a6e854518035_D2','claim_id':'c14','reason':'Unobserved B report inferred from A question is unsupported reconstruction, not a clear same-action speaker reversal.'},{'case_id':'e126873898a5d71b7573_D3','claim_id':'c20','reason':'Mixed disjunction contains a possible A-cat-to-B-dog name transfer but also a looser causal association; excluded from conservative confirmed total.'}],
                                                                         'field_refinement':{'case_id':'cf7811ce17df3c33d22e_D5','claim_id':'c12','claim_label':'OTHER_UNSUPPORTED','attribute_label':'A_TO_B'}},
                                           method='read all A turns and both text fields for all 349 claims in the 20 fixed sampled dialogues; conservative confirmed flags only',
                                           strict_labels=sorted(STRICT),sample_digest=digest(sample),rows=reviewed))
    print('Assistant-reviewed:',len(reviewed),'rows;',len(flags),'clear strict transfer flags')


if __name__=='__main__':write()
