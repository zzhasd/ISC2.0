import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=path.dirname(fileURLToPath(import.meta.url));
const out=path.join(root,'outputs','six_algorithm_evaluation');
await fs.mkdir(out,{recursive:true});
const summary=JSON.parse(await fs.readFile(path.join(root,'scored_eval/results/summary.json'),'utf8'));
const data=JSON.parse(await fs.readFile(path.join(root,'scored_eval/data.json'),'utf8'));
const methods=Object.keys(data.methods);
const wb=Workbook.create();const main=wb.worksheets.add('六算法指标');const counts=wb.worksheets.add('计数与定义');
for(const sheet of [main,counts]){sheet.showGridLines=false;sheet.getRange('A1:H42').format.font={name:'Arial',size:11};sheet.getRange('A1:H42').format.verticalAlignment='center';sheet.getRange('A1:H42').format.rowHeight=25;}
main.tabColor='#233B53';main.getRange('A2').values=[['AGD-Eval 六算法指标']];main.getRange('A2').format.font={size:16,bold:true};
main.getRange('A3').values=[['298 段对话，7,868 条冻结预测，Qwen3.8-Max-0902 自动审核']];
main.getRange('A4').values=[['人工校准待完成，UNCERTAIN 按未证实计分']];
main.getRange('A6:H6').values=[['算法','P_raw','R_full','E1 Recall','E2 Recall','Slot Coverage','Useful Yield','P_atom']];
counts.getRange('A2').values=[['汇总计数与指标定义']];counts.getRange('A2').format.font={size:16,bold:true};
counts.getRange('A3').values=[['来源：冻结预测及 scored_eval/judgments 的结构化审核；所有算法共享同一事实池']];
const keys=['raw_count','raw_grounded','atom_count','atom_grounded','pool_total','pool_core','pool_full','E1_total','E1_full','E2_total','E2_full','slot_weight_hit','slot_weight_total','unique_core_found','valid_novel_core_found','semantic_redundant_valid'];
counts.getRange('A5:G5').values=[['计数',...methods.map(m=>data.methods[m])]];
counts.getRange(`A6:G${5+keys.length}`).values=keys.map(k=>[k,...methods.map(m=>summary[m].counts[k])]);
counts.getRange('B6:G21').setNumberFormat('#,##0');
const idx=k=>6+keys.indexOf(k);
const pairs=[['raw_grounded','raw_count'],['pool_full','pool_total'],['E1_full','E1_total'],['E2_full','E2_total'],['slot_weight_hit','slot_weight_total'],['unique_core_found','raw_count'],['atom_grounded','atom_count']];
for(let i=0;i<methods.length;i++){
 const m=methods[i],r=7+i,col=String.fromCharCode(66+i);
 main.getRange(`A${r}`).values=[[data.methods[m]]];
 main.getRange(`B${r}:H${r}`).formulas=[pairs.map(([n,d])=>`=IF('计数与定义'!${col}${idx(d)}=0,"n.a.",'计数与定义'!${col}${idx(n)}/'计数与定义'!${col}${idx(d)})`)];
}
main.getRange('B7:H12').setNumberFormat('0.00%');
main.getRange('A15:F15').values=[['算法','R_full 区间下限','R_full 区间上限','P_raw ≥ 90%','新事实 / 百对话','有据重复率']];
for(let i=0;i<methods.length;i++){
 const m=methods[i],r=16+i,src=7+i,col=String.fromCharCode(66+i),s=summary[m];
 main.getRange(`A${r}:C${r}`).values=[[data.methods[m],...s.R_full_CI95_dialogue_bootstrap]];
 main.getRange(`D${r}:F${r}`).formulas=[[`=IF(B${src}>=0.9,"达到","未达到")`,`='计数与定义'!${col}${idx('valid_novel_core_found')}/298*100`,`='计数与定义'!${col}${idx('semantic_redundant_valid')}/'计数与定义'!${col}${idx('raw_count')}`]];
}
main.getRange('B16:C21').setNumberFormat('0.00%');main.getRange('E16:E21').setNumberFormat('0.00');main.getRange('F16:F21').setNumberFormat('0.00%');
main.getRange('A24').values=[['区间：以对话为配对单位的 bootstrap，2,000 次，随机种子 20261106。']];
main.getRange('A25').values=[['池内召回率可能受共同漏检影响。区间不包含模型审核误差。']];
main.getRange('A26').values=[['本轮报告冻结输出工作点，尚未校准 Recall@Precision 筛选阈值。']];
main.getRange('A27').values=[['完整度统一计入所有事实字段，核心字段权重 2，其余字段权重 1。']];
const definitions=[['P_raw','整条预测全部原子断言为 E1/E2 的条数 / 原始预测数'],['P_atom','E1/E2 原子断言数 / 所有原子断言数'],['R_full','完整恢复所有必要字段的事实数 / 共享事实池总数'],['R_core','恢复所有核心字段的事实数 / 共享事实池总数'],['Slot Coverage','命中的必要字段权重 / 全部必要字段权重'],['Useful Yield','不同有据事实核心数 / 原始预测数'],['新事实','旧参考通过审核的原子断言共同无法覆盖的事实核心'],['有据重复率','完全有据且未新增事实字段的预测数 / 原始预测数'],['人工复核','旧参考标签变化及 UNCERTAIN 见 human_review_queue.csv']];
counts.getRange('A24:B32').values=definitions;
main.getRange('A6:H6').format={fill:'#233B53',font:{bold:true,color:'#FFFFFF'},horizontalAlignment:'center'};
main.getRange('A15:F15').format={fill:'#233B53',font:{bold:true,color:'#FFFFFF'},horizontalAlignment:'center'};
counts.getRange('A5:G5').format={fill:'#233B53',font:{bold:true,color:'#FFFFFF'},horizontalAlignment:'center',wrapText:true};counts.getRange('A5:G5').format.rowHeight=48;
main.getRange('A6:A21').format.columnWidth=29;main.getRange('B6:H21').format.columnWidth=18;
counts.getRange('A5:A32').format.columnWidth=34;counts.getRange('B5:G21').format.columnWidth=25;
for(const r of [8,10,12])main.getRange(`A${r}:H${r}`).format.fill='#F0F4F8';
for(const r of [17,19,21])main.getRange(`A${r}:F${r}`).format.fill='#F0F4F8';
main.getRange('D16:D21').format.horizontalAlignment='center';
counts.freezePanes.freezeRows(5);main.getRange('A4').format.font={color:'#9B5200'};
const originalGrounded=counts.getRange('B7').values[0][0];
const rawCount=counts.getRange('B6').values[0][0];
counts.getRange('B7').values=[[originalGrounded+1]];
wb.recalculate();
if(Math.abs(main.getRange('B7').values[0][0]-(originalGrounded+1)/rawCount)>1e-10)throw Error('Recalculation verification failed');
counts.getRange('B7').values=[[originalGrounded]];
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'六算法指标!A6:H12',include:'values,formulas',tableMaxRows:7,tableMaxCols:8,maxChars:5000})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!',options:{useRegex:true,maxResults:20},summary:'formula errors'})).ndjson);
for(const [sheet,range] of [['六算法指标','A1:H28'],['计数与定义','A1:G33']]){
 if(sheet==='计数与定义' && await fs.access(path.join(out,sheet+'.png')).then(()=>true,()=>false))continue;
 const preview=await wb.render({sheetName:sheet,range,scale:1,format:'png'});await fs.writeFile(path.join(out,sheet+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(out,'AGD-Eval_六算法指标.xlsx'));
console.log('EXPORTED',out);
